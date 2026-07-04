import os
import io
import re
import json
import uuid
import asyncio
import datetime
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib import colors

from google.adk.runners import InMemoryRunner
from google.genai import types

from app.agent import app as loanshield_app

app = FastAPI(title="LoanShield Premium Frontend Gateway")

# Enable CORS for local cross-port testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from google.adk.workflow.utils._workflow_hitl_utils import (
    has_request_input_function_call,
    get_request_input_interrupt_ids,
    create_request_input_response,
    REQUEST_INPUT_FUNCTION_CALL_NAME
)

# In-memory store for active session states
sessions_store: Dict[str, Dict[str, Any]] = {}


@app.post("/api/session")
async def create_session(payload: Dict[str, Any]):
    session_id = str(uuid.uuid4())
    # Create the runner instance for this session
    runner = InMemoryRunner(app=loanshield_app)

    # Store session details. GROQ_API_KEY is expected to already be configured
    # server-side (see app/config.py) — no per-session key is collected from clients.
    sessions_store[session_id] = {
        "payload": payload,
        "runner": runner,
        "adk_session_id": None,
        "active_interrupt_id": None,
        "state": {}
    }
    return {"session_id": session_id}


@app.get("/api/run")
async def run_workflow(session_id: str):
    if session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="Session not found")

    session_info = sessions_store[session_id]
    runner = session_info["runner"]
    payload = session_info["payload"]

    # Create ADK runner session
    adk_session = await runner.session_service.create_session(
        app_name="app", user_id="test_user"
    )
    session_info["adk_session_id"] = adk_session.id

    async def event_generator():
        try:
            payload_str = json.dumps(payload)
            content = types.Content(role="user", parts=[types.Part.from_text(text=payload_str)])

            # Run workflow in memory
            async for event in runner.run_async(
                    user_id="test_user",
                    session_id=adk_session.id,
                    new_message=content
            ):
                # Fetch current state of session to stream progress
                session_obj = await runner.session_service.get_session(
                    app_name="app", user_id="test_user", session_id=adk_session.id
                )

                # Check if this event is an interrupt request using ADK helpers
                is_interrupted = has_request_input_function_call(event)
                interrupt_id = None
                interrupt_msg = None

                if is_interrupted:
                    interrupt_ids = get_request_input_interrupt_ids(event)
                    interrupt_id = interrupt_ids[0] if interrupt_ids else None
                    session_info["active_interrupt_id"] = interrupt_id

                    # Extract message from the function call args
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if part.function_call and part.function_call.name == REQUEST_INPUT_FUNCTION_CALL_NAME:
                                interrupt_msg = part.function_call.args.get(
                                    "message") if part.function_call.args else None

                yield f"data: {json.dumps({
                    'type': 'event',
                    'state': session_obj.state,
                    'is_interrupted': is_interrupted,
                    'interrupt_id': interrupt_id,
                    'interrupt_message': interrupt_msg
                })}\n\n"
                await asyncio.sleep(0.1)

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/resume")
async def resume_workflow(session_id: str, action: str):
    if session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="Session not found")

    session_info = sessions_store[session_id]
    runner = session_info["runner"]
    adk_session_id = session_info["adk_session_id"]

    if not adk_session_id:
        raise HTTPException(status_code=400, detail="Workflow has not been started yet")

    # Check current active interrupt from our store
    interrupt_id = session_info.get("active_interrupt_id")
    if not interrupt_id:
        # Fallback detection
        session_obj = await runner.session_service.get_session(
            app_name="app", user_id="test_user", session_id=adk_session_id
        )
        if session_obj.state.get("decision") == "HUMAN_REVIEW":
            interrupt_id = "underwriter_override"
        else:
            interrupt_id = "document_override"

    # Map action input to ADK function response using official ADK helper function
    resume_content = types.Content(
        role="user",
        parts=[
            create_request_input_response(
                interrupt_id=interrupt_id,
                response={"value": action.upper()}
            )
        ]
    )

    is_interrupted = False
    next_interrupt_id = None
    next_interrupt_msg = None

    async for event in runner.run_async(
            user_id="test_user",
            session_id=adk_session_id,
            new_message=resume_content
    ):
        if has_request_input_function_call(event):
            is_interrupted = True
            interrupt_ids = get_request_input_interrupt_ids(event)
            next_interrupt_id = interrupt_ids[0] if interrupt_ids else None
            session_info["active_interrupt_id"] = next_interrupt_id

            # Extract next interrupt message
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_call and part.function_call.name == REQUEST_INPUT_FUNCTION_CALL_NAME:
                        next_interrupt_msg = part.function_call.args.get("message") if part.function_call.args else None

    # Get updated session
    session_obj = await runner.session_service.get_session(
        app_name="app", user_id="test_user", session_id=adk_session_id
    )

    if not is_interrupted:
        session_info["active_interrupt_id"] = None

    return {
        "status": "success",
        "state": session_obj.state,
        "is_interrupted": is_interrupted,
        "interrupt_id": next_interrupt_id,
        "interrupt_message": next_interrupt_msg
    }


