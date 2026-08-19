"""Vincula rascunhos fiscais às NF-e filhas planejadas.

Revision ID: 20260818_03
Revises: 20260818_02
Create Date: 2026-08-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260818_03"
down_revision = "20260818_02"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "nfe_drafts",
        sa.Column(
            "planned_document_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_nfe_drafts_planned_document_id",
        "nfe_drafts",
        "nfe_planned_documents",
        ["planned_document_id"],
        ["id"],
    )
    op.create_index(
        "ix_nfe_drafts_planned_document_id",
        "nfe_drafts",
        ["planned_document_id"],
    )


def downgrade():
    op.drop_index(
        "ix_nfe_drafts_planned_document_id",
        table_name="nfe_drafts",
    )
    op.drop_constraint(
        "fk_nfe_drafts_planned_document_id",
        "nfe_drafts",
        type_="foreignkey",
    )
    op.drop_column("nfe_drafts", "planned_document_id")
