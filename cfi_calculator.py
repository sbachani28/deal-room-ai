"""
Composite Financial Index (CFI) calculator for higher education institutions.
The CFI is a weighted score (scale -4 to 10) used by the US Dept. of Education
to assess financial health. A score below 1.5 triggers enhanced oversight.
"""


def calculate_cfi(financials: dict) -> dict:
    """
    Compute the CFI from extracted financial statement data.

    Expects:
        total_revenues, operating_expenses, total_assets, total_liabilities,
        net_assets_without_donor_restrictions, net_assets_with_donor_restrictions,
        change_in_net_assets, debt_service (optional)
    """
    results = {}
    warnings = []

    try:
        rev = float(financials.get("total_revenues", 0))
        exp = float(financials.get("operating_expenses", 0))
        assets = float(financials.get("total_assets", 0))
        liab = float(financials.get("total_liabilities", 0))
        una = float(financials.get("net_assets_without_donor_restrictions", 0))
        rna = float(financials.get("net_assets_with_donor_restrictions", 0))
        change_na = float(financials.get("change_in_net_assets", 0))
        debt_service = float(financials.get("debt_service", 1))

        if debt_service == 0:
            debt_service = 1
            warnings.append("Debt service set to $1 to avoid division by zero")

        total_net_assets = una + rna
        expendable_net_assets = una + rna * 0.5  # approx — restricted net assets partially expendable

        # Ratio 1: Primary Reserve Ratio = Expendable Net Assets / Total Expenses
        if exp > 0:
            primary_reserve = expendable_net_assets / exp
        else:
            primary_reserve = 0
            warnings.append("Operating expenses = 0; primary reserve ratio may be unreliable")

        # Ratio 2: Equity Ratio = Modified Net Assets / Modified Total Assets
        modified_net_assets = total_net_assets
        modified_total_assets = assets
        equity_ratio = modified_net_assets / modified_total_assets if modified_total_assets > 0 else 0

        # Ratio 3: Net Income Ratio = Change in Net Assets / Total Revenue
        net_income_ratio = change_na / rev if rev > 0 else 0

        # Ratio 4: Return on Net Assets = Change in Net Assets / Average Net Assets
        rona = change_na / total_net_assets if total_net_assets > 0 else 0

        # CFI Strength Factors (convert ratios to -4..3 scale)
        def primary_reserve_strength(r):
            if r >= 0.4:
                return 3.0
            elif r >= 0.2:
                return 1.0 + (r - 0.2) / 0.2 * 2.0
            elif r >= 0.0:
                return -1.0 + r / 0.2 * 2.0
            else:
                return max(-4.0, -1.0 + r / 0.2 * 3.0)

        def equity_ratio_strength(r):
            if r >= 0.5:
                return 3.0
            elif r >= 0.25:
                return 1.0 + (r - 0.25) / 0.25 * 2.0
            elif r >= 0.0:
                return -1.0 + r / 0.25 * 2.0
            else:
                return max(-4.0, -4.0)

        def net_income_strength(r):
            if r >= 0.04:
                return 3.0
            elif r >= 0.02:
                return 1.0 + (r - 0.02) / 0.02 * 2.0
            elif r >= -0.02:
                return -1.0 + (r + 0.02) / 0.04 * 2.0
            else:
                return max(-4.0, -4.0)

        def rona_strength(r):
            if r >= 0.06:
                return 3.0
            elif r >= 0.03:
                return 1.0 + (r - 0.03) / 0.03 * 2.0
            elif r >= -0.03:
                return -1.0 + (r + 0.03) / 0.06 * 2.0
            else:
                return max(-4.0, -4.0)

        pr_strength = primary_reserve_strength(primary_reserve)
        er_strength = equity_ratio_strength(equity_ratio)
        ni_strength = net_income_strength(net_income_ratio)
        rona_s = rona_strength(rona)

        # CFI = weighted average (DOE weights)
        cfi = 0.35 * pr_strength + 0.35 * er_strength + 0.20 * ni_strength + 0.10 * rona_s

        # Classify
        if cfi >= 3.0:
            classification = "Financially Strong"
            color = "green"
        elif cfi >= 1.5:
            classification = "Financially Responsible"
            color = "green"
        elif cfi >= 1.0:
            classification = "Zone — Heightened Oversight"
            color = "orange"
        else:
            classification = "Financially Weak — DOE Enhanced Oversight Triggered"
            color = "red"

        results = {
            "cfi_score": round(cfi, 2),
            "classification": classification,
            "color": color,
            "components": {
                "primary_reserve_ratio": round(primary_reserve, 4),
                "primary_reserve_strength": round(pr_strength, 2),
                "equity_ratio": round(equity_ratio, 4),
                "equity_ratio_strength": round(er_strength, 2),
                "net_income_ratio": round(net_income_ratio, 4),
                "net_income_strength": round(ni_strength, 2),
                "rona": round(rona, 4),
                "rona_strength": round(rona_s, 2),
            },
            "raw_financials": {
                "total_revenues": rev,
                "operating_expenses": exp,
                "total_assets": assets,
                "total_liabilities": liab,
                "net_assets": total_net_assets,
                "change_in_net_assets": change_na,
            },
            "warnings": warnings,
            "doe_threshold_note": (
                "DOE requires a CFI ≥ 1.5 for full Title IV participation without additional conditions. "
                "Scores 1.0–1.5 trigger the Zone Alternative (heightened monitoring). "
                "Scores below 1.0 may require letter of credit or other financial protection."
            ),
        }
    except Exception as e:
        results = {"error": str(e), "cfi_score": None}

    return results
