"""setting target name nullable for scenarios

Revision ID: 79a3bd0042e5
Revises: dd4e272a520a
Create Date: 2025-09-04 12:21:01.884066

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '79a3bd0042e5'
down_revision: Union[str, Sequence[str], None] = 'dd4e272a520a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('scenarios', 'target_name', existing_type=sa.String(length=255), nullable=True)

def downgrade() -> None:
    op.alter_column('scenarios', 'target_name', existing_type=sa.String(length=255), nullable=False)