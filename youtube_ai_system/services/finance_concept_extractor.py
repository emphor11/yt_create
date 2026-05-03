from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, List, Optional
import re


@dataclass
class FinanceConcept:
    concept_name: str
    concept_type: str
    primary_entity: str
    action: str
    start_value: Optional[str] = None
    end_value: Optional[str] = None
    percentage: Optional[float] = None
    time_period: Optional[str] = None
    agent: Optional[str] = None
    victim: Optional[str] = None
    confidence: float = 1.0


CONCEPT_TAXONOMY: dict[str, dict[str, Any]] = {
    "emi_pressure": {
        "signals": [
            r"\bemi\b.*\b(stack|pressure|joins?|leaves?|starts?|takes?|fixed|month|monthly)\b",
            r"\b(phone|bike|car|personal)\s+emi\b",
            r"\bmultiple\s+emis?\b",
            r"\bfixed payments?\b",
            r"\binstalments?\b.*\b(stack|month|salary|cash)\b",
        ],
        "type": "risk",
        "visual_pattern": "emi_stack_pressure",
    },
    "sip_growth": {
        "signals": [
            r"\bsip\b",
            r"monthly investment.*compound",
            r"monthly investment.*returns?",
            r"invest.*per month.*returns?",
            r"small investments?.*corpus",
            r"corpus.*grows?",
        ],
        "type": "growth",
        "visual_pattern": "sip_compound_growth",
    },
    "lifestyle_inflation": {
        "signals": [
            r"lifestyle inflation",
            r"spend more",
            r"expenses increase",
            r"raise.*spend",
            r"income.*upgrade",
            r"earn more.*buy",
            r"salary rises.*expenses rise faster",
            r"fancy phone",
            r"brand new car",
            r"fancy wedding",
        ],
        "type": "risk",
        "visual_pattern": "income_vs_spending_divergence",
    },
    "debt_trap": {
        "signals": [
            r"debt trap",
            r"credit card.*interest",
            r"emi.*burden",
            r"loan.*spiral",
            r"borrow.*repay",
            r"interest.*compound",
            r"minimum payment",
            r"minimum dues",
            r"outstanding balance",
        ],
        "type": "risk",
        "visual_pattern": "debt_growth_spiral",
    },
    "inflation_erosion": {
        "signals": [
            r"inflation.*value",
            r"purchasing power",
            r"real returns",
            r"fd.*inflation",
            r"price.*rise",
            r"cost.*increase",
            r"buying power",
        ],
        "type": "risk",
        "visual_pattern": "value_erosion_over_time",
    },
    "compound_growth": {
        "signals": [
            r"compound",
            r"compounding",
            r"grows over time",
            r"long.?term.*investment",
            r"wealth.*build",
        ],
        "type": "growth",
        "visual_pattern": "exponential_growth_curve",
    },
    "salary_depletion": {
        "signals": [
            r"salary.*gone",
            r"paycheck.*paycheck",
            r"month.*broke",
            r"income.*expenses",
            r"nothing.*left",
            r"save.*nothing",
            r"salary.*leak",
            r"salary.*vanish",
        ],
        "type": "risk",
        "visual_pattern": "income_drain_waterfall",
    },
    "opportunity_cost": {
        "signals": [
            r"instead.*invest",
            r"could have",
            r"if.*invested",
            r"missed.*returns",
            r"cost.*not investing",
        ],
        "type": "comparison",
        "visual_pattern": "path_comparison_split",
    },
    "savings_rate": {
        "signals": [
            r"save.*percent",
            r"saving.*income",
            r"%.*saving",
            r"invest.*salary",
            r"put aside",
            r"automate.*save",
            r"budget",
            r"track",
            r"allocate",
        ],
        "type": "process",
        "visual_pattern": "income_allocation_breakdown",
    },
    "tax_efficiency": {
        "signals": [
            r"tax.*save",
            r"80c",
            r"deduction",
            r"tax.*exempt",
            r"post.?tax",
            r"pre.?tax",
            r"ppf",
            r"nps",
            r"elss",
        ],
        "type": "comparison",
        "visual_pattern": "before_after_tax_split",
    },
    "risk_return": {
        "signals": [
            r"risk.*return",
            r"safe.*low",
            r"volatile.*high",
            r"fd.*safe",
            r"equity.*risk",
            r"fixed.*return",
            r"equity.*debt",
            r"while debt is stable",
        ],
        "type": "comparison",
        "visual_pattern": "risk_return_spectrum",
    },
    "expense_leakage": {
        "signals": [
            r"subscription",
            r"subscriptions",
            r"expense",
            r"expenses",
            r"spending",
            r"dining out",
            r"ordering in",
            r"premium",
            r"leak",
            r"leaks",
        ],
        "type": "risk",
        "visual_pattern": "expense_leakage_ladder",
    },
    "emergency_fund": {
        "signals": [
            r"emergency fund",
            r"cash buffer",
            r"medical emergency",
            r"lose your job",
        ],
        "type": "definition",
        "visual_pattern": "buffer_protection_split",
    },
}


