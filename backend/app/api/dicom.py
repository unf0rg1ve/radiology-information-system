from fastapi import APIRouter, HTTPException, Query
from app.adapters.orthanc import orthanc_adapter

router = APIRouter(prefix="/dicom", tags=["DICOM"])


@router.get("/viewer-url/{study_instance_uid}")
async def get_viewer_url(
    study_instance_uid: str,
    orthanc_study_id: str | None = Query(None),
):
    if not await orthanc_adapter.verify_connection():
        raise HTTPException(status_code=503, detail="Orthanc недоступен")

    if not await orthanc_adapter.study_exists(study_instance_uid):
        raise HTTPException(status_code=404, detail="Снимки не найдены в PACS")

    try:
        url = await orthanc_adapter.get_viewer_url(study_instance_uid, orthanc_study_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Снимки не найдены в PACS")

    return {"url": url}