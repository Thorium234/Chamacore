"""Connection-string normalization for Azure Postgres + Alembic."""

from app.core.config import normalize_database_url


def test_sqlite_urls_are_unchanged():
    assert normalize_database_url("sqlite:///./chamacore.db") == "sqlite:///./chamacore.db"


def test_asyncpg_is_rewritten_to_sync_psycopg():
    url = normalize_database_url(
        "postgresql+asyncpg://chamacore:chamacore@localhost:5432/chamacore_test"
    )
    assert url.startswith("postgresql+psycopg://")
    assert "asyncpg" not in url
    assert "sslmode" not in url


def test_azure_password_special_chars_and_ssl():
    url = normalize_database_url(
        "postgresql+asyncpg://azureuser:@BIT/0060/24@host.postgres.database.azure.com:5432/chamacore"
    )
    assert url.startswith("postgresql+psycopg://azureuser:")
    assert "%40BIT%2F0060%2F24@" in url
    assert "host.postgres.database.azure.com:5432/chamacore" in url
    assert "sslmode=require" in url


def test_already_encoded_azure_url_is_not_double_encoded():
    url = normalize_database_url(
        "postgresql+psycopg://azureuser:%40BIT%2F0060%2F24@host.postgres.database.azure.com:5432/chamacore?sslmode=require"
    )
    assert url.count("%40BIT%2F0060%2F24") == 1
    assert url.count("sslmode=require") == 1
