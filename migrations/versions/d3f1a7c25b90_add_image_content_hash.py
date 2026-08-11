"""Add the image content hash

Additive and nullable, so an existing database keeps behaving exactly as before:
rows that predate the column simply have no hash until the file is uploaded again.

Every step checks first. The app calls db.create_all() when it starts, so on a fresh
install the table already carries this column by the time alembic runs with an empty
alembic_version — adding it again would abort the upgrade and leave the container
restarting.

Revision ID: d3f1a7c25b90
Revises: b7c3d1e9f204
Create Date: 2026-08-11 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3f1a7c25b90'
down_revision = 'b7c3d1e9f204'
branch_labels = None
depends_on = None


def _columns(table):
    return {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table):
    return {index['name'] for index in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade():
    if 'sha256' not in _columns('image'):
        with op.batch_alter_table('image', schema=None) as batch_op:
            batch_op.add_column(sa.Column('sha256', sa.String(length=64), nullable=True))

    # Kept out of the batch above: creating an index inside one makes alembic rebuild
    # the table, which is what trips over the column create_all already added.
    if 'ix_image_sha256' not in _indexes('image'):
        op.create_index('ix_image_sha256', 'image', ['sha256'], unique=False)


def downgrade():
    if 'ix_image_sha256' in _indexes('image'):
        op.drop_index('ix_image_sha256', table_name='image')
    if 'sha256' in _columns('image'):
        with op.batch_alter_table('image', schema=None) as batch_op:
            batch_op.drop_column('sha256')
