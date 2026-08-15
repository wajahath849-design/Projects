from __future__ import annotations

import time
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from src.answer_generator import GroundedAnswerGenerator
from src.answer_validator import validate_answer_numbers
from src.config import settings
from src.database import discover_schema
from src.executor import SQLExecutor
from src.forecasting import (
    MetricForecaster,
    detect_metric,
    detect_metrics,
    has_forecast_intent,
    resolve_target_year,
    supported_metric_names,
)
from src.logging_utils import log_event
from src.question_analyzer import QuestionAnalyzer
from src.retriever import Retriever
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


class AnalyticsPipeline:
    def __init__(self, generator=None, database_path: Path | str | None = None) -> None:
        self.database_path = Path(database_path or settings.database_path)
        self.schema = discover_schema(self.database_path)
        self.modules = self._available_modules()
        self.analyzer = QuestionAnalyzer(self.modules)
        self.retriever = Retriever(SemanticLayer(settings.project_root).build_chunks())
        self.generator = generator or self._default_generator()
        self.validator = SQLValidator(self.schema, settings.max_result_rows)
        self.executor = SQLExecutor(self.database_path, settings.sql_timeout_seconds, settings.max_result_rows)
        self.answerer = GroundedAnswerGenerator()
        self.forecaster = MetricForecaster(self.database_path)

    def _default_generator(self):
        if OllamaSQLGenerator.model_available(settings.ollama_host, settings.ollama_model):
            return OllamaSQLGenerator(settings.ollama_host, settings.ollama_model)
        return VerifiedExampleSQLGenerator()

    def _available_modules(self) -> set[str]:
        required = {
            "energy": {"facilities", "power_metrics"},
            "server_performance": {"servers", "server_metrics"},
            "network": {"facilities", "network_metrics"},
            "reliability": {"facilities", "servers", "uptime_incidents"},
        }
        return {module for module, tables in required.items() if tables <= set(self.schema)}

    def ask(self, question: str, _allow_split: bool = True) -> PipelineResult:
        started = time.perf_counter()
        if _allow_split:
            parts = self._split_questions(question)
            if len(parts) > 1:
                return self._answer_multiple(question, parts, started)
        analysis = self.analyzer.analyze(question)
        if analysis.unsafe:
            return self._stop(question, "blocked", "The request was blocked because it contains a database-changing instruction.", started)
        if analysis.ambiguous or analysis.clarification:
            return self._stop(question, "clarification", analysis.clarification or "Please clarify the requested metric.", started)
        if not analysis.relevant:
            return self._stop(question, "irrelevant", "Please ask about energy, servers, network performance, or reliability in the data-center dataset.", started)

        latest_complete_year = self.forecaster.latest_complete_year()
        target_year = resolve_target_year(question, latest_complete_year)
        if target_year is not None:
            matched_metrics = detect_metrics(question)
            if len(matched_metrics) > 1:
                return self._forecast_multiple_metrics(
                    question, matched_metrics, target_year, analysis.facilities, started
                )
            metric = detect_metric(question)
            if metric is None:
                names = ", ".join(supported_metric_names())
                if any(term in question.lower() for term in ("price", "cost", "expense", "tariff")):
                    return self._stop(
                        question, "clarification",
                        "The database does not contain a historical price series for that item. "
                        "The only monetary time series currently available is Annual Cooling Cost; "
                        f"other supported forecasts are: {names}.", started,
                    )
                return self._stop(
                    question, "clarification",
                    f"Which forecast metric do you mean? Supported time-series metrics are: {names}.", started,
                )
            return self._forecast_metric(question, metric, target_year, analysis.facilities, started)
        if has_forecast_intent(question):
            metric = detect_metric(question)
            metric_text = metric.display_name if metric else "that metric"
            return self._stop(
                question, "clarification",
                f"Which future year should I use to forecast {metric_text}? "
                f"The latest complete data year is {latest_complete_year}; for example, ask for {latest_complete_year + 5}.",
                started,
            )

        retrieved = self.retriever.retrieve(question, settings.rag_top_k)
        context = "\n\n".join(item.chunk.text for item in retrieved)
        try:
            generated = self.generator.generate(question, context)
        except Exception as error:
            return self._stop(question, "generation_error", str(error), started)
        validation = self.validator.validate(generated.sql)
        if not validation.valid:
            return self._stop(question, "validation_error", validation.error or "SQL validation failed", started, generated.sql)
        try:
            execution = self.executor.execute(validation.sql)
        except Exception as error:
            return self._stop(question, "execution_error", f"The validated query could not run: {error}", started, validation.sql)

        answer = self.answerer.generate(question, execution.frame)
        faithful, unsupported = validate_answer_numbers(answer, execution.frame)
        if not faithful:
            answer = f"The result table is authoritative; answer rendering found unsupported values: {unsupported}."
        sources = sorted({name for name in self.schema if name.lower() in validation.sql.lower()})
        result = PipelineResult(
            "ok", question, answer, validation.sql, "valid", 
            [{"id": item.chunk.chunk_id, "score": round(item.score, 4), **item.chunk.metadata} for item in retrieved],
            sources, execution.frame, chart_spec(execution.frame), execution.execution_ms,
            (time.perf_counter() - started) * 1000, generated.input_tokens, generated.output_tokens,
        )
        self._log(result)
        return result

    @staticmethod
    def _split_questions(question: str) -> list[str]:
        parts = [part.strip(" \t\r\n?.;") for part in re.split(r"\?+|;+|\r?\n+", question)]
        return [part for part in parts if len(part.split()) >= 2]

    def _answer_multiple(self, original: str, questions: list[str], started: float) -> PipelineResult:
        results = [self.ask(question, _allow_split=False) for question in questions]
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
        combined_status = "multi_ok" if statuses <= {"ok", "forecast"} else "multi_partial"
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
        )
        self._log(result)
        return result

    def _forecast_multiple_metrics(self, question, metrics, target_year, facilities, started):
        outputs = []
        frames = []
        sources = {"facilities"}
        evidence = []
        for metric in metrics:
            try:
                forecast = self.forecaster.forecast(metric, target_year, facilities or None)
            except Exception as error:
                return self._stop(
                    question, "forecast_error",
                    f"The {metric.display_name} forecast could not be calculated: {error}", started,
                )
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
        answer = (
            f"The {target_year} multi-metric forecast is:\n\n" + "\n".join(outputs) +
            "\n\nThese are projections from synthetic historical observations, not guarantees."
        )
        result = PipelineResult(
            "forecast", question, answer, validation_status="forecast_model",
            retrieved_context=evidence, source_tables=sorted(sources),
            frame=pd.concat(frames, ignore_index=True, sort=False), chart=None,
            execution_ms=None, total_ms=(time.perf_counter() - started) * 1000,
        )
        self._log(result)
        return result

    def _forecast_metric(self, question, metric, target_year: int, facilities: list[str], started: float) -> PipelineResult:
        try:
            forecast = self.forecaster.forecast(metric, target_year, facilities or None)
        except Exception as error:
            return self._stop(question, "forecast_error", f"The forecast could not be calculated: {error}", started)
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
        result = PipelineResult(
            "forecast", question, answer, forecast.source_sql, "forecast_model",
            [{"kind": "forecast_method", "method": "annual_linear_trend", "interval": "approximate_95_prediction_interval", "metric": metric.key}],
            ["facilities", metric.table], forecast.frame,
            {"kind": "bar", "x": "facility_name", "y": "predicted_value"},
            forecast.execution_ms, (time.perf_counter() - started) * 1000,
        )
        self._log(result)
        return result

    def _stop(self, question, status, answer, started, sql=None):
        result = PipelineResult(status, question, answer, sql=sql, total_ms=(time.perf_counter() - started) * 1000)
        self._log(result)
        return result

    def _log(self, result: PipelineResult) -> None:
        payload = asdict(result)
        payload.pop("frame", None)
        log_event(settings.project_root / "logs" / "analytics.jsonl", **payload)
