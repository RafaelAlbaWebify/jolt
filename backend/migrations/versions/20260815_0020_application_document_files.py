"""Add durable application document file storage.

Revision ID: 20260815_0020
Revises: 20260811_0019
"""

import sqlalchemy as sa
from alembic import op

revision = "20260815_0020"
down_revision = "20260811_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "application_documents",
        sa.Column(
            "stored_filename",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "application_documents",
        sa.Column(
            "mime_type",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "application_documents",
        sa.Column(
            "file_size",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "application_documents",
        sa.Column(
            "file_sha256",
            sa.String(length=64),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "application_documents",
        sa.Column("file_content", sa.LargeBinary(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("application_documents", "file_content")
    op.drop_column("application_documents", "file_sha256")
    op.drop_column("application_documents", "file_size")
    op.drop_column("application_documents", "mime_type")
    op.drop_column("application_documents", "stored_filename")
