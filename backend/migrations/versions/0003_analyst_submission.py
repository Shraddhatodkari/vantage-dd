"""analyst submission step before partner review; filing passage for each reconciled fact; wider lei_match

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-14
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_runs", sa.Column("submitted_by", sa.String(32), nullable=True))
    op.add_column("analysis_runs", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("analysis_runs", sa.Column("submission_note", sa.Text(), nullable=True))
    op.add_column("financial_facts", sa.Column("document_passage", sa.String(400), nullable=True))
    # 'jurisdiction_mismatch' (21 chars) did not fit VARCHAR(20); SQLite ignored it, PostgreSQL rejects it
    # SQLite does not enforce VARCHAR lengths, and a batch rebuild of a referenced table is avoidable risk there
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("companies", "lei_match", type_=sa.String(40), existing_type=sa.String(20), existing_nullable=True)


def downgrade() -> None:
    # lei_match stays VARCHAR(40): narrowing it would truncate stored values such as 'jurisdiction_mismatch'
    with op.batch_alter_table("financial_facts") as b:
        b.drop_column("document_passage")
    with op.batch_alter_table("analysis_runs") as b:
        b.drop_column("submission_note")
        b.drop_column("submitted_at")
        b.drop_column("submitted_by")
