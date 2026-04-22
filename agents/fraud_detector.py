from agents.base_agent import call_llm, parse_json_response

SYSTEM = (
    "You are a fraud detection specialist at a bank. "
    "You are the first agent in the underwriting pipeline and act as a hard stop. "
    "Identify inconsistencies, red flags, and potential fraud indicators in loan applications. "
    "Always respond with valid JSON only — no markdown, no commentary outside the JSON object."
)

PRIORITY = "Hard Stop"
PRIORITY_LEVEL = 0


def detect_fraud(data: dict) -> dict:
    flags = []
    if not (300 <= data["credit_score"] <= 850):
        flags.append(f"Credit score {data['credit_score']} is outside valid FICO range (300–850)")
    if data["annual_income"] > 0 and data["loan_amount"] / data["annual_income"] > 10:
        flags.append(
            f"Loan amount is {data['loan_amount'] / data['annual_income']:.1f}x annual income (>10x is anomalous)"
        )
    if data["employment_years"] < 0:
        flags.append("Negative employment years — data integrity issue")
    if data["existing_debt"] < 0:
        flags.append("Negative existing debt — data integrity issue")
    if data["annual_income"] < 0:
        flags.append("Negative annual income — data integrity issue")

    flags_str = (
        "\n".join(f"  - {f}" for f in flags) if flags else "  - None detected by automated pre-screening"
    )

    prompt = f"""You are the FRAUD HARD STOP — the first and most critical agent in the underwriting pipeline.
If fraud is detected, the entire application is rejected regardless of all other agent assessments.

Applicant: {data['name']}
Loan Amount: ${data['loan_amount']:,.2f}
Annual Income: ${data['annual_income']:,.2f}
Credit Score: {data['credit_score']}
Employment Years: {data['employment_years']}
Existing Debt: ${data['existing_debt']:,.2f}

Automated pre-screening flags:
{flags_str}

Analyze for: income inconsistencies, unusual loan-to-income patterns, suspicious data combinations,
data integrity violations, and statistical anomalies vs. typical applicant profiles.

In a production system this agent would call Plaid (income verification), Equifax (credit identity),
and Jumio (document/identity verification). Here you rely on internal consistency analysis only.

State the specific fraud indicator or integrity check that most influenced your assessment.

Respond with ONLY this JSON (no other text):
{{
  "analysis": "2-3 sentence fraud risk analysis noting the most significant finding",
  "confidence": <integer 0-100 where 100=no fraud indicators/safe to proceed, 0=strong fraud detected>,
  "recommendation": "<approve|review|reject>",
  "key_factors": ["factor1", "factor2", "factor3"],
  "threshold_triggered": "one sentence: which fraud indicator or integrity check was triggered, or 'No fraud indicators detected'"
}}"""

    text = call_llm(SYSTEM, prompt)
    result = parse_json_response(text)
    result["agent"] = "Fraud Detector"
    result["priority"] = PRIORITY
    result["priority_level"] = PRIORITY_LEVEL
    result["confidence"] = float(result.get("confidence", 0))
    return result
