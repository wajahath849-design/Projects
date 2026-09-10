"""Deterministic routing for advanced operations-copilot chat modes."""

from __future__ import annotations

import re

from src.conversation_context import ConversationContext


class CopilotRouter:
    ADVANCED_MODES = {
        "SCENARIO", "ANOMALY_INVESTIGATION", "INCIDENT_INVESTIGATION",
        "LOG_SEARCH", "SIMILAR_INCIDENT", "MAINTENANCE_RECOMMENDATION",
        "HEALTH_ASSESSMENT", "DECISION_SUPPORT", "PREDICTIVE_MAINTENANCE",
        "EVIDENCE_REVIEW", "TIMELINE_FIRST_EVENT",
    }
    EXTENSION_MODES = {
        "REALTIME_STATUS", "REALTIME_METRIC", "REALTIME_ANOMALY", "REALTIME_INCIDENT",
        "MULTI_AGENT_INVESTIGATION", "COST_ANALYSIS", "CARBON_ANALYSIS",
        "EFFICIENCY_SCENARIO", "IMPACT_ANALYSIS", "CORRELATION_ANALYSIS",
        "INTERVENTION_ANALYSIS", "CAUSAL_ANALYSIS",
    }
    ALL_MODES = ADVANCED_MODES | EXTENSION_MODES

    def route(self, question: str, context: ConversationContext) -> str:
        lower = question.lower().strip()
        if re.search(r"\b(multi[- ]agent|specialist investigation|investigate (?:the )?live incident)\b", lower):
            return "MULTI_AGENT_INVESTIGATION"
        if re.search(r"\b(?:causal|cause|caused|causation)\b", lower):
            return "CAUSAL_ANALYSIS"
        if re.search(r"\b(?:intervention|difference[- ]in[- ]differences?|before and after (?:the )?(?:upgrade|change))\b", lower):
            return "INTERVENTION_ANALYSIS"
        if re.search(r"\b(?:correlat(?:e|ed|ion)|relationship between|lead[- ]lag|leads? to)\b", lower):
            return "CORRELATION_ANALYSIS"
        if re.search(r"\b(?:incident impact|impact of inc-|before during and after)\b", lower):
            return "IMPACT_ANALYSIS"
        if re.search(r"\b(?:efficiency scenario|energy savings|cost savings|avoided carbon|reduce pue)\b", lower):
            return "EFFICIENCY_SCENARIO"
        if re.search(r"\b(?:carbon|co2e|emissions?)\b", lower):
            return "CARBON_ANALYSIS"
        if re.search(
            r"\b(?:electricity price|energy price|energy cost|modeled cooling cost|"
            r"it energy cost|cost per server|total energy cost|cost forecast)\b",
            lower,
        ):
            return "COST_ANALYSIS"
        if context.data_mode == "live" or context.simulation_session_id:
            if re.search(r"\banomal", lower):
                return "REALTIME_ANOMALY"
            if re.search(r"\bincident", lower):
                return "REALTIME_INCIDENT"
            if re.search(r"\b(?:status|health|what is happening|overview)\b", lower):
                return "REALTIME_STATUS"
            if re.search(r"\b(?:metric|pue|latency|power|temperature|cpu|memory|disk|availability)\b", lower):
                return "REALTIME_METRIC"
        if re.search(r"\bwhat if\b|\bscenario\b|\bassume\b|\bif .+ (?:improves?|increases?|decreases?)\b", lower):
            return "SCENARIO"
        if re.search(r"\bwhich facility should we prioritize\b|\befficiency upgrade\b|\binvestment priority\b", lower):
            return "DECISION_SUPPORT"
        if re.search(r"\bhealth score\b|\bfacility health\b|\bdata center health\b", lower):
            return "HEALTH_ASSESSMENT"
        if re.search(r"\bfailure risk\b|\bpredictive maintenance\b|\bcould this happen again\b|\b7-day risk\b", lower):
            return "PREDICTIVE_MAINTENANCE"
        if context.incident_id and re.search(
            r"\bshow (?:me )?(?:the )?evidence\b|\bwhat evidence\b|\bsupporting evidence\b",
            lower,
        ):
            return "EVIDENCE_REVIEW"
        if context.incident_id and re.search(
            r"\bwhat happened first\b|\bearliest (?:signal|event|evidence)\b|\bfirst abnormal signal\b",
            lower,
        ):
            return "TIMELINE_FIRST_EVENT"
        if re.search(r"\bhave we seen\b|\bsimilar incidents?\b|\bsimilar outage\b|\bseen this error\b", lower):
            return "SIMILAR_INCIDENT"
        if re.search(r"\bshow (?:me )?(?:the )?logs?\b|\blog search\b|\blogs? .*(?:before|after|around)\b", lower):
            return "LOG_SEARCH"
        if re.search(
            r"\bwhat should we inspect\b|\bwhat should we check\b|\bmaintenance recommendation\b|"
            r"\bhow was (?:it|the (?:closest|similar|previous) (?:one|incident)) fixed\b",
            lower,
        ):
            return "MAINTENANCE_RECOMMENDATION"
        if re.search(r"\banomal(?:y|ies|ous)\b|\bunusual behavior\b|\babnormal\b", lower):
            return "ANOMALY_INVESTIGATION"
        if (
            (context.incident_id and re.search(r"^(why|what happened|explain|investigate)\b|\bthis incident\b|\broot cause\b", lower))
            or (
                context.facilities and context.start_date == context.end_date
                and re.search(r"\bwhat happened\b|\binvestigate\b|\bincident\b", lower)
            )
            or re.search(r"\bwhy did\b.*\b(?:restart|downtime|outage|incident)\b", lower)
            or re.search(r"\binc-\d+\b|\broot[- ]cause investigation\b", lower)
        ):
            return "INCIDENT_INVESTIGATION"
        return "STANDARD_ANALYTICS"
