from agents.base_agent import call_llm, parse_json_response

SYSTEM = (
    "You are a risk assessment specialist at a financial institution. "
    "Evaluate loan risk using the exact Fannie Mae thresholds for credit score, DTI ratio, "
    "employment history, and loan-to-income ratio. "
    "Always respond with valid JSON only — no markdown, no commentary outside the JSON object."
)


def _classify_credit(score: int) -> str:
    if score >= 720:
        return f"{score} — APPROVE (720+ Fannie Mae standard)"
    elif score >= 620:
        return f"{score} — REVIEW (620–719 below preferred minimum)"
    else:
        return f"{score} — REJECT (<620 below Fannie Mae absolute minimum)"


def _classify_dti(dti: float) -> str:
    if dti < 36.0:
        return f"{dti:.1f}% — APPROVE (<36%)"
    elif dti <= 43.0:
        return f"{dti:.1f}% — REVIEW (36–43%)"
    elif dti <= 50.0:
        return f"{dti:.1f}% — REJECT (>43%)"
    else:
        return f"{dti:.1f}% — HARD REJECT (>50%)"


def _classify_employment(years: float) -> str:
    if years >= 2.0:
        return f"{years} yrs — APPROVE (2+ years)"
    elif years >= 0.5:
        return f"{years} yrs — REVIEW (6 months to 2 years)"
    else:
        return f"{years} yrs — REJECT (<6 months)"


def _classify_lti(lti: float) -> str:
    if lti < 3.0:
        return f"{lti:.2f}x — APPROVE (<3x)"
    elif lti <= 5.0:
        return f"{lti:.2f}x — REVIEW (3–5x)"
    else:
        return f"{lti:.2f}x — REJECT (>5x)"


def assess_risk(data: dict) -> dict:
    monthly_income = data["annual_income"] / 12
    monthly_new_payment = (data["loan_amount"] / 60) * 1.0417   # 5% APR, 60 months
    monthly_existing = data["existing_debt"] * 0.02              # ~2% minimum payment
    total_monthly_debt = monthly_new_payment + monthly_existing

    # DTI = total monthly debt / gross monthly income (Fannie Mae back-end definition)
    dti = (total_monthly_debt / monthly_income * 100) if monthly_income > 0 else 100.0
    loan_to_income = data["loan_amount"] / data["annual_income"] if data["annual_income"] > 0 else 999

    credit_label  = _classify_credit(data["credit_score"])
    dti_label     = _classify_dti(dti)
    emp_label     = _classify_employment(data["employment_years"])
    lti_label     = _classify_lti(loan_to_income)

    prompt = f"""Assess the overall risk profile using the exact Fannie Mae thresholds for all four
underwriting dimensions. Each dimension must be evaluated independently; the most restrictive
outcome across all four drives the overall recommendation.

APPLICANT DATA
  Name:                     {data['name']}
  Loan Amount:              ${data['loan_amount']:,.2f}
  Annual Income:            ${data['annual_income']:,.2f}  |  Monthly Gross: ${monthly_income:,.2f}
  Credit Score:             {data['credit_score']}
  Employment Years:         {data['employment_years']}
  Existing Debt:            ${data['existing_debt']:,.2f}  |  Est. monthly: ${monthly_existing:,.2f}
  New Loan Est. Payment:    ${monthly_new_payment:,.2f}
  Total Monthly Debt:       ${total_monthly_debt:,.2f}

PRE-CLASSIFIED THRESHOLDS (state which triggered your decision):
  Credit Score:             {credit_label}
  DTI Ratio:                {dti_label}
  Employment:               {emp_label}
  Loan-to-Income:           {lti_label}

FANNIE MAE THRESHOLDS — ALL FOUR DIMENSIONS:

  1. CREDIT SCORE
     720+     → APPROVE  — Fannie Mae standard; lowest risk
     620–719  → REVIEW   — below preferred minimum; compensating factors required
     <620     → REJECT   — below Fannie Mae absolute minimum for conventional loans

  2. DTI RATIO  (total monthly debt ÷ gross monthly income)
     <36%     → APPROVE    — ideal repayment capacity
     36–43%   → REVIEW     — Fannie Mae conventional maximum; review required
     >43%     → REJECT     — exceeds Fannie Mae conventional limit
     >50%     → HARD REJECT — exceeds FHA absolute maximum

  3. EMPLOYMENT HISTORY
     2+ years       → APPROVE — meets Fannie Mae 2-year continuous employment standard
     6 mo–2 years   → REVIEW  — below preferred; employment letter required
     <6 months      → REJECT  — insufficient history; income continuity unestablished

  4. LOAN-TO-INCOME RATIO
     <3x  → APPROVE — within Fannie Mae comfort zone
     3–5x → REVIEW  — elevated; compensating factors required
     >5x  → REJECT  — exceeds Fannie Mae maximum

DECISION RULE: If ANY dimension triggers REJECT → overall is reject.
               If no REJECTs but ANY triggers REVIEW → overall is review.
               All four APPROVE → overall is approve.

In your analysis, name the exact computed value for each dimension (e.g. "DTI of 38.4% falls in the
36–43% REVIEW band"), state which threshold was crossed, and identify the single most limiting factor.

Respond with ONLY this JSON (no other text):
{{
  "analysis": "2-3 sentences explicitly naming the threshold triggered in each dimension and identifying the most limiting factor that drives the overall recommendation",
  "confidence": <integer 0-100 where 100=very safe to approve, 0=definitely reject>,
  "recommendation": "<approve|review|reject>",
  "key_factors": ["factor1", "factor2", "factor3"]
}}"""

    text = call_llm(SYSTEM, prompt)
    result = parse_json_response(text)
    result["agent"] = "Risk Assessor"
    result["confidence"] = float(result.get("confidence", 0))
    return result
