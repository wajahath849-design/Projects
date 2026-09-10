from __future__ import annotations

import time
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from src.answer_generator import GroundedAnswerGenerator, OllamaGroundedAnswerGenerator
from src.advanced_chat import AdvancedAnalyticsChatService
from src.answer_validator import validate_answer_numbers
from src.action_safety import ActionSafetyPolicy
from src.config import settings
from src.conversation_context import ContextResolver, ConversationContext
from src.copilot_router import CopilotRouter
from src.database import connect_read_only, discover_schema
from src.decision_support import FacilityDecisionSupport, ScenarioEngine
from src.executor import SQLExecutor
from src.forecasting import (
    MetricForecaster,
    asks_trend_direction,
    detect_metric,
    detect_metrics,
    has_forecast_intent,
    resolve_target_year,
    supported_metric_names,
)
from src.logging_utils import log_event
from src.operations_briefing import OperationsBriefingEngine
from src.incident_engine import IncidentTimelineEngine, RootCauseInvestigationEngine
from src.incident_similarity import IncidentSimilarityEngine
from src.performance import PerformanceTrace
from src.question_analyzer import QuestionAnalyzer
from src.query_router import FastQueryRouter
from src.query_templates import QueryTemplateEngine
from src.retriever import Retriever
from src.risk_scoring import OperationsScoreEngine
from src.semantic_layer import SemanticLayer
from src.sql_generator import OllamaSQLGenerator, VerifiedExampleSQLGenerator
from src.sql_validator import SQLValidator
from src.visualizer import chart_spec


@dataclass
class PipelineResult:
    status: str
    question: str
    answer: str
    sql: str | None = None
    validation_status: str | None = None
    retrieved_context: list[dict] | None = None
    source_tables: list[str] | None = None
    frame: pd.DataFrame | None = None
    chart: dict | None = None
    execution_ms: float | None = None
    total_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    timings: dict[str, float] | None = None
    execution_path: str | None = None
    row_count: int | None = None
    cache_status: str = "not_implemented"
    llm_calls: int = 0
    parameters: list[object] | None = None
    analysis_mode: str | None = None
    diagnostic_confidence: str | None = None
    evidence_panel: dict[str, object] | None = None
    conversation_context: dict[str, object] | None = None


