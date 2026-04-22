from agents.base_agent import call_llm

SYSTEM = (
    "You are a senior loan officer writing formal bank assessment reports. "
    "Your reports are reviewed by management and regulators — they must be professional, "
    "accurate, and structured. Write in formal banking language."
)

AGENT_KEYS = ["credit_analyst", "income_verifier", "risk_assessor", "fraud_detector", "debt_analyzer"]


def _threshold_status(data: dict) -> str:
    monthly_income = data["annual_income"] / 12
    monthly_new = (data["loan_amount"] / 60) * 1.0417
    monthly_existing = data["existing_debt"] * 0.02
    total_monthly_debt = monthly_new + monthly_existing
    dti = (total_monthly_debt / monthly_income * 100) if monthly_income > 0 else 100.0
    lti = data["loan_amount"] / data["annual_income"] if data["annual_income"] > 0 else 999.0

    def credit_band(s):
        if s >= 720: return f"{s} → APPROVE band (720+)"
        if s >= 620: return f"{s} → REVIEW band (620–719)"
        return f"{s} → REJECT band (<620)"

    def dti_band(d):
        if d < 36:   return f"{d:.1f}% → APPROVE (<36%)"
        if d <= 43:  return f"{d:.1f}% → REVIEW (36–43%)"
        if d <= 50:  return f"{d:.1f}% → REJECT (>43%)"
        return f"{d:.1f}% → HARD REJECT (>50%)"

    def emp_band(y):
        if y >= 2.0:  return f"{y} yrs → APPROVE (2+ years)"
        if y >= 0.5:  return f"{y} yrs → REVIEW (6 months–2 years)"
        return f"{y} yrs → REJECT (<6 months)"

    def lti_band(l):
        if l < 3.0:  return f"{l:.2f}x → APPROVE (<3x)"
        if l <= 5.0: return f"{l:.2f}x → REVIEW (3–5x)"
        return f"{l:.2f}x → REJECT (>5x)"

    return (
        f"  Credit Score:      {credit_band(data['credit_score'])}\n"
        f"  DTI Ratio:         {dti_band(dti)}\n"
        f"  Employment:        {emp_band(data['employment_years'])}\n"
        f"  Loan-to-Income:    {lti_band(lti)}"
    )


def write_report(data: dict, results: dict) -> dict:
    agent_sections = []
    for key in AGENT_KEYS:
        if key in results:
            r = results[key]
            factors = ", ".join(r.get("key_factors", []))
            threshold = r.get("threshold_triggered", "")
            threshold_line = f"\n  Threshold Triggered: {threshold}" if threshold else ""
            agent_sections.append(
                f"• {r.get('agent', key)}: {r.get('recommendation', 'N/A').upper()} "
                f"(confidence: {r.get('confidence', 0):.0f}%)\n"
                f"  Analysis: {r.get('analysis', 'N/A')}"
                f"{threshold_line}\n"
                f"  Key Factors: {factors}"
            )

    critic = results.get("critic", {})
    conf_breakdown = "  |  ".join(
        f"{k}: {v}%" for k, v in critic.get("individual_confidences", {}).items()
    )

    agents_block = "\n\n".join(agent_sections)

    consistency = results.get("consistency_checker", {})
    consistency_block = (
        f"Status: {consistency.get('status', 'N/A')}  |  "
        f"Score: {consistency.get('consistency_score', 'N/A')}/100  |  "
        f"Flags: {consistency.get('flag_count', 0)}\n"
        + "\n".join(f"  {f}" for f in consistency.get("flags", []))
    )

    threshold_block = _threshold_status(data)

    prompt = f"""Write a formal Loan Assessment Report for the following application.
The report must explicitly reference the Fannie Mae threshold triggered in each dimension.

═══════════════════════════════════════════
APPLICANT INFORMATION
═══════════════════════════════════════════
Name: {data['name']}
Loan Amount Requested: ${data['loan_amount']:,.2f}
Annual Income: ${data['annual_income']:,.2f}
Credit Score: {data['credit_score']}
Employment Duration: {data['employment_years']} years
Existing Debt: ${data['existing_debt']:,.2f}

═══════════════════════════════════════════
FANNIE MAE THRESHOLD OUTCOMES
═══════════════════════════════════════════
{threshold_block}

  Reference bands:
    Credit Score:   720+ approve | 620–719 review | <620 reject
    DTI:            <36% approve | 36–43% review  | >43% reject | >50% hard reject
    Employment:     2+ yr approve | 6 mo–2 yr review | <6 mo reject
    Loan-to-Income: <3x approve  | 3–5x review    | >5x reject

═══════════════════════════════════════════
PRE-ASSESSMENT CONSISTENCY CHECK (Agent 0)
═══════════════════════════════════════════
{consistency_block}

═══════════════════════════════════════════
MULTI-AGENT ANALYSIS RESULTS
═══════════════════════════════════════════
{agents_block}

═══════════════════════════════════════════
CRITIC DECISION SUMMARY
═══════════════════════════════════════════
Final Decision: {critic.get('decision', 'N/A')}
Average Confidence Score: {critic.get('average_confidence', 0):.1f}%
Individual Scores: {conf_breakdown}
Rationale: {critic.get('reason', 'N/A')}

Write a formal report with these five clearly labeled sections:
1. EXECUTIVE SUMMARY — include the final decision and the single most limiting Fannie Mae threshold
2. FINANCIAL PROFILE ANALYSIS — cite the exact computed value for each of the four Fannie Mae
   dimensions and name the specific threshold band triggered (e.g. "credit score of 685 falls in
   the 620–719 REVIEW band")
3. MULTI-AGENT RISK ASSESSMENT SUMMARY — summarise what each agent found and which threshold drove it
4. DECISION RATIONALE — explain how the Fannie Mae threshold outcomes combined to produce the final decision
5. RECOMMENDATIONS & CONDITIONS — list any conditions required to move from review to approve, or
   what would need to change for a rejected application to qualify

Each section should be 1-2 substantive paragraphs. Use formal banking language.
Reference specific Fannie Mae threshold values by number throughout (do not paraphrase them)."""

    report_text = call_llm(SYSTEM, prompt, max_tokens=2048)

    return {
        "agent": "Report Writer",
        "report": report_text,
    }
