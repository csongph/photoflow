"""Compatibility revision after removing sponsor branding.

Revision ID: 0004_sponsor_branding
Revises: 0003_disable_face_search

This revision intentionally does not add columns. Keeping the revision in the
chain lets databases that already recorded it continue to migrate safely.
"""

from alembic import op


revision = "0004_sponsor_branding"
down_revision = "0003_disable_face_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
