import os
import csv
import pytest
from google.adk.apps import App
from google.adk.runners import InMemoryRunner
from google.genai import types

from app.agent import app as loanshield_app

@pytest.mark.asyncio
async def test_all_applicants():
    csv_path = "../datasets/main_applications_final.csv"
        
    assert os.path.exists(csv_path), f"Dataset not found at {csv_path}"
    
    runner = InMemoryRunner(app=loanshield_app)
    
    results = []
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            applicant_id = row["applicant_id"]
            customer_id = row["customer_id"]
            scenario = row["target_scenario"]
            
            # Setup runner session
            session = await runner.session_service.create_session(
                app_name="app", user_id="test_user"
            )
            
            # Map values to payload dictionary matching State expectations
            payload = {
                "applicant_id": applicant_id,
                "customer_id": customer_id,
                "name": row["name"],
                "ssn": row["ssn"],
                "dob": row["dob"],
                "phone_number": row["phone_number"],
                "home_address": row["home_address"],
                "age": int(row["age"]),
                "declared_income_monthly": float(row["declared_income_monthly"]),
                "loan_amount": float(row["loan_amount"]),
                "purpose": row["purpose"],
                "target_scenario": scenario
            }
            
            # Pack payload into parts
            import json
            payload_str = json.dumps(payload)
            content = types.Content(role="user", parts=[types.Part.from_text(text=payload_str)])
            
            # Run the workflow
            events = []
            async for event in runner.run_async(
                user_id="test_user",
                session_id=session.id,
                new_message=content
            ):
                events.append(event)
                
            # If the application required document completion (Rows 47-50), it interrupted
            # Let's check if the session is interrupted
            session_obj = await runner.session_service.get_session(
                app_name="app",
                user_id="test_user",
                session_id=session.id
            )
            
            if scenario == "Missing Documents":
                # Resume document check with "RESUME" override passed as a FunctionResponse part
                resume_content = types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                id="document_override",
                                name="document_override",
                                response={"value": "RESUME"}
                            )
                        )
                    ]
                )
                async for event in runner.run_async(
                    user_id="test_user",
                    session_id=session.id,
                    new_message=resume_content
                ):
                    events.append(event)
                
                session_obj = await runner.session_service.get_session(
                    app_name="app",
                    user_id="test_user",
                    session_id=session.id
                )
                
            # After complete runs or overrides, check decisions
            final_state = session_obj.state
            decision = final_state.get("decision")
            
            # If decision is HUMAN_REVIEW, simulate underwriter approving it to get final state
            if decision == "HUMAN_REVIEW":
                resume_underwriter = types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                id="underwriter_override",
                                name="underwriter_override",
                                response={"value": "APPROVE"}
                            )
                        )
                    ]
                )
                async for event in runner.run_async(
                    user_id="test_user",
                    session_id=session.id,
                    new_message=resume_underwriter
                ):
                    pass
                session_obj = await runner.session_service.get_session(
                    app_name="app",
                    user_id="test_user",
                    session_id=session.id
                )
                final_decision = session_obj.state.get("decision")
            else:
                final_decision = decision
                
            results.append({
                "row": i + 1,
                "applicant_id": applicant_id,
                "scenario": scenario,
                "score": final_state.get("composite_score"),
                "initial_decision": decision,
                "final_decision": final_decision,
                "fraud": final_state.get("fraud_flag")
            })
            
    # Print all results clearly
    for r in results:
        print(f"Row {r['row']}: ID={r['applicant_id']}, Scenario={r['scenario']}, Score={r['score']}, InitDec={r['initial_decision']}, FinalDec={r['final_decision']}, Fraud={r['fraud']}")
        
    # Assertions
    for r in results:
        scenario = r["scenario"]
        decision = r["initial_decision"]
        
        if scenario == "Prime":
            assert decision == "AUTO_APPROVE", f"Row {r['row']} ({r['applicant_id']}) expected AUTO_APPROVE, got {decision}"
        elif scenario == "Thin Credit":
            assert decision == "HUMAN_REVIEW", f"Row {r['row']} ({r['applicant_id']}) expected HUMAN_REVIEW, got {decision}"
        elif scenario == "High DTI":
            assert decision == "AUTO_REJECT", f"Row {r['row']} ({r['applicant_id']}) expected AUTO_REJECT, got {decision}"
        elif scenario == "Fraud":
            assert decision == "AUTO_REJECT", f"Row {r['row']} ({r['applicant_id']}) expected AUTO_REJECT, got {decision}"
            assert r["fraud"] is True
        elif scenario == "Terminated Employment":
            assert decision == "AUTO_REJECT", f"Row {r['row']} ({r['applicant_id']}) expected AUTO_REJECT, got {decision}"
            assert r["fraud"] is True
        elif scenario == "Missing Documents":
            # For missing documents, before override it should be None (paused)
            # But here we already did the document override, so it proceeded.
            # So let's check that the decision was resolved after resuming
            assert decision in ["AUTO_APPROVE", "HUMAN_REVIEW", "AUTO_REJECT"]
