"""Adiciona planejamento Master e documentos filhos da NF-e.

Revision ID: 20260818_02
Revises: 20260818_01
Create Date: 2026-08-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260818_02"
down_revision = "20260818_01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "nfe_document_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_process_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("duimp_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("allocation_basis", sa.String(length=40), nullable=False),
        sa.Column("shared_costs", sa.JSON(), nullable=False),
        sa.Column("totals", sa.JSON(), nullable=False),
        sa.Column("reconciliation", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["import_process_id"], ["import_processes.id"]),
        sa.ForeignKeyConstraint(["duimp_snapshot_id"], ["duimp_snapshots.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "duimp_snapshot_id",
            "version_number",
            name="uq_nfe_document_plan_snapshot_version",
        ),
    )
    for column in (
        "organization_id",
        "import_process_id",
        "duimp_snapshot_id",
        "status",
        "created_by_user_id",
    ):
        op.create_index(
            f"ix_nfe_document_plans_{column}",
            "nfe_document_plans",
            [column],
        )

    op.create_table(
        "nfe_planned_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("exporter_key", sa.String(length=255), nullable=False),
        sa.Column("exporter_code", sa.String(length=100), nullable=True),
        sa.Column("foreign_supplier", sa.JSON(), nullable=True),
        sa.Column("operation_nature", sa.String(length=60), nullable=False),
        sa.Column("item_purposes", sa.JSON(), nullable=False),
        sa.Column("mixed_import_purposes", sa.Boolean(), nullable=False),
        sa.Column("items_count", sa.Integer(), nullable=False),
        sa.Column("customs_value", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("allocated_shared_costs", sa.JSON(), nullable=False),
        sa.Column("totals", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["document_plan_id"], ["nfe_document_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_plan_id",
            "exporter_key",
            name="uq_nfe_planned_document_plan_exporter",
        ),
    )
    for column in (
        "organization_id",
        "document_plan_id",
        "exporter_code",
        "status",
    ):
        op.create_index(
            f"ix_nfe_planned_documents_{column}",
            "nfe_planned_documents",
            [column],
        )

    op.create_table(
        "nfe_planned_document_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("planned_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("duimp_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_classification_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("duimp_item_number", sa.String(length=30), nullable=False),
        sa.Column("exporter_key", sa.String(length=255), nullable=False),
        sa.Column("exporter_code", sa.String(length=100), nullable=True),
        sa.Column("import_purpose", sa.String(length=30), nullable=False),
        sa.Column("cfop", sa.String(length=4), nullable=False),
        sa.Column("customs_value", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("allocated_shared_costs", sa.JSON(), nullable=False),
        sa.Column("raw_source_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["document_plan_id"], ["nfe_document_plans.id"]),
        sa.ForeignKeyConstraint(["planned_document_id"], ["nfe_planned_documents.id"]),
        sa.ForeignKeyConstraint(["duimp_snapshot_id"], ["duimp_snapshots.id"]),
        sa.ForeignKeyConstraint(["item_classification_id"], ["nfe_item_classifications.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_plan_id",
            "duimp_item_number",
            name="uq_nfe_planned_document_item_plan_item",
        ),
    )
    for column in (
        "organization_id",
        "document_plan_id",
        "planned_document_id",
        "duimp_snapshot_id",
        "item_classification_id",
        "import_purpose",
    ):
        op.create_index(
            f"ix_nfe_planned_document_items_{column}",
            "nfe_planned_document_items",
            [column],
        )


def downgrade():
    op.drop_table("nfe_planned_document_items")
    op.drop_table("nfe_planned_documents")
    op.drop_table("nfe_document_plans")
