import os
import json
import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, List, AsyncGenerator
from pydantic import BaseModel, Field

from google.adk.agents import LlmAgent
from google.adk.apps import App, ResumabilityConfig
from google.adk.models.lite_llm import LiteLlm
from google.adk.workflow import Workflow, JoinNode, FunctionNode, START
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.genai import types as genai_types

from app.config import config
from app.state import VerifiedFile, DocumentStatus, CreditBureauProfile, BankingProfile, EmploymentProfile, AuditEvent
from app.mcp_server import get_document_status, get_credit_profile, get_banking_profile, get_employment_profile, \
    send_notification

# Import our custom skills
from app.skills.pii_redactor import pii_redactor_skill
from app.skills.income_verify import income_verify_skill
from app.skills.dti_calculator import dti_calculator_skill
from app.skills.stability_modifier import stability_modifier_skill
from app.skills.risk_scoring import risk_scoring_skill
from app.skills.fraud_detection import fraud_detection_skill
from app.skills.explanation import generate_ecoa_letter


# Pydantic Schemas for agent structured inputs/outputs
class ExplanationOutput(BaseModel):
    eco_letter: str = Field(description="The formal credit decision notification letter following ECOA guidelines.")


# LiteLlm routes ADK's LlmAgent through Groq's OpenAI-compatible API.
# Requires GROQ_API_KEY to be set in the environment.
def groq_model() -> LiteLlm:
    return LiteLlm(model=f"groq/{config.model}")


# 1. Gatekeeper Node function (with HITL check)
async def gatekeeper_node_func(ctx: Context, node_input: Any) -> AsyncGenerator[Event, None]:
    # Extract dictionary payload from node_input dynamically
    if isinstance(node_input, genai_types.Content):
        try:
            text = node_input.parts[0].text
            payload = json.loads(text)
        except Exception:
            payload = {}
    elif isinstance(node_input, str):
        try:
            payload = json.loads(node_input)
        except Exception:
            payload = {}
    elif isinstance(node_input, dict):
        payload = node_input
    else:
        payload = dict(node_input)

    applicant_id = payload.get("applicant_id", "APP-UNKNOWN")
    customer_id = payload.get("customer_id", "CU-UNKNOWN")
    # Computed once here (not left for the LLM to guess) so the notification
    # letter always shows the real date the decision was processed.
    decision_date = datetime.datetime.now().strftime("%B %d, %Y")

    # Audit log
    audit_trail = [{
        "timestamp": datetime.datetime.now().isoformat(),
        "node_name": "gatekeeper_node",
        "severity": "INFO",
        "message": f"Initalized processing for application {applicant_id} / customer {customer_id}",
        "details": {}
    }]

    # 1a. Redact PII
    redacted = pii_redactor_skill(
        name=payload.get("name", ""),
        aadhaar_number=payload.get("aadhaar_number", ""),
        dob=payload.get("dob", ""),
        phone_number=str(payload.get("phone_number", "")),
        home_address=payload.get("home_address", "")
    )

    audit_trail.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "node_name": "gatekeeper_node",
        "severity": "INFO",
        "message": "PII fields redacted successfully.",
        "details": {}
    })

    # 1b. Fetch document status from MCP mock database
    doc_status = get_document_status(customer_id)
    if "error" in doc_status:
        audit_trail.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "node_name": "gatekeeper_node",
            "severity": "CRITICAL",
            "message": f"Document lookup failed: {doc_status['error']}",
            "details": {}
        })
        yield Event(
            output={"decision": "AUTO_REJECT", "errors": [doc_status["error"]]},
            route="incomplete_docs_reject",
            state={
                "decision": "AUTO_REJECT",
                "fraud_flag": True,
                "fraud_reasons": [doc_status["error"]],
                "audit_trail": audit_trail,
                "customer_id": customer_id,
                "applicant_id": applicant_id,
                "name": payload.get("name", ""),
                "email": payload.get("email", ""),
                "composite_score": 0.0,
                "credit_score_component": 0.0,
                "dti_component": 0.0,
                "cash_flow_component": 0.0,
                "stability_modifier": 1.0,
                "decision_date": decision_date,
                **redacted
            }
        )
        return

    vault_status = doc_status.get("document_vault_status", "INCOMPLETE")

    # 1c. Document HITL Check
    if vault_status == "INCOMPLETE":
        # Check if we have received resume overrides
        if not ctx.resume_inputs or "document_override" not in ctx.resume_inputs:
            audit_trail.append({
                "timestamp": datetime.datetime.now().isoformat(),
                "node_name": "gatekeeper_node",
                "severity": "WARNING",
                "message": f"Document status INCOMPLETE. Missing: {doc_status.get('missing_requirements', [])}. Initiating HITL interrupt.",
                "details": {}
            })
            ctx.state["audit_trail"] = audit_trail
            yield RequestInput(
                interrupt_id="document_override",
                message=f"Missing documents: {', '.join(doc_status.get('missing_requirements', []))}. Respond with RESUME or REJECT."
            )
            return

        # We got resume input!
        override_val = ctx.resume_inputs["document_override"]
        override = override_val.get("value", "RESUME") if isinstance(override_val, dict) else str(override_val)

        audit_trail = ctx.state.get("audit_trail", audit_trail)
        audit_trail.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "node_name": "gatekeeper_node",
            "severity": "INFO",
            "message": f"Underwriter provided document override action: {override}",
            "details": {}
        })

        if override.upper() == "REJECT":
            yield Event(
                output={"decision": "AUTO_REJECT", "reasons": ["Missing required documents rejected by underwriter"]},
                route="incomplete_docs_reject",
                state={
                    "decision": "AUTO_REJECT",
                    "fraud_flag": True,
                    "fraud_reasons": ["Missing required documents"],
                    "audit_trail": audit_trail,
                    "customer_id": customer_id,
                    "applicant_id": applicant_id,
                    "name": payload.get("name", ""),
                    "email": payload.get("email", ""),
                    "composite_score": 0.0,
                    "credit_score_component": 0.0,
                    "dti_component": 0.0,
                    "cash_flow_component": 0.0,
                    "stability_modifier": 1.0,
                    "decision_date": decision_date,
                    **redacted
                }
            )
            return
        else:
            # Underwriter bypassed the missing document warning (RESUME)
            doc_status["document_vault_status"] = "COMPLETE_BYPASSED"
            audit_trail.append({
                "timestamp": datetime.datetime.now().isoformat(),
                "node_name": "gatekeeper_node",
                "severity": "INFO",
                "message": "Document vault status bypassed and approved to proceed by underwriter.",
                "details": {}
            })

    # Complete documents case
    yield Event(
        output=payload,
        route="complete_docs",
        state={
            "customer_id": customer_id,
            "applicant_id": applicant_id,
            "name": payload.get("name", ""),
            "email": payload.get("email", ""),
            "declared_income_monthly": float(payload.get("declared_income_monthly", 0)),
            "loan_amount": float(payload.get("loan_amount", 0)),
            "age": int(payload.get("age", 0)),
            "documents": doc_status,
            "audit_trail": audit_trail,
            "decision_date": decision_date,
            **redacted
        }
    )


