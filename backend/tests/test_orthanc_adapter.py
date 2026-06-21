"""
Tests for OrthancAdapter (Спринт 3, Задача 3.1).
Uses mocked httpx.AsyncClient — no dependency on real Orthanc in unit tests.
"""
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone, timedelta

from app.adapters.orthanc import OrthancAdapter


class MockAsyncClient:
    """Mock httpx.AsyncClient that returns configured responses."""
    def __init__(self, response_factory=None):
        self.response_factory = response_factory or (lambda req: MockResponse(200, {}))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def request(self, method, url, **kwargs):
        return self.response_factory(method, url, kwargs)


class MockResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            from httpx import HTTPStatusError
            raise HTTPStatusError("error", request=None, response=self)


def make_factory(json_data, status=200):
    def factory(method, url, kwargs):
        return MockResponse(status, json_data)
    return factory


@pytest.fixture
def adapter():
    return OrthancAdapter()


@pytest.mark.asyncio
async def test_publish_mwl_success(adapter):
    def factory(method, url, kwargs):
        assert url.endswith("/modalities/worklist")
        assert kwargs.get("json", {}).get("0008,0050", {}).get("Value", [""])[0] == "260615-00001"
        return MockResponse(200, {"status": "ok"})

    with patch("httpx.AsyncClient", return_value=MockAsyncClient(factory)):
        result = await adapter.publish_mwl(
            accession_number="260615-00001",
            patient_name="Test^Patient",
            patient_id="123456789012",
            patient_birth_date="19900115",
            patient_sex="M",
            study_instance_uid="1.2.3.4.5",
            modality="CT",
            ae_title="CT1",
            scheduled_date="20260615",
            scheduled_time="100000",
            procedure_description="CT brain",
        )
        assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_publish_mwl_orthanc_down(adapter):
    def factory(method, url, kwargs):
        from httpx import ConnectError
        raise ConnectError("Connection refused")

    with patch("httpx.AsyncClient", return_value=MockAsyncClient(factory)):
        # Should raise because publish_mwl now propagates errors; scheduling catches them
        with pytest.raises(Exception):
            await adapter.publish_mwl(
                accession_number="260615-00001",
                patient_name="Test^Patient",
                patient_id="123456789012",
                patient_birth_date="19900115",
                patient_sex="M",
                study_instance_uid="1.2.3.4.5",
                modality="CT",
                ae_title="CT1",
                scheduled_date="20260615",
                scheduled_time="100000",
                procedure_description="CT brain",
            )


@pytest.mark.asyncio
async def test_get_study(adapter):
    def factory(method, url, kwargs):
        assert "/studies/" in url
        return MockResponse(200, {
            "ID": "study-id-123",
            "StudyInstanceUID": "1.2.3.4.5",
            "PatientMainDicomTags": {"PatientName": "Test^Patient"},
        })

    with patch("httpx.AsyncClient", return_value=MockAsyncClient(factory)):
        result = await adapter.get_study("1.2.3.4.5")
        assert result["ID"] == "study-id-123"


@pytest.mark.asyncio
async def test_get_study_summary_allows_partial_orthanc_tags(adapter):
    def factory(method, url, kwargs):
        if url.endswith("/studies/study-id-123"):
            return MockResponse(200, {
                "MainDicomTags": {
                    "StudyInstanceUID": "1.2.3.4.5",
                    "AccessionNumber": "",
                    "StudyDate": "20260617",
                },
                "PatientMainDicomTags": {
                    "PatientName": "King^Arlene",
                    "PatientID": "18002019",
                },
                "Series": ["series-id-123"],
            })
        if url.endswith("/series/series-id-123"):
            return MockResponse(200, {"MainDicomTags": {"Modality": "CT"}})
        return MockResponse(404, {})

    with patch("httpx.AsyncClient", return_value=MockAsyncClient(factory)):
        result = await adapter.get_study_summary("study-id-123")

    assert result["study_instance_uid"] == "1.2.3.4.5"
    assert result["accession_number"] is None
    assert result["patient_name_dicom"] == "King Arlene"
    assert result["patient_id_dicom"] == "18002019"
    assert result["modality"] == "CT"
    assert result["study_date"] == "20260617"


@pytest.mark.asyncio
async def test_get_viewer_url(adapter):
    def factory(method, url, kwargs):
        if url.endswith("/tools/find"):
            return MockResponse(200, ["orthanc-study-id-abc"])
        return MockResponse(404, {})

    with patch("httpx.AsyncClient", return_value=MockAsyncClient(factory)):
        url = await adapter.get_viewer_url("1.2.3.4.5")
        assert "stone-webviewer" in url
        assert "study=1.2.3.4.5" in url


@pytest.mark.asyncio
async def test_get_viewer_url_with_orthanc_id(adapter):
    url = await adapter.get_viewer_url("1.2.3.4.5", orthanc_study_id="cached-orthanc-id")
    assert "stone-webviewer" in url
    assert "study=1.2.3.4.5" in url


@pytest.mark.asyncio
async def test_study_exists_true(adapter):
    def factory(method, url, kwargs):
        assert url.endswith("/tools/find")
        return MockResponse(200, ["orthanc-study-id"])

    with patch("httpx.AsyncClient", return_value=MockAsyncClient(factory)):
        assert await adapter.study_exists("1.2.3.4.5") is True


@pytest.mark.asyncio
async def test_study_exists_false(adapter):
    def factory(method, url, kwargs):
        return MockResponse(200, [])

    with patch("httpx.AsyncClient", return_value=MockAsyncClient(factory)):
        assert await adapter.study_exists("1.2.3.4.5") is False


@pytest.mark.asyncio
async def test_list_new_studies(adapter):
    def factory(method, url, kwargs):
        assert "/changes" in url
        return MockResponse(200, {"Changes": []})

    with patch("httpx.AsyncClient", return_value=MockAsyncClient(factory)):
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        result = await adapter.list_new_studies(since)
        assert isinstance(result, list)


@pytest.mark.asyncio
async def test_verify_connection(adapter):
    with patch("httpx.AsyncClient", return_value=MockAsyncClient(make_factory({"Name": "Orthanc"}))):
        assert await adapter.verify_connection() is True

    def fail_factory(method, url, kwargs):
        from httpx import ConnectError
        raise ConnectError("Connection refused")

    with patch("httpx.AsyncClient", return_value=MockAsyncClient(fail_factory)):
        assert await adapter.verify_connection() is False
