# LoanShield — Local Testing Scenarios & Benchmark Cases

This document outlines the **6 core test scenarios** to validate the security and underwriting decision workflows of the LoanShield application locally.

---

## 🚀 Setting Up the Local Host Engines

You can test these scenarios using two different interfaces:

### Option A: Premium 3D Custom Portal (Recommended)
This portal is built specifically for this application, implementing the visual guidelines, 3D particles, and real-time SVG flowcharts:
1.  In your terminal, navigate to the `loanshield` directory:
    ```bash
    cd loanshield
    ```
2.  Run the custom gateway server:
    ```bash
    make custom-ui
    ```
3.  Open **[http://127.0.0.1:18080](http://127.0.0.1:18080)** in your web browser.
4.  Use the **Select Benchmark Template** grid at the top to auto-fill the forms instantly.

### Option B: Built-in Google ADK Playground
This is the default Google ADK developer playground portal:
1.  In the `loanshield` directory, run:
    ```bash
    make playground
    ```
2.  Open **[http://127.0.0.1:18081](http://127.0.0.1:18081)** in your web browser.
3.  Select the `loanshield_workflow` from the dropdown list.
4.  Copy/paste the JSON inputs below into the prompt area to execute them.

---

## 📋 The 6 Test Scenarios & Inputs

### Scenario 1: Prime Profile (Auto Approve)
*   **Applicant**: Aarav Sharma
*   **Objective**: Test clean, low-risk workflow execution that results in immediate automated approval without interruptions.
*   **Expected Verdict**: `APPROVED` (Score ~ 85.0)
*   **ADK JSON Input**:
    ```json
    {
    "applicant_id": "APP-001",
    "customer_id": "CU-001",
    "name": "Aarav Sharma",
    "aadhar_number": "938570839347",
    "dob": "01-05-1976",
    "phone_number": "+91 98765 93810",
    "home_address": "Flat 101, Building 1, Sector 62, Noida, Uttar Pradesh 201301",
    "age": 50,
    "declared_income_monthly": 949535,
    "loan_amount": 2636955,
    "purpose": "Used Car Loan",
    "target_scenario": "Prime"
  }
    ```

---

### Scenario 2: Thin Credit Profile (HITL Underwriter Review)
*   **Applicant**: Zara Ahmed
*   **Objective**: Test Escalation to Human Underwriting. The applicant has thin credit history causing a risk score in the review band (60 to 75).
*   **Expected Flow**: The engine pauses at `human_underwriter_hitl_node` and requests input.
*   **Action Required**: Click **APPROVE LOAN** or **REJECT LOAN** in the override panel to resume.
*   **Expected Final Verdict**: `APPROVED` (if approved) or `REJECTED` (if rejected).
*   **ADK JSON Input**:
    ```json
    {
    "applicant_id": "APP-018",
    "customer_id": "CU-018",
    "name": "Zara Ahmed",
    "aadhar_number": "197581276140",
    "dob": "10-04-1999",
    "phone_number": "+91 98400 40495",
    "home_address": "Flat 322, Building 20, Besant Nagar, Chennai, Tamil Nadu 600090",
    "age": 27,
    "declared_income_monthly": 422535,
    "loan_amount": 1360170,
    "purpose": "Major Purchase",
    "target_scenario": "Thin Credit"
  } 
    ```

---

### Scenario 3: High Debt-to-Income Ratio (Auto Reject)
*   **Applicant**: Shaurya Pratap
*   **Objective**: Test automated reject due to financial insolvency (high DTI).
*   **Expected Verdict**: `REJECTED` (Score < 50.0)
*   **Adverse Action Reasons**: Low FICO credit score, high debt-to-income ratio.
*   **ADK JSON Input**:
    ```json
    {
    "applicant_id": "APP-031",
    "customer_id": "CU-031",
    "name": "Shaurya Pratap",
    "aadhar_number": "161971807456",
    "dob": "06-03-1994",
    "phone_number": "+91 98765 10851",
    "home_address": "Flat 491, Building 11, Sector 62, Noida, Uttar Pradesh 201301",
    "age": 32,
    "declared_income_monthly": 385900,
    "loan_amount": 5510975,
    "purpose": "Emergency Expenses",
    "target_scenario": "High DTI"
  }
    ```

---

### Scenario 4: Identity / Synthetic Fraud Flag (Auto Reject)
*   **Applicant**: Avani Mehta
*   **Objective**: Test automated fraud prevention. The SSN matches the credit bureau records but the associated name does not, indicating identity mismatch/synthetic fraud.
*   **Expected Verdict**: `REJECTED` (Fraud Flag = True)
*   **Adverse Action Reasons**: High-risk synthetic fraud flag triggered (identity mismatch).
*   **ADK JSON Input**:
    ```json
    {
    "applicant_id": "APP-042",
    "customer_id": "CU-042",
    "name": "Avani Mehta",
    "aadhar_number": "838723520773",
    "dob": "06-05-1985",
    "phone_number": "+91 91234 22676",
    "home_address": "Flat 634, Building 13, HSR Layout, Bengaluru, Karnataka 560102",
    "age": 41,
    "declared_income_monthly": 726835,
    "loan_amount": 3766265,
    "purpose": "Used Car Loan",
    "target_scenario": "Fraud"
  }
    ```

---

### Scenario 5: Missing Required Documents (HITL Document Bypass)
*   **Applicant**: Rishabh Pant
*   **Objective**: Test Escalation to Document Check. The applicant's document storage checklist is incomplete.
*   **Expected Flow**: The engine pauses at `gatekeeper_node` and requests input (`document_override`).
*   **Action Required**: Click **Override & Resume** (approves bypassing document checks) or **Reject Application**.
*   **Expected Final Verdict**: If overridden, continues and completes risk assessment.
*   **ADK JSON Input**:
    ```json
    {
    "applicant_id": "APP-047",
    "customer_id": "CU-047",
    "name": "Rishabh Pant",
    "aadhar_number": "268836004533",
    "dob": "01-09-1987",
    "phone_number": "+91 94321 15695",
    "home_address": "Flat 699, Building 23, Salt Lake Sector 5, Kolkata, West Bengal 700091",
    "age": 39,
    "declared_income_monthly": 568820,
    "loan_amount": 1734680,
    "purpose": "Business Venture",
    "target_scenario": "Missing Documents"
  }
    ```

---

### Scenario 6: Terminated Employment Status (Auto Reject)
*   **Applicant**: Ranbir Kapoor
*   **Objective**: Test rejection due to lack of stable source of income (recent termination status in employment records).
*   **Expected Verdict**: `REJECTED` (Score < 50.0)
*   **Adverse Action Reasons**: Employment termination flag (unstable income source).
*   **ADK JSON Input**:
    ```json
    {
    "applicant_id": "APP-051",
    "customer_id": "CU-051",
    "name": "Ranbir Kapoor",
    "aadhar_number": "632037211828",
    "dob": "14-11-1988",
    "phone_number": "+91 98765 59615",
    "home_address": "Flat 751, Building 1, Sector 62, Noida, Uttar Pradesh 201301",
    "age": 37,
    "declared_income_monthly": 807500,
    "loan_amount": 3825000,
    "purpose": "Debt Consolidation",
    "target_scenario": "Terminated Employment Fraud"
  }
    ```
