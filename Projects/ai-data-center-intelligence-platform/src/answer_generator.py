from __future__ import annotations

import re

import pandas as pd

from src.untrusted_content import untrusted_data_rules, wrap_untrusted_records, wrap_untrusted_text


class GroundedAnswerGenerator:
    """Deterministic answer renderer; it can only describe returned database values."""

    def generate(self, question: str, frame: pd.DataFrame) -> str:
        if frame.empty:
            return "No matching records were found for that question."
        if len(frame) == 1:
            values = ", ".join(
                f"{column}: {self._format(value)}" for column, value in frame.iloc[0].items()
            )
            return f"The database result is {values}."
        preview = frame.head(5)
        if len(frame.columns) == 2:
            first, second = frame.columns
            values = "; ".join(
                f"{self._format(row[first])}: {self._format(row[second])}"
                for _, row in preview.iterrows()
            )
            suffix = "" if len(frame) <= 5 else f" The table contains {len(frame)} rows in total."
            return f"The results are {values}.{suffix}"
        return f"The query returned {len(frame)} rows. The result table below is the authoritative answer."

    def answer_knowledge(self, question: str, context: str) -> str:
        first_chunk = context.split("\n\n", 1)[0].strip()
        if first_chunk:
            return f"The closest project definition is: {first_chunk}"
        return "I could not find a project definition for that question. Please name the metric you mean."

    @staticmethod
    def _format(value) -> str:
        if pd.isna(value):
            return "not available"
        if isinstance(value, float):
            return f"{value:,.2f}"
        return str(value)


class OllamaGroundedAnswerGenerator(GroundedAnswerGenerator):
    """Use Ollama only when a result genuinely requires narrative interpretation."""

    def __init__(
        self,
        client,
        model: str,
        keep_alive: str = "30m",
        num_ctx: int = 4096,
        max_tokens: int = 256,
    ) -> None:
        self.client = client
        self.model = model
        self.keep_alive = keep_alive
        self.num_ctx = num_ctx
        self.max_tokens = max_tokens

    @staticmethod
    def _content(response) -> str:
        message = getattr(response, "message", None)
        content = (
            getattr(message, "content", None)
            if message is not None
            else response["message"]["content"]
        )
        return str(content).strip()

    @staticmethod
    def will_use_llm(question: str, frame: pd.DataFrame) -> bool:
        if frame.empty:
            return False
        return bool(
            re.search(
                r"\b(why|explain|interpret|relationship|relate|correlat|coincid|cause|"
                r"deteriorat|unusual|anomal|investigat|analy[sz]e|insight)\w*\b",
                question.lower(),
            )
        )

    def _chat(self, prompt: str):
        return self.client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            keep_alive=self.keep_alive,
            options={
                "temperature": 0,
                "num_ctx": self.num_ctx,
                "num_predict": self.max_tokens,
            },
        )

    def generate(self, question: str, frame: pd.DataFrame) -> str:
        if not self.will_use_llm(question, frame):
            return super().generate(question, frame)
        records = frame.head(100).to_dict(orient="records")
        prompt = f"""Answer QUESTION using only DATABASE RESULT.
{untrusted_data_rules()}
Never invent values, causes, dates, or conclusions.
Use cautious, non-causal language unless the result explicitly confirms a cause.
Do not mention SQL. If many rows exist, summarize and point to the result table.

USER QUESTION
{wrap_untrusted_text(question, "user_question", max_chars=4_000)}

DATABASE RESULT ({len(frame)} rows; at most 100 supplied)
{wrap_untrusted_records(records, "database_result", max_records=100)}"""
        try:
            answer = self._content(self._chat(prompt))
            return answer or super().generate(question, frame)
        except Exception:
            return super().generate(question, frame)

    def answer_knowledge(self, question: str, context: str) -> str:
        prompt = f"""Answer QUESTION using only PROJECT KNOWLEDGE.
{untrusted_data_rules()}
If knowledge is insufficient, say what is missing.
Do not invent company facts or present synthetic observations as real-world facts.

USER QUESTION
{wrap_untrusted_text(question, "user_question", max_chars=4_000)}

PROJECT KNOWLEDGE
{wrap_untrusted_text(context, "retrieved_project_knowledge")}"""
        try:
            answer = self._content(self._chat(prompt))
            if answer:
                return answer
        except Exception:
            pass
        return (
            "I found relevant project definitions, but the local Ollama model was unavailable to explain "
            "them conversationally. Check that Ollama and the configured model are running."
        )
