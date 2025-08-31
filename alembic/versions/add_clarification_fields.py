"""add clarification fields to scenario

Revision ID: add_clarification_fields
Revises: 3504d33ce848
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_clarification_fields'
down_revision: Union[str, None] = '3504d33ce848'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add clarification fields
    op.add_column('scenarios', sa.Column('clarifying_questions', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('scenarios', sa.Column('clarifications', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    
    # Add quality tracking field
    op.add_column('scenarios', sa.Column('was_rewritten', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    # Remove columns
    op.drop_column('scenarios', 'was_rewritten')
    op.drop_column('scenarios', 'clarifications')
    op.drop_column('scenarios', 'clarifying_questions')
