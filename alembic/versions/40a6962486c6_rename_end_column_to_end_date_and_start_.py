"""Rename 'end' column to 'end_date' and start to start_date in seasons

Revision ID: 40a6962486c6
Revises: 08e67bdb4308
Create Date: 2024-12-13 18:38:19.807504

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '40a6962486c6'
down_revision: Union[str, None] = '08e67bdb4308'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
