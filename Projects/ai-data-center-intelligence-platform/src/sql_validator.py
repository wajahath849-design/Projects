from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SQLValidation:
    valid: bool
    sql: str
    error: str | None = None


class SQLValidator:
    FORBIDDEN = re.compile(
        r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|pragma|vacuum|reindex)\b",
        re.IGNORECASE,
    )

    def __init__(self, schema: dict[str, set[str]], max_rows: int = 1000) -> None:
        self.schema = schema
        self.max_rows = max_rows

    def validate(self, sql: str) -> SQLValidation:
        candidate = sql.strip()
        if not candidate:
            return SQLValidation(False, candidate, "SQL is empty")
        if "--" in candidate or "/*" in candidate:
            return SQLValidation(False, candidate, "SQL comments are not allowed")
        if ";" in candidate.rstrip(";"):
            return SQLValidation(False, candidate, "Multiple statements are not allowed")
        candidate = candidate.rstrip(";").strip()
        if self.FORBIDDEN.search(candidate):
            return SQLValidation(False, candidate, "SQL contains a forbidden operation")
        if not re.match(r"^(select|with)\b", candidate, re.IGNORECASE):
            return SQLValidation(False, candidate, "Only SELECT queries and read-only CTEs are allowed")

        try:
            import sqlglot
            from sqlglot import exp

            expression = sqlglot.parse_one(candidate, read="sqlite")
            if not isinstance(expression, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
                return SQLValidation(False, candidate, "Query is not a read-only SELECT")
            forbidden_types = (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter)
            if any(expression.find(kind) is not None for kind in forbidden_types):
                return SQLValidation(False, candidate, "SQL AST contains a write operation")
            cte_names = {cte.alias_or_name.lower() for cte in expression.find_all(exp.CTE)}
            table_names = {table.name.lower() for table in expression.find_all(exp.Table)} - cte_names
            unknown = table_names - {name.lower() for name in self.schema}
            if unknown:
                return SQLValidation(False, candidate, f"Unknown table(s): {', '.join(sorted(unknown))}")
        except ImportError:
            names = re.findall(r"\b(?:from|join)\s+[\"`\[]?([\w]+)", candidate, re.IGNORECASE)
            unknown = {name.lower() for name in names} - {name.lower() for name in self.schema}
            if unknown:
                return SQLValidation(False, candidate, f"Unknown table(s): {', '.join(sorted(unknown))}")
        except Exception as error:
            return SQLValidation(False, candidate, f"Invalid SQL: {error}")

        if not re.search(r"\blimit\s+\d+\b", candidate, re.IGNORECASE):
            candidate = f"{candidate} LIMIT {self.max_rows}"
        return SQLValidation(True, candidate)
