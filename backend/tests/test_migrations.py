from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.database import Base, require_current_schema


def test_database_is_at_the_committed_migration_head(db):
    configuration = Config("alembic.ini")
    expected_heads = set(ScriptDirectory.from_config(configuration).get_heads())
    current_heads = set(MigrationContext.configure(db.connection()).get_current_heads())

    assert current_heads == expected_heads
    require_current_schema()


def test_migrations_match_sqlalchemy_metadata(db):
    context = MigrationContext.configure(db.connection())

    assert compare_metadata(context, Base.metadata) == []
