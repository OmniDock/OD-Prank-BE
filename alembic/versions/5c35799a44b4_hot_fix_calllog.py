"""hot fix calllog

Revision ID: 5c35799a44b4
Revises: 5e7be2795034
Create Date: 2025-09-09 14:58:33.465260

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5c35799a44b4'
down_revision: Union[str, Sequence[str], None] = '5e7be2795034'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    # Rename 'metadata' column to 'call_metadata'
    op.alter_column('call_log', 'metadata', new_column_name='call_metadata')

def downgrade() -> None:
    # Revert the column name back to 'metadata'
    op.alter_column('call_log', 'call_metadata', new_column_name='metadata')