# 2. Financial Analyst Node function
# NOTE: This was originally an LlmAgent that called the lookup tools and asked the
# model to echo the numbers back verbatim ("Do not make up or guess any numbers").
# That combo of tools + a structured output_schema in one call isn't just
# provider-specific flakiness — Groq rejects it outright for tool-calling models
# (BadRequestError: "json mode cannot be combined with tool/function calling").
# Since the values must be reproduced exactly anyway, there's no upside to routing
# them through an LLM at all: this does the same deterministic lookups fraud_analysis_node
# does below, with zero risk of transcription errors and no dependency on which
# Groq model supports which combo of features.
def financial_analysis_node_func(ctx: Context, node_input: Any) -> Event:
    customer_id = ctx.state["customer_id"]

    credit = get_credit_profile(customer_id)
    banking = get_banking_profile(customer_id)
    employment = get_employment_profile(customer_id)

    audit_trail = ctx.state.get("audit_trail", [])
    errors = [d["error"] for d in (credit, banking, employment) if "error" in d]
    if errors:
        audit_trail.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "node_name": "financial_analysis_node",
            "severity": "CRITICAL",
            "message": f"Financial profile lookup failed: {'; '.join(errors)}",
            "details": {}
        })
    else:
        audit_trail.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "node_name": "financial_analysis_node",
            "severity": "INFO",
            "message": "Financial profile (credit, banking, employment) retrieved successfully.",
            "details": {}
        })

    financial_profile = {
        "credit_score": credit.get("credit_score", 0),
        "credit_history_length_months": credit.get("credit_history_length_months", 0),
        "delinquencies": credit.get("delinquencies", 0),
        "total_tradelines": credit.get("total_tradelines", 0),
        "monthly_debt_obligations": credit.get("monthly_debt_obligations", 0.0),
        "average_monthly_deposits": banking.get("average_monthly_deposits", 0.0),
        "average_monthly_withdrawals": banking.get("average_monthly_withdrawals", 0.0),
        "current_balance": banking.get("current_balance", 0.0),
        "employer_name": employment.get("employer_name", ""),
        "employment_status": employment.get("employment_status", ""),
        "tenure_months": employment.get("tenure_months", 0),
    }

    return Event(
        output=financial_profile,
        state={
            "financial_profile": financial_profile,
            "audit_trail": audit_trail
        }
    )


