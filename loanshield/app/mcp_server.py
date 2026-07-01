import os
import json
import csv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List
from mcp.server.fastmcp import FastMCP

# Create the MCP server instance
mcp = FastMCP("loanshield_services")

# Resolve relative path to datasets (repo-relative loanshield/datasets/)
current_dir = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.abspath(os.path.join(current_dir, "..", "datasets"))

@mcp.tool()
def get_document_status(customer_id: str) -> Dict[str, Any]:
    """Retrieves document storage vault status and list of missing files for a customer.

    Args:
        customer_id: The unique customer identifier (e.g. CU-001).
    """
    json_path = os.path.join(DATASETS_DIR, "document_storage_mcp_final.json")
    if not os.path.exists(json_path):
        return {"error": f"Document store file not found at {json_path}"}

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if customer_id in data:
        return data[customer_id]
    return {"error": f"Customer {customer_id} not found in document store."}

@mcp.tool()
def get_credit_profile(customer_id: str) -> Dict[str, Any]:
    """Retrieves credit bureau profile including credit score, history length, and delinquencies.

    Args:
        customer_id: The unique customer identifier (e.g. CU-001).
    """
    csv_path = os.path.join(DATASETS_DIR, "credit_bureau_mcp_final.csv")
    if not os.path.exists(csv_path):
        return {"error": f"Credit bureau file not found at {csv_path}"}

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["customer_id"] == customer_id:
                return {
                    "customer_id": row["customer_id"],
                    "credit_score": int(row["credit_score"]),
                    "credit_history_length_months": int(row["credit_history_length_months"]),
                    "delinquencies": int(row["delinquencies"]),
                    "total_tradelines": int(row["total_tradelines"]),
                    "monthly_debt_obligations": float(row["monthly_debt_obligations"])
                }
    return {"error": f"Customer {customer_id} not found in credit bureau database."}

@mcp.tool()
def get_banking_profile(customer_id: str) -> Dict[str, Any]:
    """Retrieves banking profile including average monthly deposits, withdrawals, and current balance.

    Args:
        customer_id: The unique customer identifier (e.g. CU-001).
    """
    csv_path = os.path.join(DATASETS_DIR, "banking_mcp_final.csv")
    if not os.path.exists(csv_path):
        return {"error": f"Banking data file not found at {csv_path}"}

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["customer_id"] == customer_id:
                return {
                    "customer_id": row["customer_id"],
                    "average_monthly_deposits": float(row["average_monthly_deposits"]),
                    "average_monthly_withdrawals": float(row["average_monthly_withdrawals"]),
                    "current_balance": float(row["current_balance"])
                }
    return {"error": f"Customer {customer_id} not found in banking database."}

@mcp.tool()
def get_employment_profile(customer_id: str) -> Dict[str, Any]:
    """Retrieves employment verification profile including employer name, status, and tenure months.

    Args:
        customer_id: The unique customer identifier (e.g. CU-001).
    """
    csv_path = os.path.join(DATASETS_DIR, "employment_mcp_final.csv")
    if not os.path.exists(csv_path):
        return {"error": f"Employment data file not found at {csv_path}"}

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["customer_id"] == customer_id:
                return {
                    "customer_id": row["customer_id"],
                    "employer_name": row["employer_name"],
                    "employment_status": row["employment_status"],
                    "tenure_months": int(row["tenure_months"])
                }
    return {"error": f"Customer {customer_id} not found in employment database."}

@mcp.tool()
def send_notification(customer_id: str, decision: str, message: str, recipient_email: str = "") -> Dict[str, Any]:
    """Sends a notification via SMTP email if configured, or falls back to mock simulation.

    Args:
        customer_id: The customer ID.
        decision: The finalized decision (AUTO_APPROVE, HUMAN_REVIEW, AUTO_REJECT).
        message: The detailed notification letter content (used as email body).
        recipient_email: The recipient's email address.
    """
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = os.environ.get("SMTP_PORT")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")

    if smtp_host and smtp_port and smtp_user and smtp_password and recipient_email:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"LoanShield Credit Decision Notification - {decision}"
            msg["From"] = smtp_user
            msg["To"] = recipient_email

            text_part = MIMEText(message, "plain")
            msg.attach(text_part)

            with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_user, [recipient_email], msg.as_string())

            return {
                "status": "success",
                "customer_id": customer_id,
                "decision": decision,
                "channel": "SMTP Email",
                "delivered": True,
                "recipient": recipient_email
            }
        except Exception as e:
            return {
                "status": "error",
                "customer_id": customer_id,
                "decision": decision,
                "channel": "SMTP Email",
                "delivered": False,
                "error": str(e)
            }

    # Fallback to mock simulation if SMTP not configured
    return {
        "status": "success",
        "customer_id": customer_id,
        "decision": decision,
        "channel": "Slack & Email Mock Dispatcher",
        "delivered": True
    }

if __name__ == "__main__":
    mcp.run()
