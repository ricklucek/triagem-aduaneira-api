"""Adiciona classificação fiscal por item da DUIMP.

Revision ID: 20260818_01
Revises:
Create Date: 2026-08-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260818_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "nfe_item_classifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_process_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("duimp_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("duimp_item_number", sa.String(length=30), nullable=False),
        sa.Column("import_purpose", sa.String(length=30), nullable=False),
        sa.Column("tax_rule_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cfop", sa.String(length=4), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("classified_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["import_process_id"], ["import_processes.id"]),
        sa.ForeignKeyConstraint(["duimp_snapshot_id"], ["duimp_snapshots.id"]),
        sa.ForeignKeyConstraint(["tax_rule_id"], ["client_import_tax_rules.id"]),
        sa.ForeignKeyConstraint(["classified_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "duimp_snapshot_id",
            "duimp_item_number",
            name="uq_nfe_item_classification_snapshot_item",
        ),
    )
    for column in (
        "organization_id",
        "import_process_id",
        "duimp_snapshot_id",
        "import_purpose",
        "tax_rule_id",
        "classified_by_user_id",
    ):
        op.create_index(
            f"ix_nfe_item_classifications_{column}",
            "nfe_item_classifications",
            [column],
        )

    op.add_column(
        "nfe_draft_items",
        sa.Column("import_purpose", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "nfe_draft_items",
        sa.Column("tax_rule_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "nfe_draft_items",
        sa.Column(
            "item_classification_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_nfe_draft_items_tax_rule_id",
        "nfe_draft_items",
        "client_import_tax_rules",
        ["tax_rule_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_nfe_draft_items_item_classification_id",
        "nfe_draft_items",
        "nfe_item_classifications",
        ["item_classification_id"],
        ["id"],
    )
    op.create_index(
        "ix_nfe_draft_items_import_purpose",
        "nfe_draft_items",
        ["import_purpose"],
    )
    op.create_index(
        "ix_nfe_draft_items_tax_rule_id",
        "nfe_draft_items",
        ["tax_rule_id"],
    )
    op.create_index(
        "ix_nfe_draft_items_item_classification_id",
        "nfe_draft_items",
        ["item_classification_id"],
    )


def downgrade():
    op.drop_index(
        "ix_nfe_draft_items_item_classification_id",
        table_name="nfe_draft_items",
    )
    op.drop_index("ix_nfe_draft_items_tax_rule_id", table_name="nfe_draft_items")
    op.drop_index(
        "ix_nfe_draft_items_import_purpose",
        table_name="nfe_draft_items",
    )
    op.drop_constraint(
        "fk_nfe_draft_items_item_classification_id",
        "nfe_draft_items",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_nfe_draft_items_tax_rule_id",
        "nfe_draft_items",
        type_="foreignkey",
    )
    op.drop_column("nfe_draft_items", "item_classification_id")
    op.drop_column("nfe_draft_items", "tax_rule_id")
    op.drop_column("nfe_draft_items", "import_purpose")
    op.drop_table("nfe_item_classifications")