financial_analysis_node = FunctionNode(
    func=financial_analysis_node_func,
    rerun_on_resume=False,
    name="financial_analysis_node"
)


# 3. Fraud & Compliance Node function
def fraud_analysis_node_func(ctx: Context, node_input: Any) -> Event:
    customer_id = ctx.state["customer_id"]
    age = ctx.state["age"]
    loan_amount = ctx.state["loan_amount"]
    declared_income = ctx.state["declared_income_monthly"]

    # Query MCP directly for rules check
    credit = get_credit_profile(customer_id)
    emp = get_employment_profile(customer_id)
    banking = get_banking_profile(customer_id)

    fraud_res = fraud_detection_skill(
        age=age,
        loan_amount=loan_amount,
        credit_history_length_months=credit.get("credit_history_length_months", 0),
        credit_score=credit.get("credit_score", 0),
        employment_status=emp.get("employment_status", ""),
        declared_income_monthly=declared_income,
        verified_income=banking.get("average_monthly_deposits", 0.0)
    )

    audit_trail = ctx.state.get("audit_trail", [])
    if fraud_res["fraud_flag"]:
        for reason in fraud_res["fraud_reasons"]:
            audit_trail.append({
                "timestamp": datetime.datetime.now().isoformat(),
                "node_name": "fraud_analysis_node",
                "severity": "WARNING",
                "message": f"Fraud compliance rule triggered: {reason}",
                "details": {}
            })
    else:
        audit_trail.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "node_name": "fraud_analysis_node",
            "severity": "INFO",
            "message": "All deterministic fraud/compliance checks passed.",
            "details": {}
        })

    return Event(
        output=fraud_res,
        state={
            "fraud_flag": fraud_res["fraud_flag"],
            "fraud_reasons": fraud_res["fraud_reasons"],
            "audit_trail": audit_trail
        }
    )


