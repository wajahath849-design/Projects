"""SQL Server database infrastructure."""

from decision_intelligence.database.connection import build_connection_string, connect

__all__ = ["build_connection_string", "connect"]
