"""Add the image content hash and the per-TV slideshow settings

Both are additive and nullable (or default to off), so an existing database keeps
behaving exactly as before until the new features are used.

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


def upgrade():
    with op.batch_alter_table('image', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sha256', sa.String(length=64), nullable=True))
        batch_op.create_index(batch_op.f('ix_image_sha256'), ['sha256'], unique=False)

    with op.batch_alter_table('tv', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('slideshow_enabled', sa.Boolean(), nullable=False, server_default=sa.text('0'))
        )
        batch_op.add_column(sa.Column('slideshow_album_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('slideshow_interval_minutes', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('slideshow_last_run', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('slideshow_last_content_id', sa.String(length=255), nullable=True))
        batch_op.create_foreign_key('fk_tv_slideshow_album', 'album', ['slideshow_album_id'], ['id'])


def downgrade():
    with op.batch_alter_table('tv', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tv_slideshow_album', type_='foreignkey')
        batch_op.drop_column('slideshow_last_content_id')
        batch_op.drop_column('slideshow_last_run')
        batch_op.drop_column('slideshow_interval_minutes')
        batch_op.drop_column('slideshow_album_id')
        batch_op.drop_column('slideshow_enabled')

    with op.batch_alter_table('image', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_image_sha256'))
        batch_op.drop_column('sha256')
