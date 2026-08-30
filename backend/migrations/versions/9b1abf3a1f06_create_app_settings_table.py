"""Create app settings table

Revision ID: 9b1abf3a1f06
Revises: ce4757b9dde8
Create Date: 2026-08-30 17:42:25.661731

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9b1abf3a1f06'
down_revision = 'ce4757b9dde8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('app_settings',
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('key')
    )


def downgrade():
    op.drop_table('app_settings')
