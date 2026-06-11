"""
Deal Room AI - Higher Education M&A Due Diligence Engine
Prager Partners Internship Demo
"""
import json
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv

load_dotenv()

import anthropic
import plotly.graph_objects as go

from src.cfi_calculator import calculate_cfi
from src.document_analyzer import (
    analyze_document,
    answer_question,
    extract_text_from_pdf,
    generate_dd_memo,
)
from src.public_data import ACCREDITOR_CHANGE_OF_CONTROL, fetch_990_data, fetch_ipeds_data

st.set_page_config(
    page_title="Deal Room AI - Higher Ed M&A",
    page_icon="üéì",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.risk-red { background-color: #fee2e2; border-left: 4px solid #ef4444; padding: 12px; border-radius: 4px; margin: 8px 0; color: #1a202c; }
.risk-yellow { background-color: #fef9c3; border-left: 4px solid #eab308; padding: 12px; border-radius: 4px; margin: 8px 0; color: #1a202c; }
.risk-green { background-color: #dcfce7; border-left: 4px solid #22c55e; padding: 12px; border-radius: 4px; margin: 8px 0; color: #1a202c; }
.metric-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 8px 0; color: #1a202c; }
.section-header { font-size: 1.1em; font-weight: 700; color: #1e293b; margin-top: 16px; }
</style>
""", unsafe_allow_html=True)


def get_client() -> anthropic.Anthropic | None:
    api_key = os.getenv("ANTHROPIC_API_KEY") or st.session_state.get("api_key", "")
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


def render_cfi_gauge(cfi_score: float):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=cfi_score,
        title={"text": "Composite Financial Index (CFI)", "font": {"size": 16}},
        number={"font": {"size": 36}},
        gauge={
            "axis": {"range": [-4, 10], "tickwidth": 1},
            "bar": {"color": "#3b82f6"},
            "steps": [
                {"range": [-4, 1.0], "color": "#fee2e2"},
                {"range": [1.0, 1.5], "color": "#fef9c3"},
                {"range": [1.5, 10], "color": "#dcfce7"},
            ],
            "threshold": {
                "line": {"color": "red", "width": 4},
                "thickness": 0.75,
                "value": 1.5,
            },
        },
    ))
    fig.update_layout(height=280, margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)


# ‚îÄ‚îÄ Sidebar ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ

with st.sidebar:
    import os
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    if os.path.exists(logo_path):
        st.image(logo_path, width=160)
    else:
        st.markdown("### Deal Room AI")
    st.markdown("### Higher Ed M&A Due Diligence Engine")
    st.caption("Built for Prager Partners - private nonprofit higher education advisory")
    st.divider()

    st.markdown("**Deal:**")
    deal_name = st.text_input("Deal Name", placeholder="e.g., Woodbury √ó Redlands")

    st.markdown("**Institutions:**")
    target_name = st.text_input("Target Institution", placeholder="e.g., Woodbury University")
    acquirer_name = st.text_input("Acquirer Institution", placeholder="e.g., University of Redlands")

    st.divider()
    tab_options = ["Public Data", "Document Analysis", "CFI Calculator", "Q&A", "DD Memo"]
    selected_tab = st.radio("Navigate", tab_options)


# ‚îÄ‚îÄ Initialize session state ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ

if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = []
if "analyses" not in st.session_state:
    st.session_state.analyses = []
if "dd_memo" not in st.session_state:
    st.session_state.dd_memo = ""


# ‚îÄ‚îÄ Main content ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ

st.title(f"Deal Room AI{' - ' + deal_name if deal_name else ''}")

client = get_client()
if not client and selected_tab not in ["Public Data", "CFI Calculator"]:
    st.warning("Enter your Anthropic API key in the sidebar to use AI features.")


# ‚îÄ‚îÄ TAB 1: Public Data ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ

if selected_tab == "Public Data":
    st.header("Public Data Intelligence")
    st.caption("Auto-fetches IRS 990 data (ProPublica) and IPEDS enrollment/sector data for both institutions")

    col1, col2 = st.columns(2)

    for col, inst_name, label in [(col1, target_name, "Target"), (col2, acquirer_name, "Acquirer")]:
        with col:
            st.subheader(f"{label}: {inst_name or '-'}")
            if not inst_name:
                st.info("Enter institution name in sidebar")
                continue

            if st.button(f"Fetch Public Data - {label}", key=f"fetch_{label}"):
                with st.spinner("Fetching IRS 990 data..."):
                    data_990 = fetch_990_data(inst_name)
                with st.spinner("Fetching IPEDS data..."):
                    ipeds = fetch_ipeds_data(inst_name)

                st.session_state[f"{label}_990"] = data_990
                st.session_state[f"{label}_ipeds"] = ipeds

            if f"{label}_990" in st.session_state:
                d = st.session_state[f"{label}_990"]
                if "error" in d:
                    st.error(f"990 fetch: {d['error']}")
                else:
                    st.markdown(f"**EIN:** {d.get('ein')} | **State:** {d.get('state')}")
                    filings = [f for f in d.get("latest_filings", []) if any(v is not None for v in [f.get("total_revenue"), f.get("total_assets")])]
                    if filings:
                        latest_yr = filings[0].get("year", "?")
                        st.caption(f"Most recent IRS 990 filing available: FY{latest_yr}. Nonprofit filings typically lag 12-18 months behind fiscal year end - this is the latest public data on record.")
                        st.markdown("**Recent 990 Financials (000s omitted if shown):**")
                        for f in filings:
                            rev = f.get("total_revenue")
                            exp = f.get("total_expenses")
                            assets = f.get("total_assets")
                            net = f.get("net_assets")
                            yr = f.get("year", "?")
                            st.markdown(f"""
<div class="metric-card">
<b>FY {yr}</b><br>
Revenue: ${f"{rev:,.0f}" if rev is not None else "N/A"} &nbsp;|&nbsp; Expenses: ${f"{exp:,.0f}" if exp is not None else "N/A"}<br>
Total Assets: ${f"{assets:,.0f}" if assets is not None else "N/A"} &nbsp;|&nbsp; Net Assets: ${f"{net:,.0f}" if net is not None else "N/A"}
</div>
""", unsafe_allow_html=True)
                    else:
                        st.warning(f"WARNING: ProPublica found this org (EIN: {d.get('ein')}) but has no financial filing data on record. Try searching by the institution's full legal name, or check [ProPublica Nonprofit Explorer](https://projects.propublica.org/nonprofits/) directly.")

            if f"{label}_ipeds" in st.session_state:
                ip = st.session_state[f"{label}_ipeds"]
                if "error" not in ip:
                    sector_map = {1: "Public 4yr", 2: "Private Nonprofit 4yr", 3: "Private For-Profit 4yr",
                                  4: "Public 2yr", 5: "Private Nonprofit 2yr", 6: "Private For-Profit 2yr"}
                    control_map = {1: "Public", 2: "Private Nonprofit", 3: "Private For-Profit"}
                    st.markdown(f"""
**IPEDS Profile:**
- Sector: {sector_map.get(ip.get('sector'), ip.get('sector', '?'))}
- Control: {control_map.get(ip.get('control'), ip.get('control', '?'))}
- HBCU: {'Yes' if ip.get('hbcu') else 'No'} | Tribal: {'Yes' if ip.get('tribal') else 'No'}
- Accreditor: {ip.get('accreditor', 'Unknown')}
""")
                    enroll = ip.get("enrollment", {})
                    if enroll.get("total_enrollment"):
                        st.metric("Total Enrollment (IPEDS)", f"{enroll['total_enrollment']:,}")

    # ‚îÄ‚îÄ Auto Accreditation Analysis ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ
    st.divider()
    st.subheader("Accreditation Change-of-Control - Deal Analysis")

    def get_accreditor_for_state(state_code):
        """Return the accreditor key for a given US state code."""
        for key, info in ACCREDITOR_CHANGE_OF_CONTROL.items():
            if state_code and state_code.upper() in [s.upper() for s in info["states"]]:
                return key
        return None

    target_data = st.session_state.get("target_990") or st.session_state.get("target_ipeds")
    acquirer_data = st.session_state.get("acquirer_990") or st.session_state.get("acquirer_ipeds")

    target_state = None
    acquirer_state = None

    if "Target_990" in st.session_state and "error" not in st.session_state["Target_990"]:
        target_state = st.session_state["Target_990"].get("state")
    elif "Target_ipeds" in st.session_state and "error" not in st.session_state["Target_ipeds"]:
        target_state = st.session_state["Target_ipeds"].get("state")

    if "Acquirer_990" in st.session_state and "error" not in st.session_state["Acquirer_990"]:
        acquirer_state = st.session_state["Acquirer_990"].get("state")
    elif "Acquirer_ipeds" in st.session_state and "error" not in st.session_state["Acquirer_ipeds"]:
        acquirer_state = st.session_state["Acquirer_ipeds"].get("state")

    if target_state or acquirer_state:
        target_acc_key = get_accreditor_for_state(target_state) if target_state else None
        acquirer_acc_key = get_accreditor_for_state(acquirer_state) if acquirer_state else None

        col1, col2 = st.columns(2)
        for col, label, acc_key, state in [
            (col1, "Target", target_acc_key, target_state),
            (col2, "Acquirer", acquirer_acc_key, acquirer_state),
        ]:
            with col:
                st.markdown(f"**{label} ({state or '?'})**")
                if acc_key:
                    acc = ACCREDITOR_CHANGE_OF_CONTROL[acc_key]
                    st.markdown(f"""
<div class="risk-yellow" style="color:#1a202c;">
<b>{acc['name']} ({acc_key})</b><br><br>
<b>Notice:</b> {acc['notice_required']}<br>
<b>Timeline:</b> {acc['timeline']}<br>
<b>Key Requirement:</b> {acc['notes']}
</div>
""", unsafe_allow_html=True)
                else:
                    st.info(f"State '{state}' not matched to a known regional accreditor.")

        # Cross-accreditor warning
        if target_acc_key and acquirer_acc_key and target_acc_key != acquirer_acc_key:
            t = ACCREDITOR_CHANGE_OF_CONTROL[target_acc_key]
            a = ACCREDITOR_CHANGE_OF_CONTROL[acquirer_acc_key]
            st.markdown(f"""
<div class="risk-red" style="margin-top:16px;">
<b>Cross-Accreditor Deal Detected</b><br>
Target ({target_acc_key}) and Acquirer ({acquirer_acc_key}) fall under <b>different regional accreditors</b>.
Both bodies must separately approve the change of control.<br><br>
<b>Combined worst-case timeline: {t['timeline']} + {a['timeline']}</b><br>
Plan for the longer of the two and file with both simultaneously at LOI.
</div>
""", unsafe_allow_html=True)
        elif target_acc_key and acquirer_acc_key and target_acc_key == acquirer_acc_key:
            acc = ACCREDITOR_CHANGE_OF_CONTROL[target_acc_key]
            st.markdown(f"""
<div class="risk-green" style="margin-top:16px; color:#1a202c;">
<b>Same Accreditor ({target_acc_key})</b> - Single approval process required.<br>
Expected timeline: <b>{acc['timeline']}</b>
</div>
""", unsafe_allow_html=True)
    else:
        st.info("Fetch public data for both institutions above to auto-generate the accreditation deal analysis.")


# ‚îÄ‚îÄ TAB 2: Document Analysis ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ

elif selected_tab == "Document Analysis":
    st.header("Document Analysis")
    st.caption("AI-powered higher-ed M&A due diligence analysis - from public data or uploaded documents")

    if not client:
        st.stop()

    # ‚îÄ‚îÄ Auto-generate from public data ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ
    has_public_data = any(k in st.session_state for k in ["Target_990", "Acquirer_990", "Target_ipeds", "Acquirer_ipeds"])

    if has_public_data:
        st.subheader("Generate Analysis from Public Data")
        st.caption("Uses the 990 and IPEDS data already fetched - no document upload needed")

        def build_public_data_text(label):
            lines = [f"=== {label} Institution ==="]
            d990 = st.session_state.get(f"{label}_990", {})
            if d990 and "error" not in d990:
                lines.append(f"Name: {d990.get('name')}")
                lines.append(f"EIN: {d990.get('ein')} | State: {d990.get('state')}")
                filings = [f for f in d990.get("latest_filings", []) if f.get("total_revenue") or f.get("total_assets")]
                for f in filings:
                    lines.append(f"FY {f.get('year')}: Revenue=${f.get('total_revenue'):,} | Expenses=${f.get('total_expenses'):,} | Assets=${f.get('total_assets'):,} | Net Assets=${f.get('net_assets') or 'N/A'}")
            ipeds = st.session_state.get(f"{label}_ipeds", {})
            if ipeds and "error" not in ipeds:
                sector_map = {1: "Public 4yr", 2: "Private Nonprofit 4yr", 3: "Private For-Profit 4yr", 4: "Public 2yr", 5: "Private Nonprofit 2yr", 6: "Private For-Profit 2yr"}
                lines.append(f"Sector: {sector_map.get(ipeds.get('sector'), 'Unknown')}")
                lines.append(f"Accreditor: {ipeds.get('accreditor', 'Unknown')}")
                lines.append(f"HBCU: {'Yes' if ipeds.get('hbcu') else 'No'} | Tribal: {'Yes' if ipeds.get('tribal') else 'No'}")
                enroll = ipeds.get("enrollment", {})
                if enroll.get("total_enrollment"):
                    lines.append(f"Enrollment: {enroll['total_enrollment']:,}")
            return "\n".join(lines)

        auto_analysis_focus = st.selectbox(
            "Analysis Focus",
            ["financial_health", "accreditation", "general"],
            format_func=lambda x: {
                "financial_health": "Financial Health & CFI Risk",
                "accreditation": "Accreditation & Regulatory Risk",
                "general": "Full Deal Overview",
            }[x],
            key="auto_focus"
        )

        if st.button("Generate Analysis from Public Data", type="primary"):
            target_text = build_public_data_text("Target")
            acquirer_text = build_public_data_text("Acquirer")
            combined = f"{target_text}\n\n{acquirer_text}"

            with st.spinner("Claude is analyzing both institutions..."):
                result = analyze_document(client, combined, f"{target_name} x {acquirer_name} - Public Data", auto_analysis_focus)
                st.session_state.analyses.append({
                    "name": f"Public Data: {target_name or 'Target'} x {acquirer_name or 'Acquirer'}",
                    "type": auto_analysis_focus,
                    "text": combined[:3000],
                    "result": result,
                })
            st.success("Analysis complete - see results below")
            st.rerun()

    st.divider()
    st.subheader("Or Upload Deal Documents")
    st.caption("Audited financials, accreditation letters, board minutes, bond indentures, etc.")

    uploaded_files = st.file_uploader(
        "Upload Deal Documents (PDFs)",
        type=["pdf", "txt"],
        accept_multiple_files=True,
    )

    analysis_type = st.selectbox(
        "Analysis Focus",
        ["general", "financial_health", "accreditation", "governance", "debt_bonds"],
        format_func=lambda x: {
            "general": "General - All M&A Considerations",
            "financial_health": "Financial Health - Extract Key Metrics",
            "accreditation": "Accreditation & Regulatory",
            "governance": "Governance, Faculty & Legal",
            "debt_bonds": "Debt Structure & Bond Covenants",
        }[x],
    )

    if uploaded_files and st.button("Analyze Documents", type="primary"):
        for f in uploaded_files:
            with st.spinner(f"Analyzing {f.name}..."):
                raw = f.read()
                if f.name.endswith(".pdf"):
                    text = extract_text_from_pdf(raw)
                else:
                    text = raw.decode("utf-8", errors="replace")

                result = analyze_document(client, text, f.name, analysis_type)

                st.session_state.analyses.append({
                    "name": f.name,
                    "type": analysis_type,
                    "text": text[:3000],
                    "result": result,
                })

    if st.session_state.analyses:
        st.subheader("Analysis Results")
        for i, a in enumerate(st.session_state.analyses):
            with st.expander(f"üìÑ {a['name']} - {a['type']}", expanded=(i == len(st.session_state.analyses) - 1)):
                result_text = a["result"]
                # Try to parse as JSON for pretty display
                try:
                    parsed = json.loads(result_text[result_text.find("{"):result_text.rfind("}") + 1])
                    red_flags = parsed.get("red_flags", [])
                    key_findings = parsed.get("key_findings", [])

                    if red_flags:
                        st.markdown('<div class="risk-red"><b>Red Flags</b><br>' + "<br>".join(f"‚Ä¢ {r}" for r in red_flags) + "</div>", unsafe_allow_html=True)
                    if key_findings:
                        st.markdown('<div class="risk-green"><b>Key Findings</b><br>' + "<br>".join(f"‚Ä¢ {r}" for r in key_findings) + "</div>", unsafe_allow_html=True)

                    # Show remaining fields
                    skip = {"red_flags", "key_findings"}
                    for k, v in parsed.items():
                        if k not in skip and v not in (None, "", [], {}):
                            st.markdown(f"**{k.replace('_', ' ').title()}:** {v}")
                except Exception:
                    st.markdown(result_text)

        if st.button("Clear All Analyses"):
            st.session_state.analyses = []
            st.rerun()


# ‚îÄ‚îÄ TAB 3: CFI Calculator ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ

elif selected_tab == "CFI Calculator":
    st.header("Composite Financial Index (CFI) Calculator")
    st.caption("DOE's primary tool for assessing financial health. Scores below 1.5 trigger enhanced oversight.")

    # Auto-fill from fetched 990 data - consensus across up to 5 years
    def get_990_consensus(label):
        key = f"{label}_990"
        if key not in st.session_state:
            return None, []
        d = st.session_state[key]
        filings = [f for f in d.get("latest_filings", []) if f.get("total_revenue") or f.get("total_assets")]
        if not filings:
            return None, []

        def avg(field):
            vals = [float(f.get(field)) for f in filings if f.get(field) is not None]
            return sum(vals) / len(vals) if vals else 0.0

        years = [str(f.get("year", "?")) for f in filings]
        consensus = {
            "total_revenue": avg("total_revenue"),
            "total_expenses": avg("total_expenses"),
            "total_assets": avg("total_assets"),
            "total_liabilities": avg("total_liabilities"),
            "net_assets": avg("net_assets"),
            "years": years,
        }
        return consensus, filings

    autofill_options = {}
    autofill_raw = {}
    for label in ["Target", "Acquirer"]:
        consensus, filings = get_990_consensus(label)
        if consensus:
            inst_name = st.session_state.get(f"{label}_990", {}).get("name", label)
            years_str = ", ".join(consensus["years"])
            key = f"{label} - {inst_name} ({len(filings)}-yr avg: {years_str})"
            autofill_options[key] = consensus
            autofill_raw[key] = filings

    cfi_defaults = {
        "rev": 50_000_000.0, "exp": 52_000_000.0, "assets": 80_000_000.0,
        "liab": 35_000_000.0, "una": 15_000_000.0, "rna": 30_000_000.0, "change_na": -2_000_000.0
    }

    if autofill_options:
        selected_autofill = st.selectbox("Auto-fill from fetched institution:", ["- Manual Entry -"] + list(autofill_options.keys()))
        if selected_autofill != "- Manual Entry -":
            c = autofill_options[selected_autofill]
            filings = autofill_raw[selected_autofill]
            cfi_defaults["rev"] = c["total_revenue"]
            cfi_defaults["exp"] = c["total_expenses"]
            cfi_defaults["assets"] = c["total_assets"]
            cfi_defaults["liab"] = c["total_liabilities"]
            net = c["net_assets"]
            cfi_defaults["una"] = net * 0.6
            cfi_defaults["rna"] = net * 0.4
            cfi_defaults["change_na"] = c["total_revenue"] - c["total_expenses"]

            # Show year-by-year trend
            with st.expander(f"Year-by-Year Trend ({len(filings)} filings)", expanded=False):
                trend_data = {"Year": [], "Revenue ($M)": [], "Expenses ($M)": [], "Net Assets ($M)": []}
                for f in sorted(filings, key=lambda x: x.get("year", 0)):
                    trend_data["Year"].append(str(f.get("year", "?")))
                    trend_data["Revenue ($M)"].append(round((f.get("total_revenue") or 0) / 1_000_000, 1))
                    trend_data["Expenses ($M)"].append(round((f.get("total_expenses") or 0) / 1_000_000, 1))
                    trend_data["Net Assets ($M)"].append(round((f.get("net_assets") or 0) / 1_000_000, 1))

                # Add average row
                rev_vals = trend_data["Revenue ($M)"][:]
                exp_vals = trend_data["Expenses ($M)"][:]
                net_vals = trend_data["Net Assets ($M)"][:]
                trend_data["Year"].append("AVG (used for CFI)")
                trend_data["Revenue ($M)"].append(round(sum(rev_vals) / len(rev_vals), 1))
                trend_data["Expenses ($M)"].append(round(sum(exp_vals) / len(exp_vals), 1))
                trend_data["Net Assets ($M)"].append(round(sum(net_vals) / len(net_vals), 1))

                st.dataframe(trend_data, use_container_width=True)

                # Show the 60/40 split being applied
                avg_net = c["net_assets"]
                st.markdown(f"""
<div class="metric-card" style="font-size:0.9em;">
<b>Net Assets Split Applied to CFI Inputs</b><br>
Avg Net Assets: <b>${avg_net/1_000_000:.1f}M</b><br>
Unrestricted (60%): <b>${avg_net*0.6/1_000_000:.1f}M</b> - used as Net Assets w/o Donor Restrictions<br>
Restricted (40%): <b>${avg_net*0.4/1_000_000:.1f}M</b> - used as Net Assets w/ Donor Restrictions<br>
<span style="color:#6b7280;font-size:0.85em;">Note: Upload audited financials for exact restricted/unrestricted split.</span>
</div>
""", unsafe_allow_html=True)

            st.info(f"Fields pre-filled using {len(filings)}-year average from IRS 990 data. Net assets split 60/40 - adjust if you have audited figures.")
    else:
        st.info("üí° Fetch public data for your institutions in the Public Data tab to auto-fill these fields.")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Input Financials")
        rev = st.number_input("Total Revenues ($)", min_value=0.0, value=cfi_defaults["rev"], step=1_000_000.0, format="%.0f")
        exp = st.number_input("Operating Expenses ($)", min_value=0.0, value=cfi_defaults["exp"], step=1_000_000.0, format="%.0f")
        assets = st.number_input("Total Assets ($)", min_value=0.0, value=cfi_defaults["assets"], step=1_000_000.0, format="%.0f")
        liab = st.number_input("Total Liabilities ($)", min_value=0.0, value=cfi_defaults["liab"], step=1_000_000.0, format="%.0f")
        una = st.number_input("Net Assets w/o Donor Restrictions ($)", min_value=-500_000_000.0, value=cfi_defaults["una"], step=1_000_000.0, format="%.0f")
        rna = st.number_input("Net Assets w/ Donor Restrictions ($)", min_value=0.0, value=cfi_defaults["rna"], step=1_000_000.0, format="%.0f")
        change_na = st.number_input("Change in Net Assets ($)", min_value=-500_000_000.0, value=cfi_defaults["change_na"], step=500_000.0, format="%.0f")

    with col2:
        if st.button("Calculate CFI", type="primary"):
            result = calculate_cfi({
                "total_revenues": rev,
                "operating_expenses": exp,
                "total_assets": assets,
                "total_liabilities": liab,
                "net_assets_without_donor_restrictions": una,
                "net_assets_with_donor_restrictions": rna,
                "change_in_net_assets": change_na,
            })

            if "error" in result:
                st.error(result["error"])
            else:
                render_cfi_gauge(result["cfi_score"])

                color_class = {"green": "risk-green", "orange": "risk-yellow", "red": "risk-red"}[result["color"]]
                st.markdown(f'<div class="{color_class}"><b>{result["cfi_score"]}</b> - {result["classification"]}</div>', unsafe_allow_html=True)

                st.subheader("Component Ratios")
                comps = result["components"]
                comp_data = {
                    "Primary Reserve": (comps["primary_reserve_ratio"], comps["primary_reserve_strength"], "‚â• 0.20 target"),
                    "Equity Ratio": (comps["equity_ratio"], comps["equity_ratio_strength"], "‚â• 0.25 target"),
                    "Net Income": (comps["net_income_ratio"], comps["net_income_strength"], "‚â• 0.02 target"),
                    "Return on Net Assets": (comps["rona"], comps["rona_strength"], "‚â• 0.03 target"),
                }
                for name, (ratio, strength, target) in comp_data.items():
                    cls = "risk-green" if strength >= 1 else ("risk-yellow" if strength >= -1 else "risk-red")
                    st.markdown(f'<div class="{cls}"><b>{name}</b>: {ratio:.4f} ‚Üí Strength: {strength:.2f} ({target})</div>', unsafe_allow_html=True)

                st.info(result["doe_threshold_note"])

                if result.get("warnings"):
                    for w in result["warnings"]:
                        st.warning(w)


# ‚îÄ‚îÄ TAB 4: Q&A ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ

elif selected_tab == "Q&A":
    st.header("Deal Q&A")
    st.caption("Ask questions about this deal and get answers grounded in the loaded documents")

    if not client:
        st.stop()

    if not st.session_state.analyses:
        st.info("Upload and analyze documents first in the Document Analysis tab.")
    else:
        st.markdown(f"**{len(st.session_state.analyses)} document(s) loaded**")

        if "qa_history" not in st.session_state:
            st.session_state.qa_history = []

        # Suggested questions
        st.markdown("**Suggested questions for higher ed M&A:**")
        suggestions = [
            "What accreditation risks does this deal face and what's the expected timeline?",
            "Are there any bond covenant change-of-control triggers in these documents?",
            "What is the target's Title IV dependency and what DOE approvals are needed?",
            "What faculty governance approvals are required before close?",
            "What are the three biggest deal risks based on these documents?",
        ]
        cols = st.columns(2)
        for i, s in enumerate(suggestions):
            if cols[i % 2].button(s, key=f"sug_{i}"):
                st.session_state["qa_prefill"] = s

        question = st.text_area(
            "Your Question",
            value=st.session_state.pop("qa_prefill", ""),
            height=80,
            placeholder="e.g., What are the primary financial risks we should flag for the client?",
        )

        if st.button("Ask", type="primary") and question:
            context = "\n\n".join(f"=== {a['name']} ===\n{a['result']}" for a in st.session_state.analyses)
            with st.spinner("Analyzing..."):
                answer = answer_question(client, question, context)
            st.session_state.qa_history.append({"q": question, "a": answer})

        for item in reversed(st.session_state.qa_history):
            st.markdown(f"**Q:** {item['q']}")
            st.markdown(item["a"])
            st.divider()


# ‚îÄ‚îÄ TAB 5: DD Memo ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ‚îÄ

elif selected_tab == "DD Memo":
    st.header("Due Diligence Memo")
    st.caption("Generate a full DD memo synthesizing all document analyses")

    if not client:
        st.stop()

    if not st.session_state.analyses:
        st.info("Analyze documents first in the Document Analysis tab.")
    else:
        inst_label = target_name or "Target Institution"

        if st.button("Generate Full DD Memo", type="primary"):
            with st.spinner("Generating due diligence memo (this takes ~30 seconds)..."):
                memo = generate_dd_memo(client, st.session_state.analyses, inst_label)
                st.session_state.dd_memo = memo

        if st.session_state.dd_memo:
            st.markdown(st.session_state.dd_memo)
            st.download_button(
                "Download Memo as Markdown",
                data=st.session_state.dd_memo,
                file_name=f"DD_Memo_{inst_label.replace(' ', '_')}.md",
                mime="text/markdown",
            )
