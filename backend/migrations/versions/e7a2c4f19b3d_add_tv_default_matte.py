"""Add the per-TV default matte

Additive and nullable, so an existing database keeps behaving exactly as before: a
TV with no default configured uploads with the app's own "none" default, same as now.

Checked first. The app calls db.create_all() when it starts, so on a fresh install the
column is already there by the time alembic runs with an empty alembic_version.

Revision ID: e7a2c4f19b3d
Revises: d3f1a7c25b90
Create Date: 2026-08-15 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7a2c4f19b3d'
down_revision = 'd3f1a7c25b90'
branch_labels = None
depends_on = None


def _columns(table):
    return {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if 'default_matte' not in _columns('tv'):
        with op.batch_alter_table('tv', schema=None) as batch_op:
            batch_op.add_column(sa.Column('default_matte', sa.String(length=64), nullable=True))


def downgrade():
    if 'default_matte' in _columns('tv'):
        with op.batch_alter_table('tv', schema=None) as batch_op:
            batch_op.drop_column('default_matte')
