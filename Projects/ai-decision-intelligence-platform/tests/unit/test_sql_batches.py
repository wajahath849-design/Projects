"""Unit tests for SQL Server GO batch parsing."""

from decision_intelligence.database.initializer import split_sql_batches


def test_split_sql_batches_handles_case_comments_and_repeat_counts() -> None:
    sql = "SELECT 1;\ngo -- separator\nSELECT 2;\nGO 2\n"
    assert split_sql_batches(sql) == ["SELECT 1;", "SELECT 2;", "SELECT 2;"]


def test_split_sql_batches_does_not_split_inline_text() -> None:
    sql = "SELECT 'GO' AS value;\nSELECT 2;"
    assert split_sql_batches(sql) == [sql]
