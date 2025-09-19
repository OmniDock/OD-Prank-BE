"""restore missing placeholder migration

Revision ID: 9cffc3c9b0d3
Revises: 6a892f7830bb
Create Date: 2025-02-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op  # noqa: F401  # imported for alembic compatibility
import sqlalchemy as sa  # noqa: F401  # imported for alembic compatibility


# revision identifiers, used by Alembic.
revision: str = "9cffc3c9b0d3"
down_revision: Union[str, Sequence[str], None] = "6a892f7830bb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op placeholder to preserve Alembic history."""
    pass


def downgrade() -> None:
    """No-op placeholder to preserve Alembic history."""
    pass
