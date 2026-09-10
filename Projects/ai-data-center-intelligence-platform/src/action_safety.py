"""Human-in-the-loop policy: diagnose and recommend, but never control infrastructure."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ActionSafetyDecision:
    approval_required: bool
    action_category: str | None = None


class ActionSafetyPolicy:
    """Detect direct requests to change systems while allowing analysis of past events."""

    _ACTION_GROUPS = {
        "server_control": r"restart|reboot|shut\s*down|power\s*off|turn\s*off",
        "network_control": r"change|modify|apply|remove|disable|enable",
        "cooling_control": r"set|change|modify|disable|enable|stop|start",
        "data_deletion": r"delete|erase|wipe|purge|truncate|drop",
    }
    _OBJECTS = {
        "server_control": r"server|host|machine|equipment|ups|pdu",
        "network_control": r"firewall|firewall rules?|routing|route|switch|network rule",
        "cooling_control": r"cooling|temperature|chiller|pump|fan|valve|setpoint|controller",
        "data_deletion": r"data|database|table|logs?|alerts?|records?|files?",
    }

    def evaluate(self, question: str) -> ActionSafetyDecision:
        lower = " ".join(question.lower().split())
        # Explicit historical/explanatory wording is analysis, not an action request.
        if re.match(r"^(why|when|what|how)\s+(?:did|was|were|has|have)\b", lower):
            return ActionSafetyDecision(False)
        if re.match(r"^(what if|what would|how would|estimate|simulate|model)\b", lower):
            return ActionSafetyDecision(False)
        request_prefix = (
            r"(?:^|\b)(?:please\s+|can you\s+|could you\s+|would you\s+|"
            r"go ahead and\s+|execute\s+|perform\s+|apply\s+|now\s+)?"
        )
        for category, action_pattern in self._ACTION_GROUPS.items():
            object_pattern = self._OBJECTS[category]
            if re.search(
                request_prefix + rf"(?:{action_pattern})\b[^?.]{{0,80}}\b(?:{object_pattern})\b",
                lower,
            ):
                return ActionSafetyDecision(True, category)
        return ActionSafetyDecision(False)

    @staticmethod
    def refusal(category: str | None) -> str:
        label = (category or "operational").replace("_", " ")
        return (
            f"I can analyze evidence and recommend checks, but I cannot execute that {label} action. "
            "A qualified operator must review the evidence, follow the approved change process, and "
            "authorize any infrastructure change. No command or control action was performed."
        )
