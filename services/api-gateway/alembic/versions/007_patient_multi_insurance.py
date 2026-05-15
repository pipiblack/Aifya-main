"""Patient multi-insurance.

Revision ID: 007
Revises: 006
Create Date: 2026-05-15

Adds is_primary and notes columns to patient_insurance so a patient can hold
multiple insurance entries (e.g. SHA + private) with one marked as primary.
The legacy Patient.insurance_provider / insurance_member_number scalar
columns are retained for backwards compatibility but kept in sync with the
primary PatientInsurance row by the service layer.

Soft, additive change — fully reversible.
"""

import sqlalchemy as sa

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add is_primary + notes columns and primary-lookup index."""
    op.add_column(
        "patient_insurance",
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "patient_insurance",
        sa.Column("notes", sa.Text(), nullable=True),
    )

    # Promote the first active insurance entry per patient to primary so existing
    # rows have a sensible default.
    op.execute(
        """
        UPDATE patient_insurance pi
        SET is_primary = TRUE
        WHERE pi.id IN (
            SELECT DISTINCT ON (patient_id) id
            FROM patient_insurance
            WHERE is_deleted = FALSE AND is_active = TRUE
            ORDER BY patient_id, created_at ASC
        )
        """
    )

    op.create_index(
        "ix_patient_insurance_primary",
        "patient_insurance",
        ["patient_id", "is_primary"],
    )


def downgrade() -> None:
    """Drop the added columns and index."""
    op.drop_index("ix_patient_insurance_primary", table_name="patient_insurance")
    op.drop_column("patient_insurance", "notes")
    op.drop_column("patient_insurance", "is_primary")
