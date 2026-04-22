from agents.base_agent import call_llm, parse_json_response

SYSTEM = (
    "You are an income verification specialist at a bank. "
    "Assess income sustainability and repayment capacity using Fannie Mae DTI guidelines. "
    "Always respond with valid JSON only — no markdown, no commentary outside the JSON object."
)

# Fannie Mae DTI thresholds — applied in Python and mirrored in the prompt
def _classify_dti(dti: float) -> tuple[str, str]:
    if dti < 36.0:
        return "approve", f"{dti:.1f}% — APPROVE: Below 36% Fannie Mae ideal threshold"
    elif dti <= 43.0:
        return "review", f"{dti:.1f}% — REVIEW: 36–43% range; meets Fannie Mae conventional maximum with review"
    elif dti <= 50.0:
        return "reject", f"{dti:.1f}% — REJECT: Above 43% Fannie Mae conventional limit"
    else:
        return "reject", f"{dti:.1f}% — HARD REJECT: Above 50%; exceeds FHA absolute maximum; no standard product available"


def verify_income(data: dict) -> dict:
    monthly_income = data["annual_income"] / 12
    # Estimated monthly payment: 5% APR, 60-month term
    monthly_new_payment = (data["loan_amount"] / 60) * 1.0417
    # Existing debt monthly obligation: ~2% of balance (standard minimum payment estimate)
    monthly_existing = data["existing_debt"] * 0.02
    # Total monthly debt post-approval = existing obligations + new loan payment
    total_monthly_debt = monthly_new_payment + monthly_existing

    # DTI = total monthly debt / gross monthly income (Fannie Mae back-end definition)
    dti = (total_monthly_debt / monthly_income * 100) if monthly_income > 0 else 100.0

    dti_rec, dti_label = _classify_dti(dti)

    prompt = f"""Verify and assess income sustainability for this loan application using Fannie Mae DTI guidelines.

APPLICANT DATA
  Name:                    {data['name']}
  Annual Income:           ${data['annual_income']:,.2f}  |  Monthly Gross: ${monthly_income:,.2f}
  Requested Loan:          ${data['loan_amount']:,.2f}
  Est. Monthly New Payment (5% APR, 60 mo): ${monthly_new_payment:,.2f}
  Est. Monthly Existing Debt Service (~2%): ${monthly_existing:,.2f}
  Total Monthly Debt Post-Approval:         ${total_monthly_debt:,.2f}
  Employment Duration:     {data['employment_years']} years

DTI CALCULATION (total monthly debt ÷ gross monthly income):
  {total_monthly_debt:,.2f} ÷ {monthly_income:,.2f} = {dti:.1f}%
  Pre-classified result: {dti_label}

FANNIE MAE DTI THRESHOLDS:
  < 36%   → APPROVE    — ideal repayment capacity; well within Fannie Mae guidelines
  36–43%  → REVIEW     — acceptable; meets Fannie Mae conventional loan maximum (review required)
  > 43%   → REJECT     — exceeds Fannie Mae conventional maximum; decline standard product
  > 50%   → HARD REJECT — exceeds FHA absolute maximum; no standard product available

In your analysis, state the exact computed DTI percentage (e.g. "DTI of 38.4% falls in the 36–43%
REVIEW band") and name the specific Fannie Mae threshold that was crossed. Do not round or paraphrase.

Respond with ONLY this JSON (no other text):
{{
  "analysis": "2-3 sentences citing the exact DTI percentage, which Fannie Mae threshold band it falls in, and the policy consequence",
  "confidence": <integer 0-100 where 100=very safe to approve, 0=definitely reject>,
  "recommendation": "<approve|review|reject>",
  "key_factors": ["factor1", "factor2", "factor3"]
}}"""

    text = call_llm(SYSTEM, prompt)
    result = parse_json_response(text)
    result["agent"] = "Income Verifier"
    result["confidence"] = float(result.get("confidence", 0))
    return result
