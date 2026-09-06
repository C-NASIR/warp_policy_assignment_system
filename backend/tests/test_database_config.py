import pytest

from app.database import database_url_for_mode


def test_real_database_mode_uses_database_url():
    assert (
        database_url_for_mode(
            {
                "DATABASE_MODE": "real",
                "DATABASE_URL": "postgresql+psycopg:///company",
                "DEMO_DATABASE_URL": "postgresql+psycopg:///demo",
            }
        )
        == "postgresql+psycopg:///company"
    )


def test_demo_database_mode_uses_demo_database_url():
    assert (
        database_url_for_mode(
            {
                "DATABASE_MODE": "DEMO",
                "DATABASE_URL": "postgresql+psycopg:///company",
                "DEMO_DATABASE_URL": "postgresql+psycopg:///demo",
            }
        )
        == "postgresql+psycopg:///demo"
    )


def test_database_mode_rejects_unknown_values():
    with pytest.raises(RuntimeError, match="either 'real' or 'demo'"):
        database_url_for_mode({"DATABASE_MODE": "staging"})
