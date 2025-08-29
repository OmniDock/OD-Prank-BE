"""adding_question_and_answers_to_scenario

Revision ID: 43230b9564a5
Revises: 3504d33ce848
Create Date: 2025-08-29 20:10:35.260035

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '43230b9564a5'
down_revision: Union[str, Sequence[str], None] = '3504d33ce848'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
