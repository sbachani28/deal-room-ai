"""Analyzes uploaded deal documents using Claude with higher-ed M&A domain knowledge."""
import anthropic
import base64
import io

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


HIGHEREDD_DD_SYSTEM_PROMPT = """CRITICAL FORMATTING RULE: You must NEVER use the em dash character (-) in any response. Not once. Replace every em dash with a regular hyphen (-) or rewrite the sentence. This is non-negotiable.

You are a senior due diligence analyst at a boutique higher education M&A advisory firm.
You specialize in private nonprofit higher education mergers, acquisitions, and affiliations.

You have deep expertise in:
- Accreditation change-of-control requirements (HLC, SACSCOC, WSCUC, NECHE, MSCHE, NWCCU)
- Title IV Higher Education Act compliance and DOE change-of-control triggers
- Composite Financial Index (CFI) calculation and DOE financial responsibility standards
- Bond covenants and municipal bond structures common in higher ed
- Faculty shared governance and AAUP standards
- IPEDS financial metrics (instruction expense ratio, tuition dependency, endowment per FTE)
- NCAA compliance implications of affiliations
- State authorization reciprocity (SARA) requirements
- 90/10 rule for Title IV institutions
- HEA reauthorization implications

When analyzing documents, always:
1. Identify the specific document type (audit, accreditation letter, board minutes, bond indenture, etc.)
2. Extract deal-critical financial figures with exact values
3. Flag regulatory red flags immediately (accreditation probation, DOE monitoring, bond covenant violations)
4. Note anything that could affect timeline or close certainty
5. Be specific - quote exact numbers, dates, and language from the document

Formatting rule: never use em dashes in your response. Use a regular hyphen (-) or rewrite the sentence instead.

Format your response as structured JSON when asked to extract data."""


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes."""
    if PdfReader is None:
        return "[pypdf not installed — cannot extract PDF text]"
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for page in reader.pages[:30]:  # cap at 30 pages to stay within token limits
            pages.append(page.extract_text() or "")
        return "\n\n".join(pages)
    except Exception as e:
        return f"[PDF extraction error: {e}]"


def analyze_document(client: anthropic.Anthropic, doc_text: str, doc_name: str, analysis_type: str) -> str:
    """Run Claude analysis on a document for a specific DD category."""

    prompts = {
        "financial_health": f"""Analyze this document for financial health indicators relevant to an M&A transaction.

Document: {doc_name}

Extract and return as JSON:
{{
  "document_type": "...",
  "fiscal_year": "...",
  "total_revenues": <number or null>,
  "operating_expenses": <number or null>,
  "total_assets": <number or null>,
  "total_liabilities": <number or null>,
  "net_assets_without_donor_restrictions": <number or null>,
  "net_assets_with_donor_restrictions": <number or null>,
  "change_in_net_assets": <number or null>,
  "endowment_value": <number or null>,
  "debt_outstanding": <number or null>,
  "tuition_revenue": <number or null>,
  "key_findings": ["...", "..."],
  "red_flags": ["...", "..."],
  "auditor_opinion": "unmodified|qualified|adverse|disclaimer|unknown",
  "going_concern_noted": true/false
}}

Document text:
{doc_text[:12000]}""",

        "accreditation": f"""Analyze this document for accreditation-related information critical to an M&A transaction.

Document: {doc_name}

Extract as JSON:
{{
  "document_type": "...",
  "accrediting_body": "...",
  "current_status": "accredited|probation|show_cause|warning|candidate|not_found",
  "accreditation_expiry": "...",
  "sanctions_or_warnings": ["...", "..."],
  "change_of_control_mentioned": true/false,
  "required_actions": ["...", "..."],
  "program_accreditations": ["...", "..."],
  "key_findings": ["...", "..."],
  "red_flags": ["...", "..."]
}}

Document text:
{doc_text[:12000]}""",

        "governance": f"""Analyze this document for governance, faculty, and board-related M&A considerations.

Document: {doc_name}

Extract as JSON:
{{
  "document_type": "...",
  "board_approval_required": true/false,
  "faculty_senate_approval_required": true/false,
  "union_contracts_present": true/false,
  "union_details": "...",
  "shared_governance_requirements": ["...", "..."],
  "executive_employment_contracts": true/false,
  "severance_obligations": "...",
  "pending_litigation": ["...", "..."],
  "key_findings": ["...", "..."],
  "red_flags": ["...", "..."]
}}

Document text:
{doc_text[:12000]}""",

        "debt_bonds": f"""Analyze this document for debt structure and bond covenant information critical to M&A.

Document: {doc_name}

Extract as JSON:
{{
  "document_type": "...",
  "bond_issuer": "...",
  "principal_outstanding": <number or null>,
  "interest_rate": "...",
  "maturity_date": "...",
  "change_of_control_provision": true/false,
  "change_of_control_language": "...",
  "financial_covenants": ["...", "..."],
  "covenant_compliance_status": "compliant|breach|waiver|unknown",
  "debt_service_coverage_ratio": <number or null>,
  "days_cash_on_hand_covenant": <number or null>,
  "trustee": "...",
  "key_findings": ["...", "..."],
  "red_flags": ["...", "..."]
}}

Document text:
{doc_text[:12000]}""",

        "general": f"""Analyze this document for any information relevant to a higher education M&A transaction.

Document: {doc_name}

Provide:
1. Document type and summary (2-3 sentences)
2. Key financial figures (if any)
3. Regulatory or compliance issues
4. Deal risk factors
5. Questions this document raises

Be specific and quote from the document. Flag anything that could affect deal timeline, structure, or price.

Document text:
{doc_text[:12000]}""",
    }

    prompt = prompts.get(analysis_type, prompts["general"])

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2000,
        thinking={"type": "adaptive"},
        system=HIGHEREDD_DD_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    text = next((b.text for b in response.content if b.type == "text"), "")
    return text.replace("—", "-").replace("–", "-")


def generate_dd_memo(client: anthropic.Anthropic, all_analyses: list[dict], institution_name: str) -> str:
    """Generate a final due diligence memo synthesizing all document analyses."""

    analyses_text = "\n\n---\n\n".join(
        f"Document: {a['name']}\nAnalysis Type: {a['type']}\n\nFindings:\n{a['result']}"
        for a in all_analyses
    )

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4000,
        thinking={"type": "adaptive"},
        system=HIGHEREDD_DD_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"""Based on the following document analyses for {institution_name}, generate a comprehensive Due Diligence Summary Memo.

Structure the memo as:

## EXECUTIVE SUMMARY
2-3 paragraph overview of deal-readiness and primary concerns.

## FINANCIAL HEALTH (RED / YELLOW / GREEN)
CFI implications, revenue trends, endowment adequacy, debt burden.

## ACCREDITATION & REGULATORY (RED / YELLOW / GREEN)
Accreditor status, change-of-control timeline, Title IV risk, DOE considerations.

## DEBT & BOND COVENANTS (RED / YELLOW / GREEN)
Outstanding debt, change-of-control triggers, covenant compliance.

## GOVERNANCE & LEGAL (RED / YELLOW / GREEN)
Board approval, faculty governance, litigation, employment contracts.

## OPEN ITEMS
List of documents not yet received or questions requiring follow-up.

## DEAL RISK MATRIX
For each major risk: Risk | Severity (High/Med/Low) | Mitigation | Who Owns It

Use specific numbers and quotes wherever the documents support them.

---

DOCUMENT ANALYSES:

{analyses_text[:20000]}""",
            }
        ],
    )

    text = next((b.text for b in response.content if b.type == "text"), "")
    return text.replace("—", "-").replace("–", "-")


def answer_question(client: anthropic.Anthropic, question: str, context: str) -> str:
    """Answer a specific question about the deal using loaded document context."""
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1500,
        thinking={"type": "adaptive"},
        system=HIGHEREDD_DD_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"""Based on the following deal documents, answer this question:

QUESTION: {question}

DOCUMENT CONTEXT:
{context[:15000]}

Be specific. Quote directly from documents when possible. If the documents don't contain enough information to answer definitively, say so and explain what additional documents would be needed.""",
            }
        ],
    )
    text = next((b.text for b in response.content if b.type == "text"), "")
    return text.replace("—", "-").replace("–", "-")
