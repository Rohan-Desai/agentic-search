"""Upload & document-management endpoints."""
from pathlib import Path

from fastapi import APIRouter, File, UploadFile

from app.core.config import get_settings
from app.models.schemas import UploadResponse
from app.services.ingest_service import ingest_file

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=UploadResponse)
async def upload_documents(files: list[UploadFile] = File(...)) -> UploadResponse:
    settings = get_settings()
    ingested = []
    for file in files:
        dest = Path(settings.upload_dir) / file.filename
        dest.write_bytes(await file.read())
        ingested.append(ingest_file(dest))
    return UploadResponse(documents=ingested)
