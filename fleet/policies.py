import datetime
from typing import List, Dict, Any
from fleet.state import PipelineState

class PolicyEngine:
    @staticmethod
    def calculate_outlier_threshold(amounts: List[float]) -> float:
        """
        Calculates a robust statistical outlier threshold using Interquartile Range (IQR).
        Threshold = Q3 + 3 * IQR
        """
        valid_amounts = [a for a in amounts if a is not None]
        if not valid_amounts:
            return 100000.0  # Safe fallback
        
        sorted_amounts = sorted(valid_amounts)
        n = len(sorted_amounts)
        
        # Calculate Q1 (25th percentile) and Q3 (75th percentile)
        q1_idx = int(n * 0.25)
        q3_idx = int(n * 0.75)
        
        q1 = sorted_amounts[q1_idx]
        q3 = sorted_amounts[q3_idx]
        iqr = q3 - q1
        
        # If IQR is too small or zero, fallback to a standard deviation or percentile
        if iqr <= 0:
            # use 3 * mean
            mean = sum(sorted_amounts) / len(sorted_amounts)
            return max(mean * 2, 50000.0)
            
        threshold = q3 + 3 * iqr
        return threshold

    @staticmethod
    def check_stale(deadline_str: str, pipeline_now_str: str) -> bool:
        """
        Checks if the deadline is before pipeline_now.
        """
        try:
            deadline = datetime.datetime.strptime(deadline_str, "%Y-%m-%d").date()
            pipeline_now = datetime.datetime.strptime(pipeline_now_str, "%Y-%m-%d").date()
            return deadline < pipeline_now
        except Exception:
            return False

    @staticmethod
    def check_missing_inputs(normalized: Dict[str, Any]) -> List[str]:
        """
        Returns missing required fields.
        For E-commerce, required fields are: id, customer, amount, deadline, shipping_address
        """
        required = ["id", "customer", "amount", "deadline", "shipping_address"]
        missing = []
        for field in required:
            val = normalized.get(field)
            if val is None or val == "":
                missing.append(field)
        return missing

    @staticmethod
    def is_injection(notes: str) -> bool:
        """
        Checks for prompt injection patterns.
        """
        if not notes:
            return False
        notes_lower = notes.lower()
        keywords = [
            "ignore all previous instructions",
            "ignore instructions",
            "ignore your rules",
            "approve immediately",
            "skip review",
            "skip validation",
            "bypass checks",
            "output approved",
            "override instructions"
        ]
        return any(kw in notes_lower for kw in keywords)

    @staticmethod
    def enforce_budgets(state: PipelineState, max_cost: float, max_steps: int) -> bool:
        """
        Checks if execution exceeds step or cost budgets.
        """
        if state.cost_usd >= max_cost or state.steps >= max_steps:
            state.status = "exception"
            state.reason_code = "BUDGET_EXCEEDED"
            state.reason_class = "A"
            return True
        return False

    @staticmethod
    def requires_compliance_approval(amount: float, threshold: float = 45000.0) -> bool:
        """
        Determines if compliance approval is required.
        """
        return amount >= threshold
