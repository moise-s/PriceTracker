"""Allow shopping quantities and catalog defaults in metres.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table, column in (("catalog_items", "default_unit"), ("list_items", "unit")):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(op.f(f"ck_{table}_{column}"), type_="check")
            batch.create_check_constraint(
                op.f(f"ck_{table}_{column}"),
                f"{column} IN ('g', 'kg', 'ml', 'l', 'un', 'pct', 'm')",
            )


def downgrade() -> None:
    # Reinterpreting metre quantities as packages would corrupt shopping lists.
    connection = op.get_bind()
    for table, column in (("catalog_items", "default_unit"), ("list_items", "unit")):
        data = sa.table(table, sa.column(column))
        if connection.scalar(
            sa.select(sa.func.count()).select_from(data).where(data.c[column] == "m")
        ):
            raise RuntimeError("Remove metre-based list items/catalog defaults before downgrading.")
    for table, column in (("catalog_items", "default_unit"), ("list_items", "unit")):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(op.f(f"ck_{table}_{column}"), type_="check")
            batch.create_check_constraint(
                op.f(f"ck_{table}_{column}"), f"{column} IN ('g', 'kg', 'ml', 'l', 'un', 'pct')"
            )
