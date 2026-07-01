from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel, Field

class VerifiedFile(BaseModel):
    type: str
    status: str
    extracted_name: Optional[str] = None
    extracted_employer: Optional[str] = None
    statement_period_days: Optional[int] = None

class DocumentStatus(BaseModel):
    customer_id: str
    document_vault_status: str  # "COMPLETE" or "INCOMPLETE"
    verified_files: List[VerifiedFile] = []
    missing_requirements: List[str] = []

class CreditBureauProfile(BaseModel):
    customer_id: str
    credit_score: int
    credit_history_length_months: int
    delinquencies: int
    total_tradelines: int
    monthly_debt_obligations: float

class BankingProfile(BaseModel):
    customer_id: str
    average_monthly_deposits: float
    average_monthly_withdrawals: float
    current_balance: float

class EmploymentProfile(BaseModel):
    customer_id: str
    employer_name: str
    employment_status: str  # "Active", "Terminated", etc.
    tenure_months: int

class AuditEvent(BaseModel):
    timestamp: str
    node_name: str
    severity: str  # "INFO", "WARNING", "CRITICAL"
    message: str
    details: Dict[str, Any] = {}

class LoanApplicationState(TypedDict, total=False):
    # Raw Inputs
    applicant_id: str
    customer_id: str
    name: str
    ssn: str
    dob: str
    phone_number: str
    home_address: str
    age: int
    declared_income_monthly: float
    loan_amount: float
    purpose: str
    target_scenario: str
    email: str

    # Redacted Fields (PII safe zone)
    redacted_name: str
    redacted_ssn: str
    redacted_dob: str
    redacted_phone_number: str
    redacted_home_address: str

    # MCP Fetched States
    documents: Optional[Dict[str, Any]]
    credit_profile: Optional[Dict[str, Any]]
    banking_profile: Optional[Dict[str, Any]]
    employment_profile: Optional[Dict[str, Any]]

    # Flags & Scoring
    fraud_flag: bool
    fraud_reasons: List[str]
    income_variance_pct: float
    calculated_dti: float
    credit_score_component: float
    dti_component: float
    cash_flow_component: float
    stability_modifier: float
    composite_score: float

    # Audit & Decisions
    decision: str  # "AUTO_APPROVE", "HUMAN_REVIEW", "AUTO_REJECT"
    underwriter_override: Optional[str]  # "APPROVE", "REJECT", None
    eco_letter: str
    audit_trail: List[Dict[str, Any]]
    errors: List[str]
