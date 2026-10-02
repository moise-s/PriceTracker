from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError


def test_existing_schema_retains_rows_and_allows_metres(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.attributes["database_url"] = f"sqlite:///{tmp_path / 'migration.db'}"
    config.attributes["configure_logger"] = False
    command.upgrade(config, "0001")
    engine = create_engine(config.attributes["database_url"])
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO catalog_items (id, slug, name, category, sold_by, default_quantity, default_unit, match_spec, is_active, sort_order, created_at, updated_at) VALUES ('abc', 'paper', 'Paper', 'Hygiene', 'package', 120, 'pct', '{}', 1, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
    command.upgrade(config, "head")
    with engine.begin() as connection:
        connection.execute(text("UPDATE catalog_items SET default_unit = 'm' WHERE id = 'abc'"))
        assert (
            connection.scalar(text("SELECT default_quantity FROM catalog_items WHERE id = 'abc'"))
            == 120
        )
        connection.execute(
            text(
                "INSERT INTO list_items (id, list_id, product_id, quantity, unit, position, created_at, updated_at) VALUES ('item', 'list', 'product', 120, 'm', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("UPDATE list_items SET unit = 'invalid'"))
    with pytest.raises(RuntimeError, match="metre-based"):
        command.downgrade(config, "0001")
    with engine.begin() as connection:
        connection.execute(text("UPDATE catalog_items SET default_unit = 'pct'"))
        connection.execute(text("DELETE FROM list_items"))
    command.downgrade(config, "0001")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT name FROM catalog_items WHERE id = 'abc'")) == "Paper"
    command.upgrade(config, "head")
    engine.dispose()
