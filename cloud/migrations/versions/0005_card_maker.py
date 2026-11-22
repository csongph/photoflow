"""add per-event photo card maker controls and template"""
from alembic import op
import sqlalchemy as sa


revision = "0005_card_maker"
down_revision = "0004_sponsor_branding"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("gallery_settings", sa.Column("card_maker_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("gallery_settings", sa.Column("card_template_name", sa.String(160), nullable=False, server_default=""))
    op.create_table(
        "card_templates",
        sa.Column("event_id", sa.String(32), sa.ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("image_data", sa.LargeBinary(), nullable=False),
    )


def downgrade():
    op.drop_table("card_templates")
    op.drop_column("gallery_settings", "card_template_name")
    op.drop_column("gallery_settings", "card_maker_enabled")
