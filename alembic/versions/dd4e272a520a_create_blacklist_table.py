"""create blacklist table

Revision ID: dd4e272a520a
Revises: a5354dbfc6be
Create Date: 2025-09-03 16:15:07.788655

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd4e272a520a'
down_revision: Union[str, Sequence[str], None] = 'a5354dbfc6be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'blacklist',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('phone_number', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.UniqueConstraint('phone_number'),
    )

def downgrade() -> None:
    op.drop_table('blacklist')
