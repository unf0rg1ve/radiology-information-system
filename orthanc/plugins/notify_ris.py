import json
import urllib.request
import urllib.error

import orthanc

RIS_WEBHOOK_URL = "http://backend:8000/api/webhook/orthanc/stored"
WEBHOOK_SECRET = "ris-orthanc-webhook-secret"


def OnStoredInstance(dicom, instanceId):
    """Called by Orthanc when a new DICOM instance is stored."""
    try:
        study_uid = dicom.get("0020,000D", "")
        accession = dicom.get("0008,0050", "")
        series_uid = dicom.get("0020,000E", "")
        sop_instance_uid = dicom.get("0008,0018", "")
        modality = dicom.get("0008,0060", "")
        patient_name = dicom.get("0010,0010", "")
        patient_id = dicom.get("0010,0020", "")

        if not accession and not study_uid:
            orthanc.LogInfo("OnStoredInstance: no accession_number or study_uid, skipping")
            return

        orthanc_study_id = orthanc.RestApiGet(f"/instances/{instanceId}/study").decode("utf-8").strip('"')

        payload = json.dumps({
            "study_instance_uid": study_uid,
            "accession_number": accession,
            "series_uid": series_uid,
            "sop_instance_uid": sop_instance_uid,
            "modality": modality,
            "patient_name": patient_name,
            "patient_id": patient_id,
            "orthanc_instance_id": orthanc_study_id,
        }).encode("utf-8")

        req = urllib.request.Request(
            RIS_WEBHOOK_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Secret": WEBHOOK_SECRET,
            },
            method="POST",
        )

        resp = urllib.request.urlopen(req, timeout=10)
        orthanc.LogInfo(
            f"OnStoredInstance: notified RIS, status={resp.status}, "
            f"study={orthanc_study_id}, instance={instanceId}"
        )

    except urllib.error.URLError as e:
        orthanc.LogWarning(f"OnStoredInstance: failed to notify RIS: {e}")
    except Exception as e:
        orthanc.LogWarning(f"OnStoredInstance: unexpected error: {e}")
