from agents.base_agent import call_llm, parse_json_response

SYSTEM = (
    "You are an employment verification specialist at a bank. "
    "Assess employment stability using exact Fannie Mae underwriting thresholds. "
    "Always respond with valid JSON only — no markdown, no commentary outside the JSON object."
)

PRIORITY = "Priority 3"
PRIORITY_LEVEL = 3

# Fannie Mae employment thresholds (in years; 6 months = 0.5 years)
def _classify_employment(years: float) -> tuple[str, str]:
    if years >= 2.0:
        return "approve", f"{years} years — APPROVE: Meets Fannie Mae 2-year continuous employment standard"
    elif years >= 0.5:
        return "review", f"{years} years — REVIEW: 6 months to 2 years; below Fannie Mae preferred standard; employment letter and pay stubs required"
    else:
        return "reject", f"{years} years — REJECT: Below 6-month minimum; insufficient employment history for income continuity"


def verify_employment(data: dict) -> dict:
    years = data["employment_years"]
    monthly_income = data["annual_income"] / 12

    emp_rec, emp_label = _classify_employment(years)

    prompt = f"""You are performing Priority 3 Employment Verification in a sequential bank underwriting pipeline.
Prior checks (Fraud Hard Stop, Priority 1 Credit, Priority 2 Income) have already been evaluated.

APPLICANT DATA
  Name:               {data['name']}
  Employment Duration:{years} years
  Annual Income:      ${data['annual_income']:,.2f}  |  Monthly: ${monthly_income:,.2f}
  Loan Requested:     ${data['loan_amount']:,.2f}
  Credit Score:       {data['credit_score']}

PRE-CLASSIFIED EMPLOYMENT THRESHOLD (Fannie Mae):
  {emp_label}

FANNIE MAE EMPLOYMENT THRESHOLDS:
  2+ years        → APPROVE — meets Fannie Mae 2-year continuous employment standard; income considered stable
  6 months–2 years→ REVIEW  — below preferred standard; require employer letter + 2 most recent pay stubs
  < 6 months      → REJECT  — insufficient employment history; no basis for income continuity

ADDITIONAL RISK FACTORS:
  Employment < 6 months with loan > $50,000: high-risk combination; note explicitly
  Employment 6 mo–2 yr with DTI > 36%: double risk factor; elevate to reject
  Self-employed applicants: require 2 years tax returns (flag as documentation gap)

In your analysis, state the exact employment duration (e.g. "1.5 years falls in the 6-month to 2-year
REVIEW band") and name the specific Fannie Mae threshold triggered. Do not round or paraphrase.

Respond with ONLY this JSON (no other text):
{{
  "analysis": "2-3 sentences citing the exact employment duration, which Fannie Mae threshold band it falls in, and the policy consequence",
  "confidence": <integer 0-100 where 100=very safe to approve, 0=definitely reject>,
  "recommendation": "<approve|review|reject>",
  "key_factors": ["factor1", "factor2", "factor3"],
  "threshold_triggered": "one sentence: which specific Fannie Mae employment threshold was triggered and what it means"
}}"""

    text = call_llm(SYSTEM, prompt)
    result = parse_json_response(text)
    result["agent"] = "Employment Verifier"
    result["priority"] = PRIORITY
    result["priority_level"] = PRIORITY_LEVEL
    result["confidence"] = float(result.get("confidence", 0))
    return result
