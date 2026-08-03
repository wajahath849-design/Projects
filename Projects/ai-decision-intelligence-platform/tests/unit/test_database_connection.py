"""Unit tests for SQL Server connection configuration."""

from decision_intelligence.database.connection import build_connection_string
from decision_intelligence.settings import DatabaseSettings


def test_connection_string_uses_windows_authentication_and_encryption() -> None:
    settings = DatabaseSettings(
        server=r"localhost\SQLEXPRESS",
        database="AIDecisionIntelligence",
        driver="ODBC Driver 18 for SQL Server",
        trusted_connection=True,
        trust_server_certificate=True,
        connection_timeout_seconds=5,
        command_timeout_seconds=60,
    )
    value = build_connection_string(settings)
    assert "Trusted_Connection=yes" in value
    assert "Encrypt=yes" in value
    assert "TrustServerCertificate=yes" in value
    assert "UseFMTONLY=yes" in value
    assert "PWD=" not in value and "UID=" not in value


def test_connection_string_allows_master_override() -> None:
    settings = DatabaseSettings(
        server="server",
        database="analytics",
        driver="driver",
        trusted_connection=True,
        trust_server_certificate=True,
        connection_timeout_seconds=5,
        command_timeout_seconds=60,
    )
    assert "DATABASE={master}" in build_connection_string(settings, "master")


def test_connection_string_supports_container_sql_authentication() -> None:
    settings = DatabaseSettings(
        server="sqlserver,1433", database="analytics", driver="driver",
        trusted_connection=False, trust_server_certificate=True,
        connection_timeout_seconds=5, command_timeout_seconds=60,
        username="sa", password="secret-value",
    )
    value = build_connection_string(settings)
    assert "Trusted_Connection=no" in value
    assert "UID={sa}" in value and "PWD={secret-value}" in value