class FinanceConceptExtractor:
    def extract(self, idea_group: Any) -> FinanceConcept:
        text = self._group_text(idea_group)
        concept = self._rule_based_extract(text, idea_group)
        if concept.confidence >= 0.6:
            return concept

        numeric_concept = self._numeric_pattern_extract(text, idea_group)
        if numeric_concept.confidence >= 0.5:
            return numeric_concept

        return self._llm_extract(text, idea_group)

    def extract_dict(self, idea_group: Any) -> dict[str, Any]:
        return asdict(self.extract(idea_group))

    def _group_text(self, idea_group: Any) -> str:
        if isinstance(idea_group, dict):
            return " ".join(str(idea_group.get("combined_text") or idea_group.get("text") or "").split())
        return " ".join(str(getattr(idea_group, "combined_text", "") or "").split())

    def _group_entity(self, idea_group: Any) -> str:
        if isinstance(idea_group, dict):
            return str(idea_group.get("dominant_entity") or "money")
        return str(getattr(idea_group, "dominant_entity", "money") or "money")

    def _group_idea_type(self, idea_group: Any) -> str:
        if isinstance(idea_group, dict):
            return str(idea_group.get("idea_type") or "emphasis")
        return str(getattr(idea_group, "idea_type", "emphasis") or "emphasis")

    def _rule_based_extract(self, text: str, idea_group: Any) -> FinanceConcept:
        text_lower = text.lower()

        for concept_key, config in CONCEPT_TAXONOMY.items():
            for signal in config["signals"]:
                if re.search(signal, text_lower):
                    numbers = self._extract_numbers(text)
                    concept_name = self._display_name(concept_key)
                    concept_type = self._normalize_type(config["type"])
                    if concept_key == "risk_return":
                        comparison_name = self._extract_comparison_name(text)
                        if comparison_name:
                            concept_name = comparison_name
                    return FinanceConcept(
                        concept_name=concept_name,
                        concept_type=concept_type,
                        primary_entity=self._group_entity(idea_group),
                        action=self._extract_action(text),
                        start_value=numbers[0] if numbers else None,
                        end_value=numbers[-1] if len(numbers) > 1 else None,
                        percentage=self._extract_percentage(text),
                        time_period=self._extract_time_period(text),
                        agent=self._extract_agent(text),
                        victim=self._extract_victim(text, self._group_entity(idea_group)),
                        confidence=0.9,
                    )

        return FinanceConcept(
            concept_name="Unknown",
            concept_type=self._normalize_type(self._group_idea_type(idea_group)),
            primary_entity=self._group_entity(idea_group),
            action=self._extract_action(text),
            confidence=0.1,
        )

    def _numeric_pattern_extract(self, text: str, idea_group: Any) -> FinanceConcept:
        numbers = self._extract_numbers(text)
        percentage = self._extract_percentage(text)
        time = self._extract_time_period(text)

        if not numbers and percentage is None:
            return FinanceConcept(
                concept_name="General Point",
                concept_type="emphasis",
                primary_entity=self._group_entity(idea_group),
                action="noted",
                confidence=0.2,
            )

        concept_type = self._group_idea_type(idea_group)
        if len(numbers) >= 2:
            try:
                n1 = float(re.sub(r"[^\d.]", "", numbers[0]))
                n2 = float(re.sub(r"[^\d.]", "", numbers[-1]))
                if n2 < n1:
                    concept_type = "risk"
                elif n2 > n1:
                    concept_type = "growth"
            except (ValueError, IndexError):
                pass

        entity = self._group_entity(idea_group)
        return FinanceConcept(
            concept_name=f"{entity.title()} Change",
            concept_type=self._normalize_type(concept_type),
            primary_entity=entity,
            action="changes over time",
            start_value=numbers[0] if numbers else None,
            end_value=numbers[-1] if len(numbers) > 1 else None,
            percentage=percentage,
            time_period=time,
            agent=self._extract_agent(text),
            victim=self._extract_victim(text, entity),
            confidence=0.6,
        )

    def _llm_extract(self, text: str, idea_group: Any) -> FinanceConcept:
        # Structured fallback kept deterministic for now.
        entity = self._group_entity(idea_group)
        numbers = self._extract_numbers(text)
        return FinanceConcept(
            concept_name=self._manual_concept_name(text, entity),
            concept_type=self._normalize_type(self._group_idea_type(idea_group)),
            primary_entity=entity,
            action=self._extract_action(text),
            start_value=numbers[0] if numbers else None,
            end_value=numbers[-1] if len(numbers) > 1 else None,
            percentage=self._extract_percentage(text),
            time_period=self._extract_time_period(text),
            agent=self._extract_agent(text),
            victim=self._extract_victim(text, entity),
            confidence=0.7,
        )

    def _display_name(self, concept_key: str) -> str:
        display_map = {
            "emi_pressure": "EMI Pressure",
            "sip_growth": "SIP Growth",
            "lifestyle_inflation": "Lifestyle Inflation",
            "debt_trap": "Debt Trap",
            "inflation_erosion": "Inflation Loss",
            "compound_growth": "Compounding Growth",
            "salary_depletion": "Salary Depletion",
            "opportunity_cost": "Opportunity Cost",
            "savings_rate": "Savings Rate",
            "tax_efficiency": "Tax Saving",
            "risk_return": "Risk Return",
            "expense_leakage": "Expense Leakage",
            "emergency_fund": "Emergency Fund",
        }
        return display_map.get(concept_key, concept_key.replace("_", " ").title())

    def _normalize_type(self, concept_type: str) -> str:
        normalized = str(concept_type or "").strip().lower()
        supported = {"risk", "growth", "comparison", "process", "definition"}
        if normalized in supported:
            return normalized
        if normalized in {"decay", "causation"}:
            return "risk"
        if normalized == "emphasis":
            return "definition"
        return "definition"

    def _manual_concept_name(self, text: str, entity: str) -> str:
        lowered = text.lower()
        comparison_name = self._extract_comparison_name(text)
        if comparison_name:
            return comparison_name
        if "emi" in lowered or "instalment" in lowered or "installment" in lowered:
            return "EMI Pressure"
        if "sip" in lowered or ("monthly investment" in lowered and ("compound" in lowered or "return" in lowered)):
            return "SIP Growth"
        if "credit card" in lowered or "interest" in lowered or "minimum payment" in lowered:
            return "Debt Trap"
        if "raise" in lowered or "lifestyle" in lowered or "upgrade" in lowered:
            return "Lifestyle Inflation"
        if "expense" in lowered or "subscription" in lowered or "spending" in lowered:
            return "Expense Leakage"
        if "emergency fund" in lowered or "buffer" in lowered:
            return "Emergency Fund"
        if "investment" in lowered or "returns" in lowered or "wealth" in lowered:
            return "Investment Growth"
        if "tax" in lowered or "ppf" in lowered or "nps" in lowered or "elss" in lowered:
            return "Tax Saving"
        if "inflation" in lowered:
            return "Inflation Loss"
        return f"{entity.title()} Change"

    def _extract_comparison_name(self, text: str) -> Optional[str]:
        lowered = text.lower()
        if "equity" in lowered and "debt" in lowered:
            return "Equity vs Debt"
        if "risk" in lowered and "return" in lowered:
            return "Risk vs Return"
        for marker in (" vs ", " versus ", " compared to ", " while ", " however "):
            if marker in lowered:
                left, right = re.split(marker, text, maxsplit=1, flags=re.IGNORECASE)
                left_entity = self._extract_entity_name(left)
                right_entity = self._extract_entity_name(right)
                if left_entity and right_entity:
                    return f"{left_entity} vs {right_entity}"
        return None

    def _extract_entity_name(self, text: str) -> Optional[str]:
        lowered = text.lower()
        ordered = [
            "equity",
            "debt",
            "salary",
            "income",
            "credit",
            "loan",
            "emi",
            "investment",
            "savings",
            "inflation",
            "expense",
            "tax",
            "wealth",
            "risk",
            "return",
        ]
        for item in ordered:
            if item in lowered:
                return " ".join(part.capitalize() for part in item.split())
        return None

    def _extract_numbers(self, text: str) -> List[str]:
        pattern = r"₹[\d,]+(?:k|L|lakh|cr|crore)?|\d+(?:,\d+)*(?:\.\d+)?\s*%"
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            return [match.strip() for match in matches]
        fallback_pattern = r"₹[\d,]+(?:k|L|lakh|cr|crore)?|\d+(?:,\d+)*(?:\.\d+)?"
        return [match.strip() for match in re.findall(fallback_pattern, text, re.IGNORECASE)]

    def _extract_percentage(self, text: str) -> Optional[float]:
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
        if match:
            return float(match.group(1))
        return None

    def _extract_time_period(self, text: str) -> Optional[str]:
        patterns = [
            r"\d+\s*years?",
            r"\d+\s*months?",
            r"\d+\s*days?",
            r"per year",
            r"per month",
            r"annually",
            r"monthly",
            r"by \d{4}",
            r"in \d+ years",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        return None

    def _extract_action(self, text: str) -> str:
        action_patterns = [
            (r"increas\w+", "increases"),
            (r"decreas\w+", "decreases"),
            (r"compoun\w+", "compounds"),
            (r"drain\w+", "drains"),
            (r"grow\w+", "grows"),
            (r"shr\w+", "shrinks"),
            (r"eros\w+", "erodes"),
            (r"spirals?", "spirals"),
            (r"leak\w+", "leaks"),
            (r"destroy\w+", "destroys"),
        ]
        text_lower = text.lower()
        for pattern, action in action_patterns:
            if re.search(pattern, text_lower):
                return action
        return "changes"

    def _extract_agent(self, text: str) -> Optional[str]:
        lowered = text.lower()
        if "interest" in lowered:
            return "interest"
        if "inflation" in lowered:
            return "inflation"
        if "spending" in lowered or "expenses" in lowered:
            return "spending"
        if "tax" in lowered:
            return "tax"
        return None

    def _extract_victim(self, text: str, primary_entity: str) -> Optional[str]:
        lowered = text.lower()
        if "savings" in lowered:
            return "savings"
        if "wealth" in lowered:
            return "wealth"
        if "income" in lowered or "salary" in lowered:
            return "salary"
        if primary_entity and primary_entity != "money":
            return primary_entity
        return None
