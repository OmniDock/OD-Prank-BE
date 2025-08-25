"""merge heads

Revision ID: 36b4c04da470
Revises: 672105e844a5, 9f3a2b1c0dfe
Create Date: 2025-08-25 15:38:19.412237

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '36b4c04da470'
down_revision: Union[str, Sequence[str], None] = ('672105e844a5', '9f3a2b1c0dfe')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
