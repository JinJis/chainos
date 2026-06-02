"""add research_report to theme

Revision ID: f84a883d5cd6
Revises: 692f664d5bd5
Create Date: 2026-06-02 08:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'f84a883d5cd6'
down_revision: str | None = '692f664d5bd5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('themes', sa.Column('research_report', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('themes', 'research_report')
