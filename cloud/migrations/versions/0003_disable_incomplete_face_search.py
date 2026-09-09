"""Disable incomplete face search by default.

Revision ID: 0003_disable_face_search
Revises: 0002_gallery_guest_text
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_disable_face_search"
down_revision = "0002_gallery_guest_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "gallery_settings",
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.execute("UPDATE gallery_settings SET find_my_photos = false")
    op.alter_column(
        "gallery_settings",
        "find_my_photos",
        existing_type=sa.Boolean(),
        server_default=sa.false(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.drop_column("gallery_settings", "enabled")
    op.alter_column(
        "gallery_settings",
        "find_my_photos",
        existing_type=sa.Boolean(),
        server_default=sa.true(),
        existing_nullable=False,
    )
