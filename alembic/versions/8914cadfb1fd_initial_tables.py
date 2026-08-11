"""initial tables

Revision ID: 8914cadfb1fd
Revises: 
Create Date: 2026-07-22 16:53:43.313852
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '8914cadfb1fd'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('email', sa.String(length=255), unique=True, index=True, nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_admin', sa.Boolean(), default=False),
        sa.Column('is_banned', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        'posts',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('media_type', sa.String(length=50), nullable=False),
        sa.Column('media_path', sa.String(length=500), nullable=True),
        sa.Column('original_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        'generated_content',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('post_id', sa.Integer(), sa.ForeignKey('posts.id'), nullable=False),
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('hashtags', sa.Text(), nullable=True),
        sa.Column('keywords', sa.Text(), nullable=True),
        sa.Column('emojis', sa.Text(), nullable=True),
        sa.Column('cta', sa.Text(), nullable=True),
        sa.Column('hook', sa.Text(), nullable=True),
        sa.Column('reel_title', sa.Text(), nullable=True),
        sa.Column('seo_tags', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('translation', sa.Text(), nullable=True),
        sa.Column('viral_score', sa.Integer(), nullable=True),
        sa.Column('viral_score_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('generated_content')
    op.drop_table('posts')
    op.drop_table('users')
