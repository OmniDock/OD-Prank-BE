"""add retry attempts to voice line audios

Revision ID: 1d4d16c1fd3a
Revises: 9cffc3c9b0d3
Create Date: 2025-02-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d4d16c1fd3a'
down_revision: Union[str, Sequence[str], None] = '9cffc3c9b0d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'voice_line_audios',
        sa.Column('retry_attempts', sa.Integer(), nullable=False, server_default='0'),
    )
    op.execute("UPDATE voice_line_audios SET retry_attempts = 0 WHERE retry_attempts IS NULL")
    op.alter_column('voice_line_audios', 'retry_attempts', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('voice_line_audios', 'retry_attempts')
