"""two-factor authentication (TOTP) columns, password-change timestamp, password-reset tokens

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-14
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # additive only: existing users keep working (2FA off until they enrol)
    op.add_column("users", sa.Column("totp_secret_enc", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("totp_last_step", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_by", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    with op.batch_alter_table("users") as b:
        b.drop_column("password_changed_at")
        b.drop_column("totp_last_step")
        b.drop_column("totp_enabled")
        b.drop_column("totp_secret_enc")
