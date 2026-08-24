"""initial schema"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("events", sa.Column("id", sa.String(32), primary_key=True), sa.Column("public_id", sa.String(64), nullable=False), sa.Column("name", sa.String(180), nullable=False), sa.Column("event_date", sa.String(20), nullable=False, server_default=""), sa.Column("description", sa.Text(), nullable=False, server_default=""), sa.Column("pin_hash", sa.String(200), nullable=False, server_default=""), sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()))
    op.create_index("ix_events_public_id", "events", ["public_id"], unique=True)
    op.create_table("gallery_settings", sa.Column("event_id", sa.String(32), sa.ForeignKey("events.id"), primary_key=True), sa.Column("allow_download", sa.Boolean(), nullable=False), sa.Column("find_my_photos", sa.Boolean(), nullable=False), sa.Column("auto_refresh", sa.Boolean(), nullable=False))
    op.create_table("photos", sa.Column("id", sa.String(32), primary_key=True), sa.Column("event_id", sa.String(32), sa.ForeignKey("events.id")), sa.Column("local_photo_id", sa.String(64)), sa.Column("filename", sa.String(260)), sa.Column("capture_id", sa.String(220)), sa.Column("storage_provider", sa.String(60)), sa.Column("storage_object_id", sa.String(300)), sa.Column("published", sa.Boolean()), sa.Column("hidden", sa.Boolean()), sa.Column("created_at", sa.DateTime()))
    op.create_index("ix_photos_event_id", "photos", ["event_id"])
    op.create_unique_constraint("uq_photo_event_local", "photos", ["event_id", "local_photo_id"])
    op.create_table("photo_variants", sa.Column("id", sa.String(32), primary_key=True), sa.Column("photo_id", sa.String(32), sa.ForeignKey("photos.id")), sa.Column("kind", sa.String(30)), sa.Column("storage_provider", sa.String(60)), sa.Column("storage_object_id", sa.String(300)), sa.Column("width", sa.Integer()), sa.Column("height", sa.Integer()))
    op.create_table("sync_jobs", sa.Column("id", sa.String(32), primary_key=True), sa.Column("event_id", sa.String(32), sa.ForeignKey("events.id")), sa.Column("state", sa.String(40)), sa.Column("payload_json", sa.Text()), sa.Column("created_at", sa.DateTime()))
    op.create_table("photo_faces", sa.Column("id", sa.String(32), primary_key=True), sa.Column("event_id", sa.String(32), sa.ForeignKey("events.id")), sa.Column("photo_id", sa.String(32), sa.ForeignKey("photos.id")), sa.Column("embedding", sa.LargeBinary()), sa.Column("confidence", sa.Float()), sa.Column("bounding_box", sa.String(120)), sa.Column("created_at", sa.DateTime()))
    op.create_index("ix_photo_faces_event_photo", "photo_faces", ["event_id", "photo_id"])
    op.create_table("face_search_sessions", sa.Column("id", sa.String(48), primary_key=True), sa.Column("event_id", sa.String(32), sa.ForeignKey("events.id")), sa.Column("status", sa.String(40)), sa.Column("created_at", sa.DateTime()))


def downgrade():
    for table in ["face_search_sessions", "photo_faces", "sync_jobs", "photo_variants", "photos", "gallery_settings", "events"]:
        op.drop_table(table)
