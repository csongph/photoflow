"""Add sponsor branding to cloud gallery settings.

Revision ID: 0004_sponsor_branding
Revises: 0003_disable_face_search
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_sponsor_branding"
down_revision = "0003_disable_face_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gallery_settings", sa.Column("sponsor_name", sa.String(180), nullable=False, server_default=""))
    op.add_column("gallery_settings", sa.Column("sponsor_logo", sa.String(2048), nullable=False, server_default=""))
    op.add_column("gallery_settings", sa.Column("sponsor_hashtag", sa.String(120), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("gallery_settings", "sponsor_hashtag")
    op.drop_column("gallery_settings", "sponsor_logo")
    op.drop_column("gallery_settings", "sponsor_name")
