"""
main.py

FastAPI entrypoint. Thin HTTP layer over the tested orchestrator —
this file should stay boring on purpose: no business logic lives here,
only request/response handling. Run with:

    uvicorn main:app --port 8000

Requires env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY, GEMINI_API_KEY
"""

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db import SupabaseDB
from agent.orchestrator import process_leave_form, resolve_reviewed_form
from vision.extract_form import extract_form_data

app = FastAPI(title="School ERP — Autonomous Substitute Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> SupabaseDB:
    return SupabaseDB()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/alerts")
def get_alerts():
    db = get_db()
    return db.get_active_alerts()


@app.get("/timetable")
def get_timetable():
    db = get_db()
    return db.get_full_timetable()


@app.post("/forms/upload")
async def upload_form(file: UploadFile = File(...)):
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(400, f"Unsupported content type: {file.content_type}")

    image_bytes = await file.read()

    try:
        extraction = extract_form_data(image_bytes, media_type=file.content_type)
    except Exception as e:
        raise HTTPException(502, f"Extraction failed: {e}")

    db = get_db()
    result = process_leave_form(extraction, db)
    return result


class ReviewCorrection(BaseModel):
    teacher_name: str
    date: str
    reason: str | None = None
    submitted_by: str | None = None
    sections_affected: str | None = None


@app.post("/forms/{form_id}/review")
def submit_review_correction(form_id: str, correction: ReviewCorrection):
    """
    Called when an admin corrects a form that was flagged needs_review
    (e.g. the vision model couldn't read the teacher's name). Re-runs
    the resolution pipeline using the human-provided values.
    """
    db = get_db()
    corrected_fields = {k: v for k, v in correction.model_dump().items() if v is not None}
    result = resolve_reviewed_form(form_id, corrected_fields, db)
    return result