class AnalyticsPipeline:
    def __init__(self, generator=None, database_path: Path | str | None = None) -> None:
        initialization_started = time.perf_counter()
        self.database_path = Path(database_path or settings.database_path)
        self.schema = discover_schema(self.database_path)
        self.modules = self._available_modules()
        self.analyzer = QuestionAnalyzer(self.modules)
        self.fast_router = FastQueryRouter(settings.project_root / "analytics/business_glossary.yaml")
        self.templates = QueryTemplateEngine()
        self.retriever = Retriever(SemanticLayer(settings.project_root).build_chunks())
        self.generator = generator or self._default_generator()
        self.validator = SQLValidator(self.schema, settings.max_result_rows)
        self.executor = SQLExecutor(self.database_path, settings.sql_timeout_seconds, settings.max_result_rows)
        self.answerer = (
            OllamaGroundedAnswerGenerator(
                self.generator.client,
                self.generator.model,
                settings.ollama_keep_alive,
                settings.ollama_num_ctx,
                settings.ollama_answer_max_tokens,
            )
            if isinstance(self.generator, OllamaSQLGenerator)
            else GroundedAnswerGenerator()
        )
        self.forecaster = MetricForecaster(self.database_path)
        self.context_resolver = ContextResolver()
        self.copilot_router = CopilotRouter()
        self.action_policy = ActionSafetyPolicy()
        self.timeline_engine = IncidentTimelineEngine(self.database_path)
        self.investigation_engine = RootCauseInvestigationEngine(
            self.database_path, settings.project_root
        )
        self.similarity_engine = IncidentSimilarityEngine(self.database_path)
        self.scenario_engine = ScenarioEngine(self.database_path)
        self.decision_engine = FacilityDecisionSupport(
            self.database_path,
            settings.project_root / "analytics/decision_support_weights.yaml",
        )
        self.briefing_engine = OperationsBriefingEngine(
            self.database_path, settings.project_root
        )
        self.advanced_chat = AdvancedAnalyticsChatService(
            settings.project_root, self.database_path
        )
        self.initialization_ms = (time.perf_counter() - initialization_started) * 1000

    def _default_generator(self):
        if OllamaSQLGenerator.model_available(settings.ollama_host, settings.ollama_model):
            return OllamaSQLGenerator(
                settings.ollama_host,
                settings.ollama_model,
                keep_alive=settings.ollama_keep_alive,
                num_ctx=settings.ollama_num_ctx,
                max_tokens=settings.ollama_sql_max_tokens,
                timeout_seconds=settings.ollama_timeout_seconds,
            )
        return VerifiedExampleSQLGenerator()

    def operations_briefing(self, month: str | None = None):
        return self.briefing_engine.generate(month)

    def _available_modules(self) -> set[str]:
        required = {
            "energy": {"facilities", "power_metrics"},
            "server_performance": {"servers", "server_metrics"},
            "network": {"facilities", "network_metrics"},
            "reliability": {"facilities", "servers", "uptime_incidents"},
        }
        return {module for module, tables in required.items() if tables <= set(self.schema)}

    def ask(
        self,
        question: str,
        _allow_split: bool = True,
        upstream_timings: dict[str, float] | None = None,
        conversation_context: ConversationContext | dict | None = None,
        requested_mode: str | None = None,
    ) -> PipelineResult:
        request_started = time.perf_counter()
        trace = PerformanceTrace(upstream_timings)
        resolved_context = self.context_resolver.resolve(question, conversation_context)
        if requested_mode and requested_mode not in self.copilot_router.ALL_MODES:
            raise ValueError(f"Unsupported requested copilot mode: {requested_mode}")
        parts = self._split_questions(question) if _allow_split else []
        if len(parts) > 1:
            mode = "MULTIPLE"
            result = self._answer_multiple(
                question,
                parts,
                request_started,
                trace,
                resolved_context,
                requested_mode,
            )
        else:
            mode = requested_mode or self.copilot_router.route(question, resolved_context)
            analysis = self.analyzer.analyze(question)
            action_decision = self.action_policy.evaluate(question)
            if analysis.unsafe:
                result = self._ask(question, _allow_split, trace)
            elif action_decision.approval_required:
                result = self._stop(
                    question,
                    "approval_required",
                    self.action_policy.refusal(action_decision.action_category),
                    request_started,
                )
                result.analysis_mode = "HUMAN_APPROVAL_REQUIRED"
                result.validation_status = "no_action_executed"
                result.execution_path = "human_approval_gate"
                result.evidence_panel = {
                    "action_category": action_decision.action_category,
                    "action_executed": False,
                    "operator_authorization_required": True,
                }
            elif mode in self.copilot_router.EXTENSION_MODES:
                with trace.stage("advanced_analytics_ms"):
                    advanced = self.advanced_chat.answer(question, mode, resolved_context)
                result = PipelineResult(
                    advanced.status, question, advanced.answer,
                    validation_status=advanced.validation_status,
                    retrieved_context=advanced.evidence,
                    source_tables=advanced.sources,
                    frame=advanced.frame,
                    chart=advanced.chart,
                    execution_path=advanced.execution_path,
                    analysis_mode=mode,
                    diagnostic_confidence=advanced.confidence,
                    evidence_panel={"evidence": advanced.evidence},
                )
                if advanced.context_updates:
                    result.conversation_context = {
                        **resolved_context.to_dict(), **advanced.context_updates
                    }
            elif mode in self.copilot_router.ADVANCED_MODES:
                result = self._ask_copilot(question, mode, resolved_context, trace)
            else:
                result = self._ask(question, _allow_split, trace)
        internal_total_ms = (time.perf_counter() - request_started) * 1000
        upstream_total_ms = sum(max(0.0, float(value)) for value in (upstream_timings or {}).values())
        result.total_ms = internal_total_ms + upstream_total_ms
        result.timings = trace.snapshot()
        result.llm_calls = trace.llm_calls
        result.row_count = 0 if result.frame is None else len(result.frame)
        result.execution_path = result.execution_path or self._execution_path(result.status)
        result.analysis_mode = result.analysis_mode or self._analysis_mode(result, mode)
        final_context = ConversationContext.from_value(
            result.conversation_context or resolved_context
        )
        final_context = self.context_resolver.with_mode(final_context, result.analysis_mode)
        result.conversation_context = final_context.to_dict()
        self._log(result)
        return result

    def _ask(self, question: str, _allow_split: bool, trace: PerformanceTrace) -> PipelineResult:
        started = time.perf_counter()
        routing_started = time.perf_counter()
        routing_finished = False

        def finish_routing() -> None:
            nonlocal routing_finished
            if not routing_finished:
                trace.add_ms("routing_ms", (time.perf_counter() - routing_started) * 1000)
                routing_finished = True

        if _allow_split:
            parts = self._split_questions(question)
            if len(parts) > 1:
                finish_routing()
                return self._answer_multiple(question, parts, started, trace)
        analysis = self.analyzer.analyze(question)
        if analysis.unsafe:
            finish_routing()
            return self._stop(question, "blocked", "The request was blocked because it contains a database-changing instruction.", started)
        if analysis.ambiguous or analysis.clarification:
            finish_routing()
            return self._stop(question, "clarification", analysis.clarification or "Please clarify the requested metric.", started)

        latest_complete_year = self.forecaster.latest_complete_year()
        target_year = resolve_target_year(question, latest_complete_year)
        if target_year is not None:
            matched_metrics = detect_metrics(question)
            if len(matched_metrics) > 1:
                finish_routing()
                return self._forecast_multiple_metrics(
                    question, matched_metrics, target_year, analysis.facilities, started, trace
                )
            metric = detect_metric(question)
            if metric is None:
                names = ", ".join(supported_metric_names())
                if any(term in question.lower() for term in ("price", "cost", "expense", "tariff")):
                    finish_routing()
                    return self._stop(
                        question, "clarification",
                        "The database does not contain a historical price series for that item. "
                        "The only monetary time series currently available is Annual Cooling Cost; "
                        f"other supported forecasts are: {names}.", started,
                    )
                finish_routing()
                return self._stop(
                    question, "clarification",
                    f"Which forecast metric do you mean? Supported time-series metrics are: {names}.", started,
                )
            finish_routing()
            return self._forecast_metric(question, metric, target_year, analysis.facilities, started, trace)

        fast_route = self.fast_router.route(question, analysis, latest_complete_year)
        if fast_route.category == "DEFINITION":
            finish_routing()
            return PipelineResult(
                "knowledge",
                question,
                fast_route.definition_answer or "No definition was found.",
                validation_status="rag_grounded",
                retrieved_context=[{"kind": "business_glossary"}],
                source_tables=[],
                total_ms=(time.perf_counter() - started) * 1000,
                execution_path="fast_definition",
            )
        if fast_route.category != "AI":
            finish_routing()
            return self._fast_analytics(question, fast_route, started, trace)

        metric = detect_metric(question)
        historical_years = [year for year in analysis.years if year <= latest_complete_year]
        historical_language = bool(re.search(
            r"\b(compare|comparison|between|change|changed|difference|versus|vs\.?|from)\b",
            question.lower(),
        ))
        generic_money = bool(re.search(r"\b(price|expense|spend|bill)\b", question.lower()))
        if metric is not None and historical_years and (
            len(historical_years) > 1 or historical_language or generic_money
        ):
            matched_metrics = detect_metrics(question)
            finish_routing()
            return self._historical_metrics(
                question, matched_metrics or [metric], historical_years, analysis.facilities, started, trace
            )

        if metric is not None and asks_trend_direction(question):
            finish_routing()
            return self._forecast_direction(
                question, metric, analysis.facilities, latest_complete_year, started, trace
            )

        if has_forecast_intent(question):
            metric_text = metric.display_name if metric else "that metric"
            finish_routing()
            return self._stop(
                question, "clarification",
                f"Which future year should I use to forecast {metric_text}? "
                f"The latest complete data year is {latest_complete_year}; for example, ask for {latest_complete_year + 5}.",
                started,
            )

        if not analysis.relevant:
            finish_routing()
            return self._stop(question, "irrelevant", "Please ask about energy, servers, network performance, or reliability in the data-center dataset.", started)

        finish_routing()
        with trace.stage("rag_retrieval_ms"):
            retrieved = self.retriever.retrieve_for_sql(question, settings.rag_top_k)
            context = "\n\n".join(item.chunk.text for item in retrieved)
        if self._is_knowledge_question(question, analysis):
            with trace.stage("answer_generation_ms"):
                if isinstance(self.answerer, OllamaGroundedAnswerGenerator):
                    trace.count_llm_call()
                answer = self.answerer.answer_knowledge(question, context)
            result = PipelineResult(
                "knowledge", question, answer, validation_status="rag_grounded",
                retrieved_context=[
                    {"id": item.chunk.chunk_id, "score": round(item.score, 4), **item.chunk.metadata}
                    for item in retrieved
                ],
                source_tables=sorted({
                    item.chunk.metadata["table"] for item in retrieved
                    if "table" in item.chunk.metadata
                }),
                total_ms=(time.perf_counter() - started) * 1000,
                execution_path="ai_definition",
            )
            return result
        try:
            with trace.stage("llm_sql_generation_ms"):
                if isinstance(self.generator, OllamaSQLGenerator):
                    trace.count_llm_call()
                generated = self.generator.generate(question, context)
        except Exception as error:
            return self._stop(question, "generation_error", str(error), started)
        with trace.stage("sql_validation_ms"):
            validation = self.validator.validate(generated.sql)
        if not validation.valid:
            return self._stop(question, "validation_error", validation.error or "SQL validation failed", started, generated.sql)
        try:
            with trace.stage("database_execution_ms"):
                execution = self.executor.execute(validation.sql)
        except Exception as error:
            return self._stop(question, "execution_error", f"The validated query could not run: {error}", started, validation.sql)

        with trace.stage("answer_generation_ms"):
            if (
                isinstance(self.answerer, OllamaGroundedAnswerGenerator)
                and self.answerer.will_use_llm(question, execution.frame)
            ):
                trace.count_llm_call()
            answer = self.answerer.generate(question, execution.frame)
            faithful, unsupported = validate_answer_numbers(answer, execution.frame, question)
            if not faithful:
                answer = f"The result table is authoritative; answer rendering found unsupported values: {unsupported}."
        sources = sorted({name for name in self.schema if name.lower() in validation.sql.lower()})
        with trace.stage("chart_generation_ms"):
            selected_chart = chart_spec(execution.frame)
        result = PipelineResult(
            "ok", question, answer, validation.sql, "valid",
            [{"id": item.chunk.chunk_id, "score": round(item.score, 4), **item.chunk.metadata} for item in retrieved],
            sources, execution.frame, selected_chart, execution.execution_ms,
            (time.perf_counter() - started) * 1000, generated.input_tokens, generated.output_tokens,
            execution_path="ai_text_to_sql",
        )
        return result

    def _ask_copilot(
        self,
        question: str,
        mode: str,
        context: ConversationContext,
        trace: PerformanceTrace,
    ) -> PipelineResult:
        started = time.perf_counter()
        if mode == "SCENARIO":
            metric = detect_metric(question)
            percent = re.search(r"(-?\d+(?:\.\d+)?)\s*%", question)
            if metric is None or percent is None:
                return self._stop(
                    question, "clarification",
                    "Please specify both a supported metric and percentage, for example: What if Frankfurt PUE improves by 10%?",
                    started,
                )
            change_pct = abs(float(percent.group(1)))
            lower = question.lower()
            if re.search(r"\b(reduce|reduces|reduced|decrease|decreases|decreased|lower)\b", lower):
                change_pct = -change_pct
            elif re.search(r"\b(increase|increases|increased|raise|raises|raised|higher)\b", lower):
                change_pct = change_pct
            elif re.search(
                r"\b(improve|improves|improved|upgrade|upgrades|upgraded|efficien(?:cy|t))\b",
                lower,
            ):
                preferred = self.scenario_engine.preferred_direction(metric.key)
                change_pct = change_pct if preferred == "higher" else -change_pct
            elif float(percent.group(1)) < 0:
                change_pct = float(percent.group(1))
            years = [int(value) for value in re.findall(r"\b(20\d{2})\b", question)]
            try:
                with trace.stage("forecast_ms" if years and max(years) > self.forecaster.latest_complete_year() else "database_execution_ms"):
                    scenario = self.scenario_engine.run(
                        metric.key,
                        change_pct,
                        list(context.facilities) or None,
                        max(years) if years else None,
                    )
            except Exception as error:
                return self._stop(question, "scenario_error", f"The scenario could not be calculated: {error}", started)
            return PipelineResult(
                "scenario", question, scenario.answer,
                validation_status="governed_scenario",
                retrieved_context=scenario.evidence,
                source_tables=sorted({str(item["source"]) for item in scenario.evidence}),
                frame=scenario.frame,
                chart={"kind": "bar", "x": "facility_name", "y": "scenario_value"},
                total_ms=(time.perf_counter() - started) * 1000,
                execution_path="scenario",
                analysis_mode=mode,
                evidence_panel={
                    "historical_or_forecast_baseline": scenario.evidence,
                    "scenario_assumption": scenario.assumption,
                    "calculated_results": scenario.frame.to_dict("records"),
                },
            )

        if mode == "DECISION_SUPPORT":
            try:
                with trace.stage("database_execution_ms"):
                    decision = self.decision_engine.rank_efficiency_upgrades()
            except Exception as error:
                return self._stop(question, "decision_error", f"The priority analysis could not be calculated: {error}", started)
            return PipelineResult(
                "decision_support", question, decision.answer,
                validation_status="governed_weights",
                retrieved_context=decision.evidence,
                source_tables=["agg_facility_yearly", "detected_anomalies", "facilities", "servers"],
                frame=decision.ranking,
                chart={"kind": "bar", "x": "facility_name", "y": "priority_score"},
                total_ms=(time.perf_counter() - started) * 1000,
                execution_path="decision_support",
                analysis_mode=mode,
                diagnostic_confidence=decision.decision_confidence,
                evidence_panel={
                    "metrics_used": list(self.decision_engine.config["weights"]),
                    "weights": decision.evidence,
                    "ranked_results": decision.ranking.to_dict("records"),
                },
            )

        if mode in {"HEALTH_ASSESSMENT", "PREDICTIVE_MAINTENANCE"}:
            try:
                with trace.stage("database_execution_ms"):
                    with connect_read_only(self.database_path) as connection:
                        scores = OperationsScoreEngine(
                            connection,
                            settings.project_root / "analytics/health_score_weights.yaml",
                        ).score()
            except Exception as error:
                return self._stop(question, "score_error", f"The governed score could not be calculated: {error}", started)
            if mode == "HEALTH_ASSESSMENT":
                frame = scores.facility_health.copy()
                if context.facilities:
                    with connect_read_only(self.database_path) as connection:
                        ids = {
                            row["facility_id"] for row in connection.execute(
                                f"SELECT facility_id FROM facilities WHERE facility_name IN ({','.join('?' for _ in context.facilities)})",
                                context.facilities,
                            )
                        }
                    frame = frame[frame["facility_id"].isin(ids)]
                if frame.empty:
                    return self._stop(question, "clarification", "No facility matched the health-score request.", started)
                ranked = frame.sort_values("health_score", ascending=False)
                answer = (
                    "The governed facility health scores are: "
                    + "; ".join(
                        f"{row.facility_id} {row.health_score:.2f}/100"
                        for row in ranked.itertuples()
                    )
                    + ". Each result uses fixed versioned weights and is a relative triage indicator, not a safety certification."
                )
                return PipelineResult(
                    "health_assessment", question, answer,
                    validation_status="governed_weights",
                    retrieved_context=[scores.metadata],
                    source_tables=["agg_facility_yearly", "detected_anomalies", "uptime_incidents"],
                    frame=ranked,
                    chart={"kind": "bar", "x": "facility_id", "y": "health_score"},
                    total_ms=(time.perf_counter() - started) * 1000,
                    execution_path="health_score",
                    analysis_mode=mode,
                    evidence_panel={
                        "component_scores": ranked.to_dict("records"),
                        "weights": scores.metadata["health_weights"],
                        "source_year": scores.metadata["latest_complete_year"],
                    },
                )
            frame = scores.server_risk.copy()
            updated_context = context.to_dict()
            server_id = context.server_id
            if not server_id and context.incident_id:
                incident = self.timeline_engine.build(context.incident_id).incident
                server_id = incident["server_id"]
                updated_context.update({
                    "server_id": server_id,
                    "facilities": (incident["facility_name"],),
                })
            if server_id:
                frame = frame[frame["server_id"].str.upper() == server_id.upper()]
            elif context.facilities:
                with connect_read_only(self.database_path) as connection:
                    ids = {
                        row["facility_id"] for row in connection.execute(
                            f"SELECT facility_id FROM facilities WHERE facility_name IN ({','.join('?' for _ in context.facilities)})",
                            context.facilities,
                        )
                    }
                frame = frame[frame["facility_id"].isin(ids)].nlargest(10, "risk_score")
            else:
                frame = frame.nlargest(10, "risk_score")
            if frame.empty:
                return self._stop(question, "clarification", "No server matched the predictive-maintenance request.", started)
            top = frame.iloc[0]
            answer = (
                f"The highest matching seven-day screening risk is {top['server_id']}: "
                f"{top['risk_level']} ({top['risk_score']:.2f}/100). {top['recommendation']} "
                "This explainable score prioritizes inspection; it is not a guaranteed failure prediction."
            )
            return PipelineResult(
                "predictive_maintenance", question, answer,
                validation_status="governed_risk_rules",
                retrieved_context=[scores.metadata],
                source_tables=["servers", "server_metrics", "system_logs", "uptime_incidents", "maintenance_actions"],
                frame=frame,
                total_ms=(time.perf_counter() - started) * 1000,
                execution_path="predictive_maintenance",
                analysis_mode=mode,
                evidence_panel={
                    "risk_signals": frame.to_dict("records"),
                    "method_version": scores.metadata["risk_method_version"],
                    "score_date": scores.metadata["score_date"],
                },
                conversation_context=updated_context,
            )

        if mode == "ANOMALY_INVESTIGATION":
            clauses, parameters = ["1=1"], []
            if context.facilities:
                placeholders = ",".join("?" for _ in context.facilities)
                clauses.append(
                    f"facility_id IN (SELECT facility_id FROM facilities WHERE facility_name IN ({placeholders}))"
                )
                parameters.extend(context.facilities)
            if context.start_date:
                clauses.append("date(timestamp) >= date(?)")
                parameters.append(context.start_date)
            if context.end_date:
                clauses.append("date(timestamp) <= date(?)")
                parameters.append(context.end_date)
            anomaly_metric = {
                "average_pue": "pue",
                "server_network_utilization_pct": "network_utilization_pct",
            }.get(context.metric_key or "", context.metric_key)
            if anomaly_metric:
                clauses.append("metric_name = ?")
                parameters.append(anomaly_metric)
            sql = f"""SELECT * FROM detected_anomalies
            WHERE {' AND '.join(clauses)}
            ORDER BY anomaly_score DESC, timestamp DESC LIMIT 1000"""
            try:
                with trace.stage("database_execution_ms"):
                    execution = self.executor.execute(sql, tuple(parameters))
            except Exception as error:
                return self._stop(question, "execution_error", f"Anomaly search failed: {error}", started, sql)
            frame = execution.frame
            answer = (
                f"I found {len(frame)} stored anomaly record(s) in the requested scope. "
                + (
                    f"The strongest is {frame.iloc[0]['metric_name']} at {frame.iloc[0]['facility_id']} "
                    f"on {frame.iloc[0]['timestamp']} with {frame.iloc[0]['severity']} severity and score "
                    f"{frame.iloc[0]['anomaly_score']:.2f}."
                    if len(frame) else "No observation crossed its governed seasonal-IQR bounds."
                )
                + " Anomalies are statistical triage signals, not root-cause conclusions."
            )
            return PipelineResult(
                "anomaly_investigation", question, answer, sql, "valid",
                [{"kind": "anomaly_method", "method": "seasonal_iqr"}],
                ["detected_anomalies", "facilities"], frame,
                chart_spec(frame), execution.execution_ms,
                (time.perf_counter() - started) * 1000,
                execution_path="anomaly_investigation",
                analysis_mode=mode,
                evidence_panel={
                    "anomalies": frame.to_dict("records"),
                    "generated_sql": sql,
                    "time_window": {"start": context.start_date, "end": context.end_date},
                },
                parameters=parameters,
            )

        prefer_related = bool(
            mode == "MAINTENANCE_RECOMMENDATION"
            and context.related_incident_id
            and re.search(r"\bclosest\b|\bsimilar\b|\bprevious\b", question.lower())
        )
        incident, clarification = self._resolve_incident(context, prefer_related=prefer_related)
        if incident is None and mode in {
            "INCIDENT_INVESTIGATION", "EVIDENCE_REVIEW", "TIMELINE_FIRST_EVENT",
            "LOG_SEARCH", "MAINTENANCE_RECOMMENDATION",
        }:
            return self._stop(question, "clarification", clarification or "Which incident should I use?", started)

        if mode in {
            "INCIDENT_INVESTIGATION", "EVIDENCE_REVIEW", "TIMELINE_FIRST_EVENT",
            "LOG_SEARCH", "MAINTENANCE_RECOMMENDATION",
        }:
            incident_id = incident["incident_id"]
            updated_context = context.to_dict()
            if prefer_related:
                updated_context["related_incident_id"] = incident_id
            else:
                updated_context.update({
                    "incident_id": incident_id,
                    "server_id": incident["server_id"],
                    "facilities": (incident["facility_name"],),
                    "start_date": incident["start_time"][:10],
                    "end_date": incident["end_time"][:10],
                })
            with trace.stage("database_execution_ms"):
                investigation = self.investigation_engine.investigate(incident_id)
            panel = self._investigation_evidence_panel(investigation)
            if mode == "INCIDENT_INVESTIGATION":
                frame = pd.DataFrame([asdict(event) for event in investigation.timeline.events])
                return PipelineResult(
                    "incident_investigation", question, investigation.answer,
                    validation_status="evidence_grounded",
                    retrieved_context=investigation.evidence["runbooks"],
                    source_tables=[
                        "uptime_incidents", "system_logs", "alerts", "maintenance_actions",
                        "power_metrics", "network_metrics", "server_metrics", "detected_anomalies",
                    ],
                    frame=frame,
                    total_ms=(time.perf_counter() - started) * 1000,
                    execution_path="incident_investigation",
                    analysis_mode=mode,
                    diagnostic_confidence=investigation.diagnostic_confidence,
                    evidence_panel=panel,
                    conversation_context=updated_context,
                )
            if mode == "EVIDENCE_REVIEW":
                frame = pd.DataFrame([asdict(event) for event in investigation.timeline.events])
                evidence = investigation.evidence
                answer = (
                    f"Here is the sourced evidence for {incident_id}: "
                    f"{len(evidence['metrics'])} metric observation(s), {len(evidence['logs'])} log event(s), "
                    f"{len(evidence['alerts'])} alert(s), {len(evidence['anomalies'])} stored anomaly record(s), "
                    f"and {len(evidence['maintenance'])} maintenance record(s). "
                    "Every item retains its source table and record identifier. Together they support the "
                    f"recorded {investigation.recorded_root_cause} category, but do not prove a more specific cause."
                )
                return PipelineResult(
                    "evidence_review", question, answer,
                    validation_status="evidence_grounded",
                    retrieved_context=investigation.evidence["runbooks"],
                    source_tables=[
                        "uptime_incidents", "system_logs", "alerts", "maintenance_actions",
                        "power_metrics", "network_metrics", "server_metrics", "detected_anomalies",
                    ],
                    frame=frame,
                    total_ms=(time.perf_counter() - started) * 1000,
                    execution_path="evidence_review", analysis_mode=mode,
                    diagnostic_confidence=investigation.diagnostic_confidence,
                    evidence_panel=panel, conversation_context=updated_context,
                )
            if mode == "TIMELINE_FIRST_EVENT":
                abnormal = [
                    event for event in investigation.timeline.events
                    if event.source_type == "alert"
                    or (
                        event.source_type == "log"
                        and str(event.details.get("log_level", "")).upper()
                        in {"WARNING", "ERROR", "CRITICAL"}
                    )
                ]
                first_event = abnormal[0] if abnormal else investigation.timeline.events[0]
                frame = pd.DataFrame([asdict(event) for event in investigation.timeline.events])
                answer = (
                    f"The earliest minute-precision abnormal signal for {incident_id} was at "
                    f"{first_event.timestamp}: {first_event.summary} "
                    f"Source: {first_event.source_table}/{first_event.source_record_id}. "
                    "This establishes observed sequence, not causation."
                )
                panel["first_abnormal_signal"] = asdict(first_event)
                return PipelineResult(
                    "timeline_first_event", question, answer,
                    validation_status="evidence_grounded",
                    source_tables=[
                        "uptime_incidents", "system_logs", "alerts", "maintenance_actions",
                        "power_metrics", "network_metrics", "server_metrics",
                    ],
                    frame=frame,
                    total_ms=(time.perf_counter() - started) * 1000,
                    execution_path="timeline_first_event", analysis_mode=mode,
                    diagnostic_confidence=investigation.diagnostic_confidence,
                    evidence_panel=panel, conversation_context=updated_context,
                )
            if mode == "LOG_SEARCH":
                logs = investigation.evidence["logs"]
                frame = pd.DataFrame(logs)
                answer = (
                    f"I found {len(logs)} sourced log event(s) for {incident_id} between "
                    f"{investigation.timeline.window_start} and {investigation.timeline.window_end}. "
                    "Each row retains its event code, timestamp, source table, and record identifier."
                )
                return PipelineResult(
                    "log_search", question, answer,
                    validation_status="evidence_grounded",
                    retrieved_context=[], source_tables=["system_logs", "uptime_incidents"],
                    frame=frame, total_ms=(time.perf_counter() - started) * 1000,
                    execution_path="log_search", analysis_mode=mode,
                    evidence_panel=panel, conversation_context=updated_context,
                )
            maintenance = investigation.evidence["maintenance"]
            if prefer_related and maintenance:
                details = maintenance[-1]["details"]
                answer = (
                    f"The closest historical case, {incident_id}, was recorded as resolved after "
                    f"{details['action_type']}: {details['description']} Result: {details['result']} "
                    "This is a sourced synthetic maintenance record, not an instruction to repeat the action. "
                    "A qualified operator must assess and authorize any current change."
                )
                validation_status = "maintenance_history_grounded"
            else:
                answer = (
                    f"For {incident_id}, the reviewed checks are:\n\n"
                    + "\n".join(f"- {item}" for item in investigation.recommended_checks)
                    + "\n\nThese are inspection recommendations from the reviewed runbook. "
                    "A qualified operator must authorize any change."
                )
                validation_status = "runbook_grounded"
            return PipelineResult(
                "maintenance_recommendation", question, answer,
                validation_status=validation_status,
                retrieved_context=investigation.evidence["runbooks"],
                source_tables=["maintenance_actions", "uptime_incidents"],
                total_ms=(time.perf_counter() - started) * 1000,
                execution_path="maintenance_recommendation", analysis_mode=mode,
                diagnostic_confidence=investigation.diagnostic_confidence,
                evidence_panel=panel, conversation_context=updated_context,
            )

        if mode == "SIMILAR_INCIDENT":
            if context.incident_id:
                try:
                    with trace.stage("database_execution_ms"):
                        matches = self.similarity_engine.retrieve(context.incident_id, 5)
                except Exception as error:
                    return self._stop(question, "similarity_error", str(error), started)
            else:
                codes = re.findall(r"\b[A-Z]{3,}(?:_[A-Z]+)+\b", question.upper())
                if not codes:
                    return self._stop(
                        question, "clarification",
                        "Which incident or event code should I compare? For example: Have we seen TEMP_HIGH and COOL_FLOW_LOW before?",
                        started,
                    )
                with trace.stage("database_execution_ms"):
                    matches = self.similarity_engine.search_by_signals(log_codes=codes, top_k=5)
            rows = [{
                "incident_id": item.incident.incident_id,
                "facility_name": item.incident.facility_name,
                "start_time": item.incident.start_time,
                "severity": item.incident.severity,
                "recorded_root_cause": item.incident.root_cause,
                "similarity_pct": round(item.similarity * 100, 1),
                "resolution": item.incident.resolution,
                "score_breakdown": item.score_breakdown,
            } for item in matches]
            if not rows:
                return self._stop(
                    question, "no_matches", "No historical incident met the similarity search scope.", started
                )
            frame = pd.DataFrame(rows)
            answer = (
                f"The closest historical match is {rows[0]['incident_id']} at {rows[0]['facility_name']} "
                f"with {rows[0]['similarity_pct']:.1f}% weighted similarity. Its recorded category is "
                f"{rows[0]['recorded_root_cause']}. Similarity supports investigation; it does not prove the same cause."
            )
            updated_context = context.to_dict()
            updated_context["related_incident_id"] = rows[0]["incident_id"]
            return PipelineResult(
                "similar_incident", question, answer,
                validation_status="weighted_similarity",
                retrieved_context=[{"weights": self.similarity_engine.WEIGHTS}],
                source_tables=["uptime_incidents", "system_logs", "alerts", "detected_anomalies", "maintenance_actions"],
                frame=frame, total_ms=(time.perf_counter() - started) * 1000,
                execution_path="similar_incident", analysis_mode=mode,
                evidence_panel={
                    "similar_incidents": rows,
                    "similarity_weights": self.similarity_engine.WEIGHTS,
                },
                conversation_context=updated_context,
            )
        return self._stop(question, "routing_error", f"Unsupported copilot mode: {mode}", started)

    def _resolve_incident(
        self, context: ConversationContext, *, prefer_related: bool = False
    ) -> tuple[dict | None, str | None]:
        incident_id = context.related_incident_id if prefer_related else context.incident_id
        if incident_id:
            try:
                timeline = self.timeline_engine.build(incident_id)
                return timeline.incident, None
            except LookupError as error:
                return None, str(error)
        exact_date = (
            context.start_date
            if context.start_date and context.start_date == context.end_date
            else None
        )
        matches = self.timeline_engine.find_incidents(
            facility=context.facilities[0] if len(context.facilities) == 1 else None,
            date=exact_date,
            server_id=context.server_id,
            limit=20,
        )
        if len(matches) == 1:
            return matches[0], None
        if not matches:
            return None, "No incident matched the current facility, server, and date context."
        choices = ", ".join(
            f"{item['incident_id']} ({item['facility_name']}, {item['start_time']})"
            for item in matches[:5]
        )
        return None, f"I found multiple matching incidents. Which incident do you mean: {choices}?"

    @staticmethod
    def _investigation_evidence_panel(investigation) -> dict[str, object]:
        return {
            "metrics_used": investigation.evidence["metrics"],
            "logs_used": investigation.evidence["logs"],
            "alerts_used": investigation.evidence["alerts"],
            "incidents_used": investigation.evidence["incidents"],
            "runbooks_used": investigation.evidence["runbooks"],
            "similar_incidents": investigation.evidence["similar_incidents"],
            "maintenance_history": investigation.evidence["maintenance"],
            "anomalies_used": investigation.evidence["anomalies"],
            "generated_sql": None,
            "time_window": {
                "start": investigation.timeline.window_start,
                "end": investigation.timeline.window_end,
            },
            "confidence": {
                "level": investigation.diagnostic_confidence,
                "score": investigation.confidence_score,
                "maximum": 9,
                "breakdown": investigation.confidence_breakdown,
            },
            "likely_area": investigation.likely_area,
            "recommended_checks": investigation.recommended_checks,
        }

    def _fast_analytics(self, question, decision, started, trace) -> PipelineResult:
        try:
            template = self.templates.build(decision)
        except Exception as error:
            return self._stop(
                question, "template_error", f"The fast analytical route could not be built: {error}", started
            )
        with trace.stage("sql_validation_ms"):
            validation = self.validator.validate(template.sql)
        if not validation.valid:
            return self._stop(
                question, "validation_error", validation.error or "SQL validation failed", started, template.sql
            )
        try:
            with trace.stage("database_execution_ms"):
                execution = self.executor.execute(validation.sql, template.parameters)
        except Exception as error:
            return self._stop(
                question, "execution_error", f"The fast analytical query could not run: {error}",
                started, validation.sql,
            )
        with trace.stage("answer_generation_ms"):
            answer = self.templates.answer(template, execution.frame)
        with trace.stage("chart_generation_ms"):
            selected_chart = chart_spec(execution.frame)
        path = {
            "SIMPLE_KPI": "fast_kpi",
            "COMPARISON": "fast_comparison",
            "TREND": "fast_trend",
            "RANKING": "fast_ranking",
        }[decision.category]
        return PipelineResult(
            "historical" if decision.category in {"COMPARISON", "TREND"} else "ok",
            question,
            answer,
            validation.sql,
            "valid",
            [{"kind": "fast_route", "category": decision.category, "metric": decision.metric_key}],
            ["agg_facility_yearly", "facilities"],
            execution.frame,
            selected_chart,
            execution.execution_ms,
            (time.perf_counter() - started) * 1000,
            execution_path=path,
            parameters=list(template.parameters),
        )

    @staticmethod
    def _is_knowledge_question(question: str, analysis) -> bool:
        lower = question.lower().strip()
        explicit_definition = bool(re.search(
            r"^(what (?:is|are|does)|explain|define|meaning of|how (?:is|are).+calculated)",
            lower,
        ))
        short_metric_question = len(lower.split()) <= 4 and detect_metric(lower) is not None
        data_request_words = bool(re.search(
            r"\b(highest|lowest|average|total|sum|count|compare|between|by facility|which facility|show|list)\b",
            lower,
        ))
        return not analysis.years and (explicit_definition or short_metric_question) and not data_request_words

    @staticmethod
    def _split_questions(question: str) -> list[str]:
        parts = [part.strip(" \t\r\n?.;") for part in re.split(r"\?+|;+|\r?\n+", question)]
        return [
            part for part in parts
            if len(part.split()) >= 2 or detect_metric(part) is not None or re.fullmatch(r"20\d{2}", part)
        ]

    def _answer_multiple(
        self,
        original: str,
        questions: list[str],
        started: float,
        trace: PerformanceTrace,
        initial_context: ConversationContext | dict | None = None,
        requested_mode: str | None = None,
    ) -> PipelineResult:
        # Auto-route each part independently while carrying only structured state forward.
        # A manual mode applies to a single prompt, not indiscriminately to every part.
        del requested_mode
        current_context = ConversationContext.from_value(initial_context)
        results = []
        for question in questions:
            child = self.ask(
                question,
                _allow_split=False,
                conversation_context=current_context,
            )
            results.append(child)
            current_context = ConversationContext.from_value(
                child.conversation_context or current_context
            )
        for child in results:
            trace.add_trace(child.timings, child.llm_calls)
        answer = "\n\n".join(
            f"**{index}. {question}**\n\n{result.answer}"
            for index, (question, result) in enumerate(zip(questions, results), start=1)
        )
        frames = []
        for index, result in enumerate(results, start=1):
            if result.frame is not None:
                frame = result.frame.copy()
                frame.insert(0, "question_number", index)
                frames.append(frame)
        statuses = {result.status for result in results}
        successful = {
            "ok", "forecast", "forecast_direction", "historical", "knowledge",
            "scenario", "decision_support", "health_assessment", "predictive_maintenance",
            "anomaly_investigation", "incident_investigation", "log_search",
            "similar_incident", "maintenance_recommendation", "evidence_review",
            "timeline_first_event",
            "cost_analysis", "cost_forecast", "carbon_analysis", "carbon_forecast",
            "efficiency_scenario", "correlation_analysis", "lead_lag_analysis",
            "intervention_analysis", "impact_analysis", "realtime_status",
            "realtime_metric", "realtime_anomaly", "realtime_incident",
            "multi_agent_investigation",
        }
        combined_status = "multi_ok" if statuses <= successful else "multi_partial"
        result = PipelineResult(
            combined_status,
            original,
            answer,
            validation_status="multiple_results",
            retrieved_context=[
                {"question": question, "status": item.status}
                for question, item in zip(questions, results)
            ],
            source_tables=sorted({table for item in results for table in (item.source_tables or [])}),
            frame=pd.concat(frames, ignore_index=True, sort=False) if frames else None,
            chart=None,
            execution_ms=sum(item.execution_ms or 0 for item in results),
            total_ms=(time.perf_counter() - started) * 1000,
            input_tokens=sum(item.input_tokens or 0 for item in results) or None,
            output_tokens=sum(item.output_tokens or 0 for item in results) or None,
            execution_path="multiple",
            analysis_mode="MULTIPLE",
            conversation_context=current_context.to_dict(),
        )
        return result

    def _historical_metrics(self, question, metrics, years, facilities, started, trace):
        outputs = []
        frames = []
        sql_statements = []
        sources = {"facilities"}
        evidence = []
        for metric in metrics:
            try:
                with trace.stage("database_execution_ms"):
                    frame, sql = self.forecaster.historical(metric, years, facilities or None)
            except Exception as error:
                return self._stop(
                    question, "historical_error",
                    f"The historical {metric.display_name} comparison could not be calculated: {error}",
                    started,
                )
            frames.append(frame)
            sql_statements.append(sql)
            sources.add(metric.table)
            evidence.append({"kind": "historical_metric", "metric": metric.key, "years": years})

            answer_started = time.perf_counter()
            metric_sections = []
            for facility_name, group in frame.groupby("facility_name", sort=False):
                group = group.sort_values("year")
                values = ", ".join(
                    f"{int(row.year)}: {float(row.value):,.4f} {metric.unit}"
                    for row in group.itertuples()
                )
                comparison = ""
                if len(group) > 1:
                    first = group.iloc[0]
                    last = group.iloc[-1]
                    change = float(last["value"] - first["value"])
                    direction = "increased" if change > 0 else "decreased" if change < 0 else "was unchanged"
                    if float(first["value"]) != 0:
                        percent = abs(change / float(first["value"]) * 100)
                        comparison = (
                            f" From {int(first['year'])} to {int(last['year'])}, it {direction} "
                            f"by {abs(change):,.4f} {metric.unit} ({percent:.2f}%)."
                        )
                    else:
                        comparison = (
                            f" From {int(first['year'])} to {int(last['year'])}, it {direction} "
                            f"by {abs(change):,.4f} {metric.unit}."
                        )
                metric_sections.append(f"- **{facility_name}:** {values}.{comparison}")
            outputs.append(f"**{metric.display_name}**\n\n" + "\n".join(metric_sections))
            trace.add_ms("answer_generation_ms", (time.perf_counter() - answer_started) * 1000)

        combined = pd.concat(frames, ignore_index=True, sort=False)
        chart_started = time.perf_counter()
        selected_chart = {"kind": "line", "x": "year", "y": "value"} if len(metrics) == 1 else None
        trace.add_ms("chart_generation_ms", (time.perf_counter() - chart_started) * 1000)
        result = PipelineResult(
            "historical",
            question,
            "Here is the comparison from the current database:\n\n" + "\n\n".join(outputs),
            sql_statements[0] if len(sql_statements) == 1 else None,
            "historical_metric",
            evidence,
            sorted(sources),
            combined,
            selected_chart,
            None,
            (time.perf_counter() - started) * 1000,
            execution_path="deterministic_historical",
        )
        return result

    def _forecast_direction(self, question, metric, facilities, latest_complete_year, started, trace):
        try:
            with trace.stage("forecast_ms"):
                forecast = self.forecaster.forecast(metric, latest_complete_year + 1, facilities or None)
        except Exception as error:
            return self._stop(
                question, "forecast_error", f"The trend could not be calculated: {error}", started
            )

        answer_started = time.perf_counter()
        summaries = []
        for row in forecast.frame.itertuples():
            trend = float(row.trend_per_year)
            if abs(trend) < 1e-9:
                direction = "approximately stable"
            elif trend > 0:
                direction = "increasing"
            else:
                direction = "decreasing"
            confidence = (
                "The fitted trend is reasonably consistent with the history."
                if float(row.r_squared) >= 0.5
                else "The trend fit is weak, so the direction is uncertain."
            )
            summaries.append(
                f"- **{row.facility_name}:** {direction}, with a fitted change of "
                f"{trend:,.4f} {metric.unit} per year (R-squared {float(row.r_squared):.3f}). "
                f"{confidence}"
            )
        answer = (
            f"Based on the {forecast.training_start_year}-{forecast.training_end_year} database history, "
            f"the linear direction for {metric.display_name} is:\n\n" + "\n".join(summaries) +
            "\n\nThis describes a historical statistical trend, not a guaranteed future outcome."
        )
        trace.add_ms("answer_generation_ms", (time.perf_counter() - answer_started) * 1000)
        result = PipelineResult(
            "forecast_direction", question, answer, forecast.source_sql, "forecast_model",
            [{"kind": "forecast_method", "method": "annual_linear_trend", "metric": metric.key}],
            ["facilities", metric.table], forecast.frame, None, forecast.execution_ms,
            (time.perf_counter() - started) * 1000,
            execution_path="forecast",
        )
        return result

    def _forecast_multiple_metrics(self, question, metrics, target_year, facilities, started, trace):
        outputs = []
        frames = []
        sources = {"facilities"}
        evidence = []
        for metric in metrics:
            try:
                with trace.stage("forecast_ms"):
                    forecast = self.forecaster.forecast(metric, target_year, facilities or None)
            except Exception as error:
                return self._stop(
                    question, "forecast_error",
                    f"The {metric.display_name} forecast could not be calculated: {error}", started,
                )
            answer_started = time.perf_counter()
            row = forecast.frame.iloc[0]
            scope = row["facility_name"]
            caveat = " — low confidence" if float(row["r_squared"]) < 0.5 else ""
            outputs.append(
                f"- **{metric.display_name} ({scope}):** {row['predicted_value']:.4f} {metric.unit} "
                f"(95% interval {row['lower_95']:.4f}–{row['upper_95']:.4f}, "
                f"backtest MAE {row['backtest_mae']:.4f}){caveat}"
            )
            frames.append(forecast.frame)
            sources.add(metric.table)
            evidence.append({
                "kind": "forecast_method", "metric": metric.key,
                "method": "annual_linear_trend", "r_squared": float(row["r_squared"]),
                "backtest_mae": float(row["backtest_mae"]),
            })
            trace.add_ms("answer_generation_ms", (time.perf_counter() - answer_started) * 1000)
        answer = (
            f"The {target_year} multi-metric forecast is:\n\n" + "\n".join(outputs) +
            "\n\nThese are projections from synthetic historical observations, not guarantees."
        )
        result = PipelineResult(
            "forecast", question, answer, validation_status="forecast_model",
            retrieved_context=evidence, source_tables=sorted(sources),
            frame=pd.concat(frames, ignore_index=True, sort=False), chart=None,
            execution_ms=None, total_ms=(time.perf_counter() - started) * 1000,
            execution_path="forecast",
        )
        return result

    def _forecast_metric(
        self, question, metric, target_year: int, facilities: list[str], started: float,
        trace: PerformanceTrace,
    ) -> PipelineResult:
        try:
            with trace.stage("forecast_ms"):
                forecast = self.forecaster.forecast(metric, target_year, facilities or None)
        except Exception as error:
            return self._stop(question, "forecast_error", f"The forecast could not be calculated: {error}", started)
        answer_started = time.perf_counter()
        if facilities:
            row = forecast.frame.iloc[0]
            answer = (
                f"The {target_year} forecast for {row['facility_name']} is {metric.display_name} "
                f"{row['predicted_value']:.4f} {metric.unit} "
                f"(95% prediction interval {row['lower_95']:.4f}–{row['upper_95']:.4f})."
            )
        else:
            row = forecast.frame.iloc[0]
            answer = (
                f"The fleet-wide {target_year} forecast for {metric.display_name} is "
                f"{row['predicted_value']:.4f} {metric.unit} "
                f"(95% prediction interval {row['lower_95']:.4f}–{row['upper_95']:.4f}). "
                "Facility-level forecasts are shown in the table."
            )
        answer += (
            f" This is a linear-trend projection trained on {forecast.training_start_year}–"
            f"{forecast.training_end_year} synthetic observations, not an observed value or guarantee."
        )
        if float(row["r_squared"]) < 0.5:
            answer += " The historical linear trend is weak, so this estimate has low confidence and should be treated cautiously."
        trace.add_ms("answer_generation_ms", (time.perf_counter() - answer_started) * 1000)
        result = PipelineResult(
            "forecast", question, answer, forecast.source_sql, "forecast_model",
            [{"kind": "forecast_method", "method": "annual_linear_trend", "interval": "approximate_95_prediction_interval", "metric": metric.key}],
            ["facilities", metric.table], forecast.frame,
            {"kind": "bar", "x": "facility_name", "y": "predicted_value"},
            forecast.execution_ms, (time.perf_counter() - started) * 1000,
            execution_path="forecast",
        )
        return result

    def _stop(self, question, status, answer, started, sql=None):
        return PipelineResult(status, question, answer, sql=sql, total_ms=(time.perf_counter() - started) * 1000)

    @staticmethod
    def _execution_path(status: str) -> str:
        if status in {"forecast", "forecast_direction", "forecast_error"}:
            return "forecast"
        if status == "historical":
            return "deterministic_historical"
        if status == "knowledge":
            return "ai_definition"
        if status in {"ok", "generation_error", "validation_error", "execution_error"}:
            return "ai_text_to_sql"
        if status.startswith("multi"):
            return "multiple"
        return "router_only"

    @staticmethod
    def _analysis_mode(result: PipelineResult, routed_mode: str) -> str:
        if routed_mode != "STANDARD_ANALYTICS":
            return routed_mode
        if result.status == "knowledge":
            return "DEFINITION"
        if result.status in {"forecast", "forecast_direction"}:
            return "FORECAST"
        if result.execution_path == "fast_comparison":
            return "COMPARISON"
        if result.execution_path in {"fast_kpi", "fast_trend", "fast_ranking", "deterministic_historical"}:
            return "HISTORICAL_ANALYTICS"
        if result.execution_path == "ai_text_to_sql":
            return "SQL_ANALYTICS"
        return "STANDARD_ANALYTICS"

    def _log(self, result: PipelineResult) -> None:
        payload = asdict(result)
        payload.pop("frame", None)
        log_event(settings.project_root / "logs" / "analytics.jsonl", **payload)
