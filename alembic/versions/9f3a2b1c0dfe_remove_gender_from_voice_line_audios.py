"""remove gender from voice_line_audios

Revision ID: 9f3a2b1c0dfe
Revises: 8729ebfa06c4
Create Date: 2025-08-25 14:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f3a2b1c0dfe'
down_revision: Union[str, Sequence[str], None] = '8729ebfa06c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: drop gender column and enum type."""
    with op.batch_alter_table('voice_line_audios') as batch_op:
        batch_op.drop_column('gender')
    # Drop the enum type if it exists (PostgreSQL)
    try:
        op.execute("DROP TYPE IF EXISTS genderenum")
    except Exception:
        # If DB doesn't support or type not present, ignore
        pass


def downgrade() -> None:
    """Downgrade schema: re-add gender column and enum type."""
    # Recreate the enum type
    gender_enum = sa.Enum('MALE', 'FEMALE', name='genderenum')
    gender_enum.create(op.get_bind(), checkfirst=True)
    with op.batch_alter_table('voice_line_audios') as batch_op:
        batch_op.add_column(sa.Column('gender', gender_enum, nullable=True))


