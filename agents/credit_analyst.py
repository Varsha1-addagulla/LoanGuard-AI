from agents.base_agent import call_llm, parse_json_response

SYSTEM = (
    "You are a senior credit analyst at a major bank with 20 years of experience. "
    "You represent Priority 1 in the underwriting pipeline — credit quality is the first "
    "fundamental check after fraud screening. "
    "Always respond with valid JSON only — no markdown, no commentary outside the JSON object."
)

PRIORITY = "Priority 1"
PRIORITY_LEVEL = 1

# Fannie Mae thresholds — used in Python pre-classification and in the prompt
CREDIT_TIERS = [
    (720, None, "approve", "720+ — AUTO APPROVE: Meets Fannie Mae standard guidelines; lowest risk tier"),
    (620, 719,  "review",  "620–719 — REVIEW: Below Fannie Mae preferred minimum; compensating factors required"),
    (0,   619,  "reject",  "<620 — REJECT: Below Fannie Mae absolute minimum for conventional loans"),
]

LTI_TIERS = [
    (None, 3.0, "approve", "<3x — APPROVE: Well within Fannie Mae loan-to-income comfort zone"),
    (3.0,  5.0, "review",  "3–5x — REVIEW: Elevated loan-to-income; requires compensating factors"),
    (5.0,  None,"reject",  ">5x — REJECT: Exceeds Fannie Mae maximum loan-to-income threshold"),
]


def _classify_credit(score: int) -> tuple[str, str]:
    for lo, hi, rec, label in CREDIT_TIERS:
        if hi is None and score >= lo:
            return rec, label
        if lo <= score <= hi:
            return rec, label
    return "reject", "<620 — REJECT"


def _classify_lti(lti: float) -> tuple[str, str]:
    for lo, hi, rec, label in LTI_TIERS:
        if hi is None and lti >= lo:
            return rec, label
        if (lo is None or lti < hi) and (lo is None or lti >= lo):
            return rec, label
    return "reject", ">5x — REJECT"


def analyze_credit(data: dict) -> dict:
    loan_to_income = (
        data["loan_amount"] / data["annual_income"] if data["annual_income"] > 0 else 999
    )
    dti = (
        data["existing_debt"] / data["annual_income"] * 100 if data["annual_income"] > 0 else 100
    )

    credit_rec, credit_label = _classify_credit(data["credit_score"])
    lti_rec, lti_label = _classify_lti(loan_to_income)

    prompt = f"""You are Priority 1 — Credit Analysis — in a sequential bank underwriting pipeline.
The Fraud Hard Stop has already cleared this application. Your assessment gates all subsequent checks.

APPLICANT DATA
  Name:                {data['name']}
  Requested Loan:      ${data['loan_amount']:,.2f}
  Annual Income:       ${data['annual_income']:,.2f}
  Credit Score:        {data['credit_score']}
  Employment Years:    {data['employment_years']}
  Existing Debt:       ${data['existing_debt']:,.2f}
  Loan-to-Income:      {loan_to_income:.2f}x
  Existing Debt/Income:{dti:.1f}%

PRE-CLASSIFIED THRESHOLDS (Fannie Mae — state which was triggered):
  Credit Score:        {credit_label}
  Loan-to-Income:      {lti_label}

FANNIE MAE THRESHOLDS — CREDIT SCORE:
  720+    → AUTO APPROVE  — meets Fannie Mae standard guidelines; lowest risk tier
  620–719 → REVIEW        — below Fannie Mae preferred minimum; compensating factors required
  <620    → REJECT        — below Fannie Mae absolute minimum for conventional loans

FANNIE MAE THRESHOLDS — LOAN-TO-INCOME RATIO:
  < 3x    → APPROVE — well within Fannie Mae comfort zone
  3–5x    → REVIEW  — elevated; requires strong compensating factors (credit, employment)
  > 5x    → REJECT  — exceeds Fannie Mae maximum loan-to-income threshold

DECISION RULES:
  • If EITHER threshold triggers REJECT → overall recommendation is reject
  • If neither triggers reject but either triggers REVIEW → recommendation is review
  • Both must be APPROVE for an approve recommendation

In your analysis, explicitly name the exact threshold value (e.g. "credit score of 685 falls in the
620–719 REVIEW band") and state the policy consequence. Do not round or paraphrase the thresholds.

Respond with ONLY this JSON (no other text):
{{
  "analysis": "2-3 sentences explicitly naming the credit score threshold triggered and the loan-to-income threshold triggered, with exact values and Fannie Mae policy consequence for each",
  "confidence": <integer 0-100 where 100=very safe to approve, 0=definitely reject>,
  "recommendation": "<approve|review|reject>",
  "key_factors": ["factor1", "factor2", "factor3"],
  "threshold_triggered": "one sentence: which specific Fannie Mae band(s) were triggered and their combined policy outcome"
}}"""

    text = call_llm(SYSTEM, prompt)
    result = parse_json_response(text)
    result["agent"] = "Credit Analyst"
    result["priority"] = PRIORITY
    result["priority_level"] = PRIORITY_LEVEL
    result["confidence"] = float(result.get("confidence", 0))
    return result
