from agents.base_agent import call_llm, parse_json_response

SYSTEM = (
    "You are a debt sustainability specialist at a bank. "
    "Synthesize findings from multiple analysts and provide a holistic debt sustainability assessment "
    "anchored to Fannie Mae underwriting thresholds. "
    "Always respond with valid JSON only — no markdown, no commentary outside the JSON object."
)


def analyze_debt(data: dict, parallel_results: dict) -> dict:
    monthly_income = data["annual_income"] / 12
    monthly_existing = data["existing_debt"] * 0.02          # ~2% of balance
    monthly_new = (data["loan_amount"] / 60) * 1.0417        # 5% APR, 60 months
    total_monthly_debt = monthly_existing + monthly_new
    disposable = monthly_income - total_monthly_debt
    dscr = monthly_income / total_monthly_debt if total_monthly_debt > 0 else 99.0

    # Recompute all four Fannie Mae dimensions for synthesis context
    dti = (total_monthly_debt / monthly_income * 100) if monthly_income > 0 else 100.0
    lti = data["loan_amount"] / data["annual_income"] if data["annual_income"] > 0 else 999.0

    def credit_band(s):
        if s >= 720: return f"{s} — APPROVE band (720+)"
        if s >= 620: return f"{s} — REVIEW band (620–719)"
        return f"{s} — REJECT band (<620)"

    def dti_band(d):
        if d < 36:   return f"{d:.1f}% — APPROVE (<36%)"
        if d <= 43:  return f"{d:.1f}% — REVIEW (36–43%)"
        if d <= 50:  return f"{d:.1f}% — REJECT (>43%)"
        return f"{d:.1f}% — HARD REJECT (>50%)"

    def emp_band(y):
        if y >= 2.0:  return f"{y} yrs — APPROVE (2+)"
        if y >= 0.5:  return f"{y} yrs — REVIEW (6 mo–2 yr)"
        return f"{y} yrs — REJECT (<6 mo)"

    def lti_band(l):
        if l < 3.0:  return f"{l:.2f}x — APPROVE (<3x)"
        if l <= 5.0: return f"{l:.2f}x — REVIEW (3–5x)"
        return f"{l:.2f}x — REJECT (>5x)"

    agent_summary_lines = []
    for key in ["credit_analyst", "income_verifier", "risk_assessor", "fraud_detector"]:
        if key in parallel_results:
            r = parallel_results[key]
            agent_summary_lines.append(
                f"  {r.get('agent', key)}: {r.get('recommendation', 'N/A').upper()} "
                f"(confidence {r.get('confidence', 0):.0f}%)"
            )
    agent_summary = "\n".join(agent_summary_lines) or "  No prior assessments available"

    prompt = f"""Perform comprehensive debt sustainability analysis, synthesizing all prior agent assessments.
Your role is to evaluate whether the combined debt picture is sustainable given the Fannie Mae thresholds
already triggered, and to deliver a holistic verdict.

APPLICANT DATA
  Name:                           {data['name']}
  Annual Income:                  ${data['annual_income']:,.2f}  |  Monthly: ${monthly_income:,.2f}
  Existing Debt:                  ${data['existing_debt']:,.2f}  |  Est. monthly: ${monthly_existing:,.2f}
  New Loan:                       ${data['loan_amount']:,.2f}    |  Est. monthly: ${monthly_new:,.2f}
  Total Monthly Debt Service:     ${total_monthly_debt:,.2f}
  Est. Monthly Disposable Income: ${disposable:,.2f}
  Debt Service Coverage Ratio:    {dscr:.2f}x  (>1.25 healthy, <1.0 critical)
  Credit Score:                   {data['credit_score']}
  Employment Years:               {data['employment_years']}

FANNIE MAE THRESHOLD STATUS (all four dimensions):
  Credit Score:      {credit_band(data['credit_score'])}
  DTI Ratio:         {dti_band(dti)}
  Employment:        {emp_band(data['employment_years'])}
  Loan-to-Income:    {lti_band(lti)}

PRIOR AGENT RESULTS:
{agent_summary}

FANNIE MAE THRESHOLDS — REFERENCE:
  Credit Score:  720+ approve | 620–719 review | <620 reject
  DTI:           <36% approve | 36–43% review  | >43% reject | >50% hard reject
  Employment:    2+ yr approve | 6 mo–2 yr review | <6 mo reject
  Loan-to-Income:<3x approve  | 3–5x review    | >5x reject

Your synthesis should:
1. Confirm or challenge the individual agents based on the holistic debt picture
2. State which of the four Fannie Mae dimensions is the binding constraint (if any)
3. Assess whether DSCR and disposable income support or contradict the threshold outcomes

Respond with ONLY this JSON (no other text):
{{
  "analysis": "2-3 sentences identifying the binding Fannie Mae constraint, confirming or challenging prior agent findings, and stating whether DSCR supports the recommendation",
  "confidence": <integer 0-100 where 100=very safe to approve, 0=definitely reject>,
  "recommendation": "<approve|review|reject>",
  "key_factors": ["factor1", "factor2", "factor3"]
}}"""

    text = call_llm(SYSTEM, prompt)
    result = parse_json_response(text)
    result["agent"] = "Debt Analyzer"
    result["confidence"] = float(result.get("confidence", 0))
    return result
