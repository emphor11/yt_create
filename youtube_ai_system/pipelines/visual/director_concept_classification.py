from __future__ import annotations

import re
from typing import Any

from ...services.financial_governance import first_fact, numeric_role_map
from .director_types import VisualDirectorInput


class VisualDirectorConceptClassificationMixin:
    def _normalized_concept_type(self, director_input: VisualDirectorInput) -> str:
        explicit = str(director_input.concept_type or "").strip().lower()
        aliases = {
            "emi_stack": "emi_pressure",
            "fomo_risk": "speculation_risk",
            "salary_depletion": "salary_drain",
            # tax_drain is NOT aliased to tax_saving — they are opposite concepts:
            # tax_drain = money leaking to tax (danger, MoneyFlow)
            # tax_saving = reducing tax via planning (positive, SplitComparison)
        }
        if explicit in aliases:
            return aliases[explicit]
        semantic_key = self._semantic_primary_concept_key(director_input)
        if semantic_key in aliases:
            return aliases[semantic_key]
        if semantic_key and semantic_key not in {"unknown", "definition", "general_point"}:
            return semantic_key
        if explicit in {
            "salary_drain",
            "lifestyle_inflation",
            "emi_pressure",
            "debt_trap",
            "inflation_erosion",
            "sip_growth",
            "compounding",
            "recap_system",
            "risk_return",
            "emergency_fund",
            "speculation_risk",
            "diversification",
            "tax_saving",
            "tax_drain",
            "rent_burden",
            "expense_leakage",
            "subscription_leak",
            "budgeting",
            "savings_rate",
            "loan_cost",
            "net_worth_growth",
        }:
            return explicit
        narration_text = str(director_input.narration_text or "").lower()
        if narration_text.strip().startswith("recap") or ("break free" in narration_text and "future self" in narration_text):
            return "recap_system"
        text = f"{director_input.narration_text} {explicit}".lower()
        if "sip" in text or "systematic investment plan" in text:
            return "sip_growth"
        if any(token in text for token in ("debt trap", "credit card", "minimum payment", "minimum dues")):
            return "debt_trap"
        if "debt" in text and any(token in text for token in ("interest", "compound", "grows", "trapped", "trap")):
            return "debt_trap"
        if "emi" in text and any(token in text for token in ("pressure", "burden", "loan", "interest", "stack", "takes", "fixed", "month")):
            return "emi_pressure"
        if "salary" in text and any(token in text for token in ("drain", "depletion", "disappear", "vanish", "left", "gone", "empty", "broke")):
            return "salary_drain"
        if "lifestyle inflation" in text:
            return "lifestyle_inflation"
        if (
            ("raise" in text or "hike" in text or "income rises" in text or "salary rises" in text)
            and any(token in text for token in ("lifestyle", "upgrade", "luxury", "luxuries", "expenses catch", "spending rises", "savings stay", "savings flat"))
        ):
            return "lifestyle_inflation"
        # loan/debt checks before generic keyword grabs
        if "loan" in text and ("cost" in text or "interest" in text):
            return "loan_cost"
        if "inflation" in text and any(token in text for token in ("fd", "fixed deposit", "real return", "return")):
            return "fd_vs_inflation"
        if "inflation" in text or "purchasing power" in text or "buying power" in text:
            return "inflation_erosion"
        if "fomo" in text or "speculation" in text or "life savings" in text or "don't understand" in text or "do not understand" in text:
            return "speculation_risk"
        if "diversification" in text or "diversify" in text or "asset classes" in text or "one basket" in text or "one stock" in text or "all eggs" in text:
            return "diversification"
        if "compound" in text or "compounding" in text:
            return "compounding"
        if "real return" in text or ("tax" in text and "return" in text):
            return "real_return"
        if (
            "expense leakage" in text
            or "subscription" in text
            or "leak" in text
            or ("small" in text and any(token in text for token in ("choices add", "adding up", "repeats", "tiny", "harmless")))
            or ("pattern" in text and "expensive" in text)
        ):
            return "expense_leakage"
        if "emergency fund" in text or "cash buffer" in text:
            return "emergency_fund"
        # opportunity_cost: require specific intent, not just "instead"
        if "opportunity cost" in text or "could have been" in text or (
            "instead" in text and any(token in text for token in ("invest", "sip", "fd", "savings", "corpus", "compound"))
        ):
            return "opportunity_cost"
        if "risk" in text and "return" in text:
            return "risk_return"
        # tax_saving: only when an explicit planning/saving action is present
        if "80c" in text or ("tax" in text and any(token in text for token in ("save", "saving", "invest", "plan", "deduct", "exemption"))):
            return "tax_saving"
        # tax_drain: informational tax mention (bracket, GST, income tax, etc.)
        if "tax" in text:
            return "tax_drain"
        if "budget" in text or "allocate" in text:
            return "budgeting"
        # savings_rate: require specific phrasing, not just "save" + "income"
        if "savings rate" in text or re.search(r"save\s+\d+\s*%\s*(?:of|from)?\s*income", text):
            return "savings_rate"
        # net_worth_growth: only when growth/building direction is explicit
        negative_wealth_context = any(token in text for token in ("destroy", "debt", "lose", "loss", "erode", "hurt", "trap"))
        if "net worth" in text or (
            "wealth" in text
            and not negative_wealth_context
            and any(token in text for token in ("build", "grow", "create", "compound", "increase"))
        ):
            return "net_worth_growth"
        return str(director_input.concept_type or director_input.idea_type or "definition").strip() or "definition"

    def _display_concept_name(self, concept_type: str) -> str:
        return {
            "lifestyle_inflation": "Lifestyle Inflation",
            "expense_leakage": "Expense Leakage",
            "budgeting": "Budget Allocation",
            "savings_rate": "Savings Rate",
            "emergency_fund": "Emergency Fund",
            "rent_burden": "Rent Burden",
            "emi_pressure": "EMI Pressure",
            "loan_cost": "Loan Cost",
            "compounding": "Compounding",
            "net_worth_growth": "Net Worth Growth",
            "recap_system": "Money System Recap",
            "inflation_erosion": "Inflation Erosion",
            "inflation_loss": "Inflation Loss",
            "real_return": "Real Return",
            "fd_vs_inflation": "FD vs Inflation",
            "opportunity_cost": "Opportunity Cost",
            "comparison_timeline": "Decision Timeline",
            "risk_return": "Risk vs Return",
            "diversification": "Diversification",
            "tax_saving": "Tax Saving",
            "tax_drain": "Tax Drain",
            "speculation_risk": "Investing vs Speculation",
        }.get(concept_type, concept_type.replace("_", " ").title())

    def _money_flow_title(self, concept_type: str) -> str:
        return {
            "lifestyle_inflation": "Where the raise went",
            "expense_leakage": "Where money leaks",
            "budgeting": "Budget split",
            "savings_rate": "Income allocation",
            "emergency_fund": "Safety buffer",
            "tax_drain": "Tax drain",
            "rent_burden": "Rent burden",
        }.get(concept_type, "Money movement")

    def _money_mechanism_punch(self, flow_data: dict[str, Any], concept_type: str) -> str:
        if concept_type == "emergency_fund":
            return f"{flow_data['remainder']['value']} buffer"
        if flow_data["remainder"]["is_dangerous"]:
            return f"{flow_data['remainder']['value']} left"
        return "The gap matters"
