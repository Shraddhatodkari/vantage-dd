"""coverage disclosure, historical cut-off, per-fact document reconciliation

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-14
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Plain ADD COLUMN (no table rebuild): safe on SQLite with foreign keys enabled and existing data.
    op.add_column("deals", sa.Column("historical_cutoff", sa.Date(), nullable=True))
    op.add_column("analysis_runs", sa.Column("coverage", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("financial_facts", sa.Column("document_check", sa.String(20), nullable=False,
                                               server_default="not_checked"))
    op.add_column("financial_facts", sa.Column("document_check_detail", sa.String(400), nullable=True))
    op.add_column("financial_facts", sa.Column("revision_note", sa.String(600), nullable=True))
    op.create_index("ix_findings_run_code", "findings", ["run_id", "code"])
    op.create_index("ix_runs_deal_status", "analysis_runs", ["deal_id", "status"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        bind.exec_driver_sql("PRAGMA foreign_keys=OFF")  # batch mode rebuilds tables
    op.drop_index("ix_runs_deal_status", "analysis_runs")
    op.drop_index("ix_findings_run_code", "findings")
    with op.batch_alter_table("financial_facts") as b:
        b.drop_column("revision_note")
        b.drop_column("document_check_detail")
        b.drop_column("document_check")
    with op.batch_alter_table("analysis_runs") as b:
        b.drop_column("coverage")
    with op.batch_alter_table("deals") as b:
        b.drop_column("historical_cutoff")
    if bind.dialect.name == "sqlite":
        bind.exec_driver_sql("PRAGMA foreign_keys=ON")
