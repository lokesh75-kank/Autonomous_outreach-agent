"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2024-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('source', sa.Enum('jobright', 'linkedin', 'greenhouse', 'lever', 'manual', name='jobsource'), nullable=False),
        sa.Column('external_id', sa.String(255), nullable=True),
        sa.Column('url', sa.String(2048), nullable=False),
        sa.Column('url_hash', sa.String(64), nullable=False),
        sa.Column('company', sa.String(255), nullable=False),
        sa.Column('role', sa.String(255), nullable=False),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('skills', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('salary_range', sa.String(100), nullable=True),
        sa.Column('posted_date', sa.DateTime(), nullable=True),
        sa.Column('status', sa.Enum('new', 'processed', 'expired', 'skipped', name='jobstatus'), nullable=False),
        sa.Column('discovered_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url'),
        sa.UniqueConstraint('url_hash')
    )
    op.create_index('ix_jobs_url_hash', 'jobs', ['url_hash'])

    op.create_table(
        'hiring_managers',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('linkedin_url', sa.String(2048), nullable=False),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('relevance_score', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('discovered_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'outreach_queue',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('hiring_manager_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum(
            'pending_enrichment', 'pending_message', 'pending_approval',
            'approved', 'rejected', 'sent', 'accepted', 'replied', 'cold', 'error',
            name='outreachstatus'
        ), nullable=False),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('replied_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['hiring_manager_id'], ['hiring_managers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'outreach_logs',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('outreach_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('result', sa.String(50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['outreach_id'], ['outreach_queue.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'follow_ups',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('outreach_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('type', sa.Enum('follow_up_1', 'follow_up_2', 'thank_you', 'resume', name='followuptype'), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('scheduled_for', sa.DateTime(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'sent', 'cancelled', name='followupstatus'), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['outreach_id'], ['outreach_queue.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'user_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('resume_text', sa.Text(), nullable=True),
        sa.Column('linkedin_url', sa.String(2048), nullable=True),
        sa.Column('target_roles', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('target_locations', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('target_companies', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('skills', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('experience_summary', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('user_profiles')
    op.drop_table('follow_ups')
    op.drop_table('outreach_logs')
    op.drop_table('outreach_queue')
    op.drop_table('hiring_managers')
    op.drop_table('jobs')
    
    op.execute('DROP TYPE IF EXISTS followupstatus')
    op.execute('DROP TYPE IF EXISTS followuptype')
    op.execute('DROP TYPE IF EXISTS outreachstatus')
    op.execute('DROP TYPE IF EXISTS jobstatus')
    op.execute('DROP TYPE IF EXISTS jobsource')
