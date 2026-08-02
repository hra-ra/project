"""
main.py

FastAPI entrypoint. Thin HTTP layer over the tested orchestrator —
this file should stay boring on purpose: no business logic lives here,
only request/response handling. Run with:

    uvicorn main:app --port 8000

Requires env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY, GEMINI_API_KEY
"""

from datetime import datetime
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


# ==========================================
# MONTHLY TEACHER LEAVE COUNTER ENDPOINT
# ==========================================
@app.get("/analytics/teacher-absences")
def get_teacher_absence_analytics():
    """
    Tracks leave submissions per teacher for the current calendar month.
    Repeated leave applications automatically increment the leave count.
    Resets count at the start of each month.
    """
    try:
        db = get_db()
        current_year = datetime.now().year
        current_month = datetime.now().month

        # Fetch form submissions from DB layer safely
        forms = []
        if hasattr(db, 'get_form_submissions'):
            forms = db.get_form_submissions()
        elif hasattr(db, 'get_forms'):
            forms = db.get_forms()
        elif hasattr(db, 'forms'):
            forms = db.forms

        teacher_counts = {}

        for form in forms:
            # Handle object vs dictionary payload format
            if hasattr(form, '__dict__'):
                data = form.__dict__
            elif isinstance(form, dict):
                data = form
            else:
                continue

            # Extract teacher name from possible schema fields
            teacher_name = (
                data.get("teacher_name") or 
                data.get("teacher") or 
                (data.get("extraction") and isinstance(data.get("extraction"), dict) and data.get("extraction").get("teacher")) or 
                "Unknown Teacher"
            )
            
            teacher_name = str(teacher_name).strip().title()

            submitted_at = data.get("created_at") or data.get("timestamp") or data.get("date")
            
            is_current_month = True
            if submitted_at:
                try:
                    dt = datetime.fromisoformat(str(submitted_at).replace("Z", "+00:00"))
                    if dt.year != current_year or dt.month != current_month:
                        is_current_month = False
                except Exception:
                    pass

            if is_current_month and teacher_name != "Unknown Teacher":
                teacher_counts[teacher_name] = teacher_counts.get(teacher_name, 0) + 1

        response_data = [
            {
                "teacher_name": name,
                "leave_count": count
            }
            for name, count in teacher_counts.items()
        ]

        return {
            "status": "success",
            "data": response_data
        }

    except Exception as e:
        return {"status": "error", "message": str(e), "data": []}