# 4. Risk Scorer Node function (joins outputs)
def risk_scoring_node_func(ctx: Context, node_input: Any) -> Event:
    if ctx.state.get("fraud_flag", False):
        return Event(
            output={"decision": "AUTO_REJECT", "composite_score": 0.0},
            route="auto",
            state={
                "composite_score": 0.0,
                "decision": "AUTO_REJECT",
                "credit_score_component": 0.0,
                "dti_component": 0.0,
                "cash_flow_component": 0.0,
                "stability_modifier": 1.0,
                "audit_trail": ctx.state.get("audit_trail", []) + [{
                    "timestamp": datetime.datetime.now().isoformat(),
                    "node_name": "risk_scoring_node",
                    "severity": "CRITICAL",
                    "message": f"Fraud flag active — risk scoring bypassed. Reasons: {ctx.state.get('fraud_reasons', [])}",
                    "details": {}
                }]
            }
        )
    fin_data = ctx.state["financial_profile"]
    fraud_data = ctx.state

    declared_income = ctx.state["declared_income_monthly"]
    loan_amount = ctx.state["loan_amount"]

    # 4a. Verify Income Stability
    inc_verify = income_verify_skill(
        declared_income_monthly=declared_income,
        average_monthly_deposits=fin_data.get("average_monthly_deposits", 0.0)
    )

    # 4b. Calculate DTI ratio
    dti_res = dti_calculator_skill(
        monthly_debt_obligations=fin_data.get("monthly_debt_obligations", 0.0),
        verified_income=fin_data.get("average_monthly_deposits", 0.0)
    )

    # 4c. Calculate stability modifier
    stability = stability_modifier_skill(tenure_months=fin_data.get("tenure_months", 0))

    # 4d. Compute composite risk score
    score_res = risk_scoring_skill(
        credit_score=fin_data.get("credit_score", 0),
        delinquencies=fin_data.get("delinquencies", 0),
        dti_component=dti_res["dti_component"],
        current_balance=fin_data.get("current_balance", 0.0),
        loan_amount=loan_amount,
        average_monthly_deposits=fin_data.get("average_monthly_deposits", 0.0),
        average_monthly_withdrawals=fin_data.get("average_monthly_withdrawals", 0.0),
        stability_modifier=stability["stability_modifier"]
    )

    # Update fraud flag with income anomaly if any
    fraud_flag = fraud_data.get("fraud_flag", False)
    fraud_reasons = fraud_data.get("fraud_reasons", [])
    if inc_verify["income_anomaly"]:
        fraud_flag = True
        if "Income Mismatch Anomaly" not in fraud_reasons:
            fraud_reasons.append("Income Mismatch Anomaly")

    composite_score = score_res["composite_score"]

    # Apply thin credit history penalty to align thin credit profiles with the 40-69 range
    credit_history = fin_data.get("credit_history_length_months", 0)
    if credit_history < 6:
        composite_score = max(0.0, composite_score - 5.0)

    # Apply high DTI penalty to align high DTI scenarios with the < 40 range
    calculated_dti = dti_res["calculated_dti"]
    if calculated_dti > 0.45:
        composite_score = max(0.0, composite_score - 10.0)

    # Underwriting decision routing
    if fraud_flag or composite_score < 40.0:
        decision = "AUTO_REJECT"
        route = "auto"
    elif composite_score < 70.0:
        decision = "HUMAN_REVIEW"
        route = "human_review"
    else:
        decision = "AUTO_APPROVE"
        route = "auto"

    audit_trail = ctx.state.get("audit_trail", [])
    audit_trail.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "node_name": "risk_scoring_node",
        "severity": "INFO",
        "message": f"Risk evaluation complete. Composite Score: {composite_score:.1f}. Decision: {decision}",
        "details": {
            "credit_component": score_res["credit_score_component"],
            "dti_component": dti_res["dti_component"],
            "cash_flow_component": score_res["cash_flow_component"]
        }
    })

    return Event(
        output={"decision": decision, "composite_score": composite_score},
        route=route,
        state={
            "fraud_flag": fraud_flag,
            "fraud_reasons": fraud_reasons,
            "income_variance_pct": inc_verify["income_variance_pct"],
            "calculated_dti": dti_res["calculated_dti"],
            "credit_score_component": score_res["credit_score_component"],
            "dti_component": dti_res["dti_component"],
            "cash_flow_component": score_res["cash_flow_component"],
            "stability_modifier": stability["stability_modifier"],
            "composite_score": composite_score,
            "decision": decision,
            "audit_trail": audit_trail
        }
    )


# 5. Human Underwriter Override Node (HITL check)
async def human_underwriter_hitl_node_func(ctx: Context, node_input: Any) -> AsyncGenerator[Event, None]:
    audit_trail = ctx.state.get("audit_trail", [])

    if not ctx.resume_inputs or "underwriter_override" not in ctx.resume_inputs:
        audit_trail.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "node_name": "human_underwriter_hitl_node",
            "severity": "WARNING",
            "message": f"Escalated to human review. Composite risk score: {ctx.state.get('composite_score', 0.0):.1f}. Pausing execution.",
            "details": {}
        })
        ctx.state["audit_trail"] = audit_trail
        yield RequestInput(
            interrupt_id="underwriter_override",
            message=f"Application in thin-credit zone (Score: {ctx.state.get('composite_score', 0.0):.1f}). Approve or Reject."
        )
        return

    override_val = ctx.resume_inputs["underwriter_override"]
    override = override_val.get("value", "APPROVE") if isinstance(override_val, dict) else str(override_val)

    decision = "AUTO_APPROVE" if override.upper() == "APPROVE" else "AUTO_REJECT"

    audit_trail.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "node_name": "human_underwriter_hitl_node",
        "severity": "INFO",
        "message": f"Underwriter override action submitted: {override}. Finalizing application as {decision}.",
        "details": {}
    })

    yield Event(
        output={"decision": decision, "underwriter_override": override},
        state={
            "decision": decision,
            "underwriter_override": override,
            "audit_trail": audit_trail
        }
    )


# 6. Explanation & Output Node (LlmAgent)
explanation_node = LlmAgent(
    name="explanation_node",
    model=groq_model(),
    instruction="""You are a senior Compliance Officer Agent at LoanShield.
Your job is to write a formal credit decision notification letter.

Context Details (for your reasoning only — see Format requirements below on what may appear in the letter):
- Customer Name: {redacted_name}
- Final decision: {decision}
- Letter date: {decision_date}
- Risk score: {composite_score}
- Credit FICO component: {credit_score_component}
- Debt-to-income affordability component: {dti_component}
- Cash flow buffer component: {cash_flow_component}
- Stability modifiers: {stability_modifier}
- Fraud/Anomalies Detected: {fraud_flag}
- Compliance Reason(s): {fraud_reasons}

Format requirements:
- Head the letter with the date, using the exact value given in "Letter date" above. Never invent or reuse a different date.
- If approved, write a welcoming and congratulatory notification detailing that they passed our risk matrices.
- If declined, cite the specific reasons clearly in alignment with Section 701(a) of the Equal Credit Opportunity Act (ECOA). Address the reasons (e.g. low credit score, high debt-to-income ratio, cash flow insolvency, or synthetic/fraud flag triggers) in plain qualitative language.
- Do NOT include any numeric scores, percentages, or raw metric values anywhere in the letter (no composite score, component scores, stability modifier value, etc.) — describe the reasoning qualitatively only.
- Do NOT use abbreviations or short forms for financial terms — spell them out in full every time (e.g. write "debt-to-income ratio" in full, never "DTI"; write "Equal Credit Opportunity Act (ECOA)" in full on first use).
- DO NOT use the customer's actual Aadhaar Number, phone number, or home address. Reference the redacted fields compulsorily.
- Put your complete generated letter inside the 'eco_letter' field.
- At the end, do not use any name for regards. Just keep it to the role
""",
    output_schema=ExplanationOutput,
    output_key="explanation_result",
)


# 7. Notification Node (FunctionNode)
def notifier_node_func(ctx: Context, node_input: Any) -> Event:
    customer_id = ctx.state["customer_id"]
    decision = ctx.state["decision"]
    email = ctx.state.get("email", "")

    explanation_res = ctx.state["explanation_result"]
    eco_letter = explanation_res.get("eco_letter", "")

    # Restore actual applicant name in the notification letter for personalized dispatch
    applicant_name = ctx.state.get("name", "")
    if applicant_name and "[REDACTED_NAME]" in eco_letter:
        eco_letter = eco_letter.replace("[REDACTED_NAME]", applicant_name)

    resp = send_notification(
        customer_id=customer_id,
        decision=decision,
        message=eco_letter,
        recipient_email=email
    )

    audit_trail = ctx.state.get("audit_trail", [])
    audit_trail.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "node_name": "notifier_node",
        "severity": "INFO",
        "message": f"Notification successfully dispatched via {resp['channel']}",
        "details": resp
    })

    return Event(
        output={"status": "dispatched", "notification": resp},
        state={
            "eco_letter": eco_letter,
            "audit_trail": audit_trail,
            "notification_result": resp
        }
    )


# Wrap callable functions as FunctionNodes with correct rerun_on_resume settings
gatekeeper_node = FunctionNode(func=gatekeeper_node_func, rerun_on_resume=True, name="gatekeeper_node")
fraud_analysis_node = FunctionNode(func=fraud_analysis_node_func, rerun_on_resume=False, name="fraud_analysis_node")
risk_scoring_node = FunctionNode(func=risk_scoring_node_func, rerun_on_resume=False, name="risk_scoring_node")
human_underwriter_hitl_node = FunctionNode(func=human_underwriter_hitl_node_func, rerun_on_resume=True,
                                           name="human_underwriter_hitl_node")
notifier_node = FunctionNode(func=notifier_node_func, rerun_on_resume=False, name="notifier_node")

# Create join node
join = JoinNode(name="merge_analysis")

# Define Graph Workflow Edges using conditional route mapping dicts
edges = [
    # 1. Start application intake
    ('START', gatekeeper_node),

    # 2. Gatekeeper branches
    (gatekeeper_node, {
        "incomplete_docs_reject": explanation_node,
        "complete_docs": (financial_analysis_node, fraud_analysis_node)
    }),

    # 3. Parallel analysis branches merge into join, then risk scoring
    ((financial_analysis_node, fraud_analysis_node), join),
    (join, risk_scoring_node),

    # 4. Routing based on composite scoring (converging routes use the single "auto" route to prevent duplicate edges)
    (risk_scoring_node, {
        "auto": explanation_node,
        "human_review": human_underwriter_hitl_node
    }),

    # 5. Review node routes to explanation
    (human_underwriter_hitl_node, explanation_node),

    # 6. Final dispatch
    (explanation_node, notifier_node),
]

# Create the Workflow Graph agent
root_agent = Workflow(
    name="loanshield_workflow",
    edges=edges,
    rerun_on_resume=True
)

# App wrapping
app = App(
    root_agent=root_agent,
    name="app",
    resumability_config=ResumabilityConfig(is_resumable=True)
)