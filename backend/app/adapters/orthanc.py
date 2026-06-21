import httpx
from uuid import UUID
from datetime import datetime
from typing import Any
from urllib.parse import quote
from app.core.config import get_settings

settings = get_settings()


class OrthancAdapter:
    """Изолированный адаптер для работы с Orthanc DICOM server.

    Никогда не вызывать Orthanc REST напрямую из бизнес-логики.
    Только через этот адаптер.
    """

    def __init__(self):
        self.base_url = settings.ORTHANC_URL
        self.external_url = settings.ORTHANC_EXTERNAL_URL
        self.auth = (settings.ORTHANC_USER, settings.ORTHANC_PASSWORD)

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await client.request(
                method,
                f"{self.base_url}{path}",
                auth=self.auth,
                **kwargs,
            )

    async def publish_mwl(
        self,
        accession_number: str,
        patient_name: str,
        patient_id: str,
        patient_birth_date: str,
        patient_sex: str,
        study_instance_uid: str,
        modality: str,
        ae_title: str,
        scheduled_date: str,
        scheduled_time: str,
        procedure_description: str,
    ) -> dict:
        """Создать MWL запись в Orthanc при переходе заказа в SCHEDULED.

        DICOM теги по ТЗ раздел 8.1:
        (0010,0010) PatientName
        (0010,0020) PatientID (ИИН)
        (0010,0030) PatientBirthDate (YYYYMMDD)
        (0010,0040) PatientSex (M/F/O)
        (0008,0050) AccessionNumber
        (0020,000D) StudyInstanceUID
        (0008,0060) Modality
        (0040,0001) ScheduledStationAETitle
        (0040,0002) ScheduledProcedureStepDate
        (0040,0003) ScheduledProcedureStepTime
        (0032,1060) RequestedProcedureDescription
        """
        mwl_entry = {
            "0010,0010": {"vr": "PN", "Value": [{"Alphabetic": patient_name}]},
            "0010,0020": {"vr": "LO", "Value": [patient_id]},
            "0010,0030": {"vr": "DA", "Value": [patient_birth_date]},
            "0010,0040": {"vr": "CS", "Value": [patient_sex]},
            "0008,0050": {"vr": "SH", "Value": [accession_number]},
            "0020,000D": {"vr": "UI", "Value": [study_instance_uid]},
            "0008,0060": {"vr": "CS", "Value": [modality]},
            "0040,0001": {"vr": "AE", "Value": [ae_title]},
            "0040,0002": {"vr": "DA", "Value": [scheduled_date]},
            "0040,0003": {"vr": "TM", "Value": [scheduled_time]},
            "0032,1060": {"vr": "LO", "Value": [procedure_description]},
        }

        resp = await self._request(
            "POST",
            "/modalities/worklist",
            json=mwl_entry,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_study(self, study_instance_uid: str) -> dict:
        """Получить информацию об исследовании из Orthanc по StudyInstanceUID."""
        resp = await self._request("GET", f"/studies/{study_instance_uid}")
        resp.raise_for_status()
        return resp.json()

    async def find_study_summary_by_accession(self, accession_number: str) -> dict | None:
        """Найти исследование в Orthanc по Accession Number."""
        resp = await self._request(
            "POST",
            "/tools/find",
            json={
                "Level": "Study",
                "Query": {"AccessionNumber": accession_number},
            },
        )
        resp.raise_for_status()
        ids = resp.json()
        if not ids:
            return None
        return await self.get_study_summary(ids[0])

    async def get_study_summary(self, orthanc_study_id: str) -> dict:
        """Метаданные исследования из Orthanc по внутреннему ID."""
        resp = await self._request("GET", f"/studies/{orthanc_study_id}")
        resp.raise_for_status()
        data = resp.json()
        main_tags = data.get("MainDicomTags", {})
        patient_tags = data.get("PatientMainDicomTags", {})
        modality = main_tags.get("Modality", "") or await self._get_first_series_modality(data)
        return {
            "orthanc_study_id": orthanc_study_id,
            "study_instance_uid": main_tags.get("StudyInstanceUID", ""),
            "accession_number": main_tags.get("AccessionNumber", "") or None,
            "patient_name_dicom": self._format_patient_name(patient_tags.get("PatientName", "")),
            "patient_id_dicom": patient_tags.get("PatientID", ""),
            "modality": modality,
            "study_date": main_tags.get("StudyDate", ""),
        }

    async def _get_first_series_modality(self, study_data: dict) -> str:
        """Modality is often stored on series, not on study."""
        for series_id in study_data.get("Series", []) or []:
            try:
                resp = await self._request("GET", f"/series/{series_id}")
                resp.raise_for_status()
                modality = resp.json().get("MainDicomTags", {}).get("Modality", "")
                if modality:
                    return modality
            except Exception:
                continue
        return ""

    @staticmethod
    def _format_patient_name(value: Any) -> str:
        if isinstance(value, list):
            value = value[0] if value else ""
        if isinstance(value, dict):
            value = value.get("Alphabetic") or value.get("Ideographic") or value.get("Phonetic") or ""
        if not value:
            return ""
        return " ".join(str(value).replace("^", " ").split())

    async def list_study_summaries(self) -> list[dict]:
        """Список всех исследований в Orthanc с основными тегами."""
        resp = await self._request("GET", "/studies")
        resp.raise_for_status()
        study_ids = resp.json()
        summaries = []
        for study_id in study_ids:
            try:
                summaries.append(await self.get_study_summary(study_id))
            except Exception:
                continue
        return summaries

    async def resolve_orthanc_study_id(self, study_instance_uid: str) -> str | None:
        """Найти внутренний ID исследования в Orthanc по StudyInstanceUID."""
        resp = await self._request(
            "POST",
            "/tools/find",
            json={
                "Level": "Study",
                "Query": {"StudyInstanceUID": study_instance_uid},
            },
        )
        resp.raise_for_status()
        ids = resp.json()
        return ids[0] if ids else None

    async def study_exists(self, study_instance_uid: str) -> bool:
        """Проверить, что исследование с данным StudyInstanceUID есть в Orthanc."""
        return await self.resolve_orthanc_study_id(study_instance_uid) is not None

    async def get_viewer_url(
        self,
        study_instance_uid: str,
        orthanc_study_id: str | None = None,
    ) -> str:
        """Ссылка на Stone Web Viewer.

        Stone Web Viewer expects DICOM StudyInstanceUID in the `study`
        query parameter. Orthanc's internal study ID opens an empty viewer.
        """
        if orthanc_study_id:
            study_exists = True
        else:
            study_exists = await self.resolve_orthanc_study_id(study_instance_uid) is not None
        if not study_exists:
            raise ValueError(f"Study not found in Orthanc: {study_instance_uid}")
        return f"{self.external_url}/stone-webviewer/index.html?study={quote(study_instance_uid)}"

    async def list_new_studies(self, since: datetime) -> list[dict]:
        """Для поллинга — список студий новее since.

        Используется как запасной вариант вместо webhook.
        """
        resp = await self._request("GET", "/changes", params={
            "since": int(since.timestamp()),
            "limit": 100,
            "change-type": "NEW_SERIES",
        })
        resp.raise_for_status()
        changes = resp.json().get("Changes", [])

        studies = []
        for change in changes:
            if change.get("ChangeType") == "NEW_SERIES":
                series_id = change.get("ID")
                try:
                    study_resp = await self._request("GET", f"/series/{series_id}")
                    study_data = study_resp.json()
                    studies.append({
                        "orthanc_series_id": series_id,
                        "study_instance_uid": study_data.get("MainDicomTags", {}).get("StudyInstanceUID", ""),
                        "accession_number": study_data.get("MainDicomTags", {}).get("AccessionNumber", ""),
                    })
                except Exception:
                    continue

        return studies

    async def verify_connection(self) -> bool:
        """Проверить доступность Orthanc."""
        try:
            resp = await self._request("GET", "/system")
            return resp.status_code == 200
        except Exception:
            return False


orthanc_adapter = OrthancAdapter()
