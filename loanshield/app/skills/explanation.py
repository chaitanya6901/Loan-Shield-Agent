from typing import Dict, Any, List
import datetime


def generate_ecoa_letter(
        name: str,
        decision: str,
        composite_score: float,
        credit_score: int,
        calculated_dti: float,
        fraud_reasons: List[str]
) -> str:
    """Generates an ECOA-aligned notice letter.

    Args:
        name: The applicant's name (or redacted representation).
        decision: AUTO_APPROVE, HUMAN_REVIEW, or AUTO_REJECT.
        composite_score: The composite risk score.
        credit_score: The credit score.
        calculated_dti: The calculated DTI.
        fraud_reasons: List of active fraud/compliance reasons.

    Returns:
        The notice letter text.
    """
    if decision == "AUTO_APPROVE":
        status = "Approved"
        body = (
            f"We are pleased to inform you that your application for credit has been approved. "
            f"Our automated underwriting system evaluated your credit profile and determined you meet all "
            f"eligibility requirements. Your risk-adjusted composite score was {composite_score:.1f}/100. "
            f"Thank you for choosing LoanShield."
        )
    elif decision == "HUMAN_REVIEW":
        status = "Pending Manual Review"
        body = (
            f"Your application has been received and is currently under review by our underwriting team. "
            f"Our automated scoring system generated a risk score of {composite_score:.1f}/100, which requires "
            f"additional manual verification of your thin-credit profile. "
            f"We will contact you shortly if additional documentation is required."
        )
    else:
        status = "Declined"
        reasons_text = ""
        if fraud_reasons:
            reasons_text = "\n- " + "\n- ".join(fraud_reasons)
        else:
            reasons = []
            if credit_score < 620:
                reasons.append(f"Insufficient credit score ({credit_score})")
            if calculated_dti > 0.45:
                reasons.append(f"High Debt-to-Income ratio ({calculated_dti * 100:.1f}%)")
            if composite_score < 40:
                reasons.append(f"Composite risk score ({composite_score:.1f}/100) below underwriting guidelines")

            if reasons:
                reasons_text = "\n- " + "\n- ".join(reasons)
            else:
                reasons_text = "\n- Insufficient credit profile metrics"

        body = (
            f"Thank you for your recent application. Your request for credit has been evaluated by our "
            f"automated underwriting system and was unfortunately declined. "
            f"In accordance with the Equal Credit Opportunity Act (ECOA), the principal reasons for this decision "
            f"are listed below:{reasons_text}\n\n"
            f"If you have any questions regarding this decision, you may contact our compliance department."
        )

    letter = (
        f"LOANSHIELD CREDIT DECISION NOTIFICATION\n"
        f"──────────────────────────────────────────────────\n"
        f"Applicant: {name}\n"
        f"Decision: {status}\n"
        f"Date: {datetime.datetime.now().strftime('%B %d, %Y')}\n"
        f"──────────────────────────────────────────────────\n\n"
        f"Dear {name},\n\n"
        f"{body}\n\n"
        f"Sincerely,\n"
        f"The LoanShield Underwriting Operations Team"
    )
    return letter