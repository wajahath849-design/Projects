from src.database import discover_schema
from src.sql_validator import SQLValidator


def validator():
    return SQLValidator(discover_schema("database/datacenter.db"), max_rows=25)


def test_valid_select_gets_limit():
    result = validator().validate("SELECT facility_name FROM facilities")
    assert result.valid
    assert result.sql.endswith("LIMIT 25")


def test_safe_cte_allowed():
    result = validator().validate("WITH x AS (SELECT facility_id FROM facilities) SELECT * FROM x")
    assert result.valid


def test_writes_and_multiple_statements_blocked():
    for sql in [
        "DROP TABLE facilities", "DELETE FROM facilities", "UPDATE facilities SET city='x'",
        "INSERT INTO facilities VALUES (1)", "SELECT 1; SELECT 2",
    ]:
        assert not validator().validate(sql).valid


def test_unknown_table_and_column_blocked():
    assert not validator().validate("SELECT * FROM secrets").valid
    assert not validator().validate("SELECT secret_value FROM facilities").valid
