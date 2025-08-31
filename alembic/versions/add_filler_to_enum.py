# File: /Users/sebastianroedling/Desktop/OD-Prank/OD-Prank-BE/alembic/versions/add_filler_to_enum.py
"""add filler to voicelinetypeenum

Revision ID: add_filler_to_enum
Revises: b99384b1657a
Create Date: 2024-12-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_filler_to_enum'
down_revision: Union[str, Sequence[str], None] = 'b99384b1657a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add FILLER value to voicelinetypeenum."""
    # PostgreSQL-specific: Add new value to existing enum type
    op.execute("ALTER TYPE voicelinetypeenum ADD VALUE IF NOT EXISTS 'FILLER'")


def downgrade() -> None:
    """Downgrade not supported for enum value removal."""
    # Note: PostgreSQL doesn't support removing values from enums
    # This is a one-way migration
    pass