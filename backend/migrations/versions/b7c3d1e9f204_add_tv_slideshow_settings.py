"""Add the per-TV slideshow settings

Additive and off by default, so an existing database behaves exactly as before until
a slideshow is configured.

Revision ID: b7c3d1e9f204
Revises: 601a7cee3cbb
Create Date: 2026-08-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c3d1e9f204'
down_revision = '601a7cee3cbb'
branch_labels = None
depends_on = None


COLUMNS = [
    ('slideshow_enabled', sa.Column('slideshow_enabled', sa.Boolean(), nullable=False, server_default=sa.text('0'))),
    ('slideshow_album_id', sa.Column('slideshow_album_id', sa.Integer(), nullable=True)),
    ('slideshow_interval_minutes', sa.Column('slideshow_interval_minutes', sa.Integer(), nullable=True)),
    ('slideshow_last_run', sa.Column('slideshow_last_run', sa.DateTime(), nullable=True)),
    ('slideshow_last_content_id', sa.Column('slideshow_last_content_id', sa.String(length=255), nullable=True)),
]


def _existing_columns():
    return {column['name'] for column in sa.inspect(op.get_bind()).get_columns('tv')}


def upgrade():
    # create_all() runs when the app starts, so on a fresh install these columns may
    # already exist by the time this runs. Adding them again would abort the upgrade.
    present = _existing_columns()
    missing = [column for name, column in COLUMNS if name not in present]
    if missing:
        with op.batch_alter_table('tv', schema=None) as batch_op:
            for column in missing:
                batch_op.add_column(column)


def downgrade():
    present = _existing_columns()
    to_drop = [name for name, _ in reversed(COLUMNS) if name in present]
    if to_drop:
        with op.batch_alter_table('tv', schema=None) as batch_op:
            for name in to_drop:
                batch_op.drop_column(name)