def _build_letter_pdf(letter_text: str, applicant_name: str = "", decision: str = "",
                      decision_date: str = "", applicant_id: str = "") -> bytes:
    """Renders the ECOA decision letter as a formatted PDF and returns the raw bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=LETTER,
        topMargin=0.9 * inch, bottomMargin=0.9 * inch,
        leftMargin=1 * inch, rightMargin=1 * inch,
        title="LoanShield Credit Decision Notice"
    )

    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        "LetterHeader", parent=styles["Heading1"],
        fontSize=16, textColor=colors.HexColor("#0A0A0A"), spaceAfter=4
    )
    meta_style = ParagraphStyle(
        "LetterMeta", parent=styles["Normal"],
        fontSize=9, textColor=colors.HexColor("#555555"), spaceAfter=18
    )
    body_style = ParagraphStyle(
        "LetterBody", parent=styles["Normal"],
        fontSize=11, leading=16, alignment=TA_JUSTIFY, spaceAfter=12
    )

    story = [
        Paragraph("LoanShield — Formal Credit Decision Notice", header_style),
    ]
    meta_bits = []
    if applicant_name:
        meta_bits.append(f"Applicant: {applicant_name}")
    if applicant_id:
        meta_bits.append(f"Application ID: {applicant_id}")
    if decision:
        meta_bits.append(f"Decision: {decision.replace('_', ' ')}")
    if decision_date:
        meta_bits.append(f"Date: {decision_date}")
    if meta_bits:
        story.append(Paragraph(" &nbsp;|&nbsp; ".join(meta_bits), meta_style))
    story.append(Spacer(1, 6))

    # Split on blank lines so each paragraph wraps/justifies correctly
    for para in re.split(r"\n\s*\n", letter_text.strip()):
        cleaned = para.strip().replace("\n", "<br/>")
        if cleaned:
            # Escape any characters that would be misread as markup
            cleaned = cleaned.replace("&", "&amp;").replace("<br/>", "\x00BR\x00")
            cleaned = cleaned.replace("<", "&lt;").replace(">", "&gt;")
            cleaned = cleaned.replace("\x00BR\x00", "<br/>")
            story.append(Paragraph(cleaned, body_style))

    doc.build(story)
    return buffer.getvalue()


@app.post("/api/letter/pdf")
async def generate_letter_pdf(payload: Dict[str, Any]):
    """Generates a downloadable PDF of the final ECOA credit decision letter."""
    letter_text = (payload or {}).get("letter", "").strip()
    if not letter_text:
        raise HTTPException(status_code=400, detail="No letter content provided")

    applicant_name = payload.get("applicant_name", "")
    applicant_id = payload.get("applicant_id", "")
    decision = payload.get("decision", "")
    decision_date = payload.get("decision_date", "")

    pdf_bytes = _build_letter_pdf(
        letter_text,
        applicant_name=applicant_name,
        decision=decision,
        decision_date=decision_date,
        applicant_id=applicant_id
    )

    safe_id = re.sub(r"[^A-Za-z0-9_-]", "", applicant_id) or "letter"
    filename = f"LoanShield_Decision_Notice_{safe_id}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# Expose sample dataset records to client
@app.get("/api/benchmark")
async def get_benchmark_cases():
    import csv
    csv_path = "../datasets/main_applications_final.csv"
    if not os.path.exists(csv_path):
        csv_path = "datasets/main_applications_final.csv"

    cases = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            cases.append({
                "row": i + 1,
                "applicant_id": row["applicant_id"],
                "customer_id": row["customer_id"],
                "name": row["name"],
                "aadhaar_number": row["aadhaar_number"],
                "dob": row["dob"],
                "phone_number": row["phone_number"],
                "home_address": row["home_address"],
                "age": int(row["age"]),
                "declared_income_monthly": float(row["declared_income_monthly"]),
                "loan_amount": float(row["loan_amount"]),
                "purpose": row["purpose"],
                "target_scenario": row["target_scenario"]
            })
    return cases


# Serve custom frontend static files
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))


@app.get("/")
async def get_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Loanshield custom server running. Static files directory missing."}


if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=18080)