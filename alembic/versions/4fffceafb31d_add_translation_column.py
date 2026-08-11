"""add translation column

Revision ID: 4fffceafb31d
Revises: 8914cadfb1fd
Create Date: 2026-07-22 22:58:23.073031
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '4fffceafb31d'
down_revision: Union[str, None] = '8914cadfb1fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('generated_content', sa.Column('reel_title', sa.Text(), nullable=True))
    op.add_column('generated_content', sa.Column('viral_score', sa.Integer(), nullable=True))
    op.add_column('generated_content', sa.Column('viral_score_reason', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('generated_content', 'viral_score_reason')
    op.drop_column('generated_content', 'viral_score')
    op.drop_column('generated_content', 'reel_title')
