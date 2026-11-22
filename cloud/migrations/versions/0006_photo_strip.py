"""store per-event photo strip theme configuration and layouts"""
from alembic import op
import sqlalchemy as sa


revision = "0006_photo_strip"
down_revision = "0005_card_maker"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("gallery_settings", sa.Column("photo_strip_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("gallery_settings", sa.Column("photo_strip_config_json", sa.Text(), nullable=False, server_default="{}"))
    op.create_table(
        "photo_strip_assets",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("event_id", sa.String(32), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("theme_id", sa.String(64), nullable=False),
        sa.Column("photo_count", sa.Integer(), nullable=False),
        sa.Column("image_data", sa.LargeBinary(), nullable=False),
        sa.UniqueConstraint("event_id", "theme_id", "photo_count", name="uq_photo_strip_event_theme_count"),
    )
    op.create_index("ix_photo_strip_assets_event_id", "photo_strip_assets", ["event_id"])
    op.create_index("ix_photo_strip_assets_theme_id", "photo_strip_assets", ["theme_id"])


def downgrade():
    op.drop_index("ix_photo_strip_assets_theme_id", table_name="photo_strip_assets")
    op.drop_index("ix_photo_strip_assets_event_id", table_name="photo_strip_assets")
    op.drop_table("photo_strip_assets")
    op.drop_column("gallery_settings", "photo_strip_config_json")
    op.drop_column("gallery_settings", "photo_strip_enabled")
