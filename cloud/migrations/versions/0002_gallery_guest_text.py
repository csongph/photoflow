"""add guest gallery text settings"""
from alembic import op
import sqlalchemy as sa

revision = "0002_gallery_guest_text"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("gallery_settings", sa.Column("credit_text", sa.String(220), nullable=False, server_default=""))
    op.add_column("gallery_settings", sa.Column("report_contact", sa.String(220), nullable=False, server_default=""))


def downgrade():
    op.drop_column("gallery_settings", "report_contact")
    op.drop_column("gallery_settings", "credit_text")
