from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


def _odbc_value(value: str) -> str:
    return "{" + value.replace("}", "}}") + "}"


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    sec_user_agent: str = os.getenv("SEC_USER_AGENT", "")
    sec_cik: str = os.getenv("SEC_CIK", "0000320193")
    sec_company_name: str = os.getenv("SEC_COMPANY_NAME", "Apple Inc.")
    sec_ticker: str = os.getenv("SEC_TICKER", "AAPL")
    sec_request_timeout_seconds: int = int(os.getenv("SEC_REQUEST_TIMEOUT_SECONDS", "30"))
    sec_cache_hours: int = int(os.getenv("SEC_CACHE_HOURS", "12"))

    mssql_server: str = os.getenv("MSSQL_SERVER", "localhost,1433")
    mssql_database: str = os.getenv("MSSQL_DATABASE", "AppleFinancialReporting")
    mssql_username: str = os.getenv("MSSQL_USERNAME", "sa")
    mssql_password: str = os.getenv("MSSQL_PASSWORD", "")
    mssql_driver: str = os.getenv("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server")
    mssql_windows_auth: bool = _as_bool(os.getenv("MSSQL_WINDOWS_AUTH"), False)
    mssql_encrypt: str = os.getenv("MSSQL_ENCRYPT", "yes")
    mssql_trust_server_certificate: str = os.getenv("MSSQL_TRUST_SERVER_CERTIFICATE", "yes")

    history_years: int = int(os.getenv("HISTORY_YEARS", "10"))
    raw_data_dir: Path = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
    processed_data_dir: Path = Path(os.getenv("PROCESSED_DATA_DIR", "data/processed"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    def validate_sec_user_agent(self) -> None:
        if not self.sec_user_agent or "@" not in self.sec_user_agent:
            raise ValueError(
                "SEC_USER_AGENT must identify you and include an email address. "
                "Copy .env.example to .env and update SEC_USER_AGENT."
            )

    @property
    def sqlalchemy_master_url(self) -> str:
        return self._sqlalchemy_url(database="master")

    @property
    def sqlalchemy_database_url(self) -> str:
        return self._sqlalchemy_url(database=self.mssql_database)

    def _sqlalchemy_url(self, database: str) -> str:
        if self.mssql_windows_auth:
            odbc = (
                f"DRIVER={_odbc_value(self.mssql_driver)};"
                f"SERVER={_odbc_value(self.mssql_server)};"
                f"DATABASE={_odbc_value(database)};"
                f"Trusted_Connection=yes;Encrypt={self.mssql_encrypt};"
                f"TrustServerCertificate={self.mssql_trust_server_certificate}"
            )
        else:
            if not self.mssql_password:
                raise ValueError("MSSQL_PASSWORD is required when MSSQL_WINDOWS_AUTH=false.")
            odbc = (
                f"DRIVER={_odbc_value(self.mssql_driver)};"
                f"SERVER={_odbc_value(self.mssql_server)};"
                f"DATABASE={_odbc_value(database)};"
                f"UID={_odbc_value(self.mssql_username)};"
                f"PWD={_odbc_value(self.mssql_password)};"
                f"Encrypt={self.mssql_encrypt};"
                f"TrustServerCertificate={self.mssql_trust_server_certificate}"
            )
        return f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc)}"


def get_settings() -> Settings:
    settings = Settings()
    settings.raw_data_dir.mkdir(parents=True, exist_ok=True)
    settings.processed_data_dir.mkdir(parents=True, exist_ok=True)
    return settings
