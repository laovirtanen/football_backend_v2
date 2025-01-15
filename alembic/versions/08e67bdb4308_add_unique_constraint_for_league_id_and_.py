"""Add unique constraint for league_id and year in seasons

Revision ID: 08e67bdb4308
Revises: 20d19614b566
Create Date: 2024-12-13 18:31:09.754515

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '08e67bdb4308'
down_revision: Union[str, None] = '20d19614b566'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
