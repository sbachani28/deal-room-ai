"""Fetches public data for higher ed institutions via ProPublica and IPEDS APIs."""
import requests


def fetch_990_data(org_name: str) -> dict:
    """Search ProPublica Nonprofit Explorer for an institution's 990 filings."""
    try:
        url = f"https://projects.propublica.org/nonprofits/api/v2/search.json"
        resp = requests.get(url, params={"q": org_name, "ntee_major_code": "B"}, timeout=10)
        if resp.status_code != 200:
            return {"error": f"ProPublica API returned {resp.status_code}"}

        data = resp.json()
        orgs = data.get("organizations", [])
        if not orgs:
            return {"error": "No matching nonprofit found"}

        org = orgs[0]
        ein = org.get("ein")

        filings_resp = requests.get(
            f"https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json",
            timeout=10,
        )
        if filings_resp.status_code != 200:
            return {"org": org, "filings": []}

        filings_data = filings_resp.json()
        filings = filings_data.get("filings_with_data", [])[:5]

        return {
            "name": org.get("name"),
            "ein": ein,
            "state": org.get("state"),
            "ntee_code": org.get("ntee_code"),
            "latest_filings": [
                {
                    "year": f.get("tax_prd_yr"),
                    "total_revenue": f.get("totrevenue"),
                    "total_expenses": f.get("totfuncexpns"),
                    "total_assets": f.get("totassetsend"),
                    "total_liabilities": f.get("totliabend"),
                    "net_assets": f.get("totnetassetsend") or (
                        (f.get("totassetsend") or 0) - (f.get("totliabend") or 0)
                        if f.get("totassetsend") else None
                    ),
                    "employee_count": f.get("noemployees"),
                }
                for f in filings
            ],
        }
    except Exception as e:
        return {"error": str(e)}


def fetch_ipeds_data(institution_name: str) -> dict:
    """Search IPEDS (Integrated Postsecondary Education Data System) for institution data."""
    try:
        search_url = "https://educationdata.urban.org/api/v1/college-university/ipeds/directory/"
        resp = requests.get(
            search_url,
            params={"inst_name": institution_name, "limit": 3},
            timeout=15,
        )
        if resp.status_code != 200:
            return {"error": f"IPEDS API returned {resp.status_code}"}

        data = resp.json()
        results = data.get("results", [])
        if not results:
            return {"error": "No IPEDS match found"}

        inst = results[0]
        unitid = inst.get("unitid")

        enrollment_resp = requests.get(
            f"https://educationdata.urban.org/api/v1/college-university/ipeds/fall-enrollment/{unitid}/",
            params={"year": 2023, "level_of_study": 1},
            timeout=10,
        )
        enrollment = {}
        if enrollment_resp.status_code == 200:
            enroll_data = enrollment_resp.json().get("results", [])
            if enroll_data:
                enrollment = {"total_enrollment": sum(r.get("enrollment", 0) for r in enroll_data[:5])}

        return {
            "name": inst.get("inst_name"),
            "unitid": unitid,
            "state": inst.get("fips_ipeds"),
            "sector": inst.get("sector"),
            "control": inst.get("control"),
            "hbcu": inst.get("hbcu"),
            "tribal": inst.get("tribal"),
            "level": inst.get("level"),
            "accreditor": inst.get("accreditor"),
            "website": inst.get("website"),
            "enrollment": enrollment,
        }
    except Exception as e:
        return {"error": str(e)}


ACCREDITOR_CHANGE_OF_CONTROL = {
    "HLC": {
        "name": "Higher Learning Commission",
        "states": ["IL", "IN", "IA", "KS", "MI", "MN", "MO", "NE", "ND", "OH", "OK", "SD", "WI", "WV", "WY", "CO", "AZ", "NM"],
        "notice_required": "6 months prior written notice",
        "approval_required": True,
        "timeline": "Typically 6-18 months",
        "notes": "Requires substantive change application. May require focused visit or comprehensive evaluation.",
    },
    "SACSCOC": {
        "name": "Southern Association of Colleges and Schools Commission on Colleges",
        "states": ["AL", "FL", "GA", "KY", "LA", "MS", "NC", "SC", "TN", "TX", "VA"],
        "notice_required": "Prospectus required before change",
        "approval_required": True,
        "timeline": "12-24 months",
        "notes": "Strictest change-of-control process. Requires level change application and on-site committee.",
    },
    "WSCUC": {
        "name": "WASC Senior College and University Commission",
        "states": ["CA", "HI", "OR", "WA", "AK", "NV", "UT", "ID", "MT"],
        "notice_required": "Notify immediately upon intent",
        "approval_required": True,
        "timeline": "6-12 months",
        "notes": "Requires substantive change report and possible special visit.",
    },
    "NECHE": {
        "name": "New England Commission of Higher Education",
        "states": ["CT", "ME", "MA", "NH", "RI", "VT"],
        "notice_required": "Immediate notification",
        "approval_required": True,
        "timeline": "3-12 months depending on complexity",
        "notes": "Change-of-control triggers substantive change review.",
    },
    "MSCHE": {
        "name": "Middle States Commission on Higher Education",
        "states": ["DE", "MD", "NJ", "NY", "PA", "DC"],
        "notice_required": "Immediate notification",
        "approval_required": True,
        "timeline": "6-18 months",
        "notes": "Substantive change protocol applies. May require evaluation visit.",
    },
    "NWCCU": {
        "name": "Northwest Commission on Colleges and Universities",
        "states": ["AK", "ID", "MT", "NV", "OR", "UT", "WA"],
        "notice_required": "As soon as practicable",
        "approval_required": True,
        "timeline": "6-12 months",
        "notes": "Change of ownership/control is a substantive change.",
    },
}
