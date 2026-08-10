"""Add the image content hash and the per-TV slideshow settings

Both are additive and nullable (or default to off), so an existing database keeps
behaving exactly as before until the new features are used.

Every step checks first. The app calls db.create_all() when it starts, so on a fresh
install the tables already carry these columns by the time alembic runs with an empty
alembic_version — adding them again would abort the upgrade and leave the container
restarting.

Revision ID: c1d2e3f4a5b6
Revises: 601a7cee3cbb
Create Date: 2026-08-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1d2e3f4a5b6'
down_revision = '601a7cee3cbb'
branch_labels = None
depends_on = None


def _columns(table):
    return {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table):
    return {index['name'] for index in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade():
    missing_image = [
        column for column in [
            sa.Column('sha256', sa.String(length=64), nullable=True),
        ] if column.name not in _columns('image')
    ]
    if missing_image:
        with op.batch_alter_table('image', schema=None) as batch_op:
            for column in missing_image:
                batch_op.add_column(column)

    # Kept out of the batch above: creating an index inside one makes alembic rebuild
    # the table, which is what trips over the column that create_all already added.
    if 'ix_image_sha256' not in _indexes('image'):
        op.create_index('ix_image_sha256', 'image', ['sha256'], unique=False)

    missing_tv = [
        column for column in [
            sa.Column('slideshow_enabled', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('slideshow_album_id', sa.Integer(), nullable=True),
            sa.Column('slideshow_interval_minutes', sa.Integer(), nullable=True),
            sa.Column('slideshow_last_run', sa.DateTime(), nullable=True),
            sa.Column('slideshow_last_content_id', sa.String(length=255), nullable=True),
        ] if column.name not in _columns('tv')
    ]
    if missing_tv:
        with op.batch_alter_table('tv', schema=None) as batch_op:
            for column in missing_tv:
                batch_op.add_column(column)


def downgrade():
    present_tv = _columns('tv')
    slideshow_columns = [
        'slideshow_last_content_id',
        'slideshow_last_run',
        'slideshow_interval_minutes',
        'slideshow_album_id',
        'slideshow_enabled',
    ]
    if any(name in present_tv for name in slideshow_columns):
        with op.batch_alter_table('tv', schema=None) as batch_op:
            for name in slideshow_columns:
                if name in present_tv:
                    batch_op.drop_column(name)

    if 'ix_image_sha256' in _indexes('image'):
        op.drop_index('ix_image_sha256', table_name='image')
    if 'sha256' in _columns('image'):
        with op.batch_alter_table('image', schema=None) as batch_op:
            batch_op.drop_column('sha256')
