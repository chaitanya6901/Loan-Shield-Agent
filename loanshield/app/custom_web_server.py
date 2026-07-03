import os
import json
import uuid
import asyncio
import datetime
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

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
    
    # Pop and store API key in the session info (not payload)
    api_key = payload.pop("gemini_api_key", None)
    
    # Store session details
    sessions_store[session_id] = {
        "payload": payload,
        "runner": runner,
        "gemini_api_key": api_key,
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
    
    # Dynamically inject the user-provided API key into the environment
    api_key = session_info.get("gemini_api_key")
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key
        os.environ["GOOGLE_API_KEY"] = api_key
        
    # Create ADK runner session
    adk_session = await runner.session_service.create_session(
        app_name="app", user_id="test_user"
    )
    session_info["adk_session_id"] = adk_session.id

    async def event_generator():
        nonlocal adk_session
        max_retries = 3
        backoff_base = 2

        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    adk_session = await runner.session_service.create_session(
                        app_name="app", user_id="test_user"
                    )
                    session_info["adk_session_id"] = adk_session.id

                payload_str = json.dumps(payload)
                content = types.Content(role="user", parts=[types.Part.from_text(text=payload_str)])

                async for event in runner.run_async(
                    user_id="test_user",
                    session_id=adk_session.id,
                    new_message=content
                ):
                    session_obj = await runner.session_service.get_session(
                        app_name="app", user_id="test_user", session_id=adk_session.id
                    )

                    is_interrupted = has_request_input_function_call(event)
                    interrupt_id = None
                    interrupt_msg = None

                    if is_interrupted:
                        interrupt_ids = get_request_input_interrupt_ids(event)
                        interrupt_id = interrupt_ids[0] if interrupt_ids else None
                        session_info["active_interrupt_id"] = interrupt_id

                        if event.content and event.content.parts:
                            for part in event.content.parts:
                                if part.function_call and part.function_call.name == REQUEST_INPUT_FUNCTION_CALL_NAME:
                                    interrupt_msg = part.function_call.args.get("message") if part.function_call.args else None

                    yield f"data: {json.dumps({
                        'type': 'event',
                        'state': session_obj.state,
                        'is_interrupted': is_interrupted,
                        'interrupt_id': interrupt_id,
                        'interrupt_message': interrupt_msg
                    })}\n\n"
                    await asyncio.sleep(0.1)

                break

            except Exception as e:
                estr = str(e)
                exc_type = type(e).__name__

                if "ResourceExhausted" in exc_type or "429" in estr or "RESOURCE_EXHAUSTED" in estr:
                    yield f"data: {json.dumps({'type': 'quota_error', 'message': 'API quota limit reached. Please wait 60 seconds and try again.'})}\n\n"
                    break

                is_unavailable = "UNAVAILABLE" in estr or "503" in estr or "ServiceUnavailable" in exc_type or "ServerError" in exc_type
                if is_unavailable and attempt < max_retries:
                    wait = backoff_base ** attempt
                    yield f"data: {json.dumps({'type': 'retry', 'message': f'Service temporarily unavailable. Retrying in {wait}s (attempt {attempt}/{max_retries})...'})}\n\n"
                    await asyncio.sleep(wait)
                else:
                    yield f"data: {json.dumps({'type': 'error', 'message': f'[{exc_type}] {estr}'})}\n\n"
                    break

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/resume")
async def resume_workflow(session_id: str, action: str):
    if session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session_info = sessions_store[session_id]
    runner = session_info["runner"]
    adk_session_id = session_info["adk_session_id"]
    
    # Dynamically inject the user-provided API key into the environment
    api_key = session_info.get("gemini_api_key")
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key
        os.environ["GOOGLE_API_KEY"] = api_key
        
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
                "ssn": row["ssn"],
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
