"""Fase 2: base experimental

Revision ID: 0002_experimental_base
Revises: 0001_auth
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '0002_experimental_base'
down_revision = '0001_auth'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Gerada por autogenerate a partir das tabelas ORM e revisada.
    op.create_table('spectral_axes',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('axis_hash', sa.String(length=64), nullable=False),
    sa.Column('unit', sa.String(length=8), nullable=False),
    sa.Column('n_points', sa.Integer(), nullable=False),
    sa.Column('values', postgresql.ARRAY(sa.Float(precision=53)), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_spectral_axes')),
    sa.UniqueConstraint('axis_hash', name=op.f('uq_spectral_axes_axis_hash'))
    )
    op.create_table('mapping_templates',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('plan', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_by', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_mapping_templates_created_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_mapping_templates')),
    sa.UniqueConstraint('name', name=op.f('uq_mapping_templates_name'))
    )
    op.create_table('import_batches',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('study_id', sa.String(length=128), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('file_hash', sa.String(length=64), nullable=False),
    sa.Column('storage_key', sa.String(length=512), nullable=False),
    sa.Column('imported_by', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('import_timestamp', sa.DateTime(timezone=True), nullable=True),
    sa.Column('template_id', sa.String(length=32), nullable=True),
    sa.Column('plan', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('report', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['imported_by'], ['users.id'], name=op.f('fk_import_batches_imported_by_users')),
    sa.ForeignKeyConstraint(['template_id'], ['mapping_templates.id'], name=op.f('fk_import_batches_template_id_mapping_templates')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_import_batches'))
    )
    op.create_index(op.f('ix_import_batches_file_hash'), 'import_batches', ['file_hash'], unique=False)
    op.create_index(op.f('ix_import_batches_study_id'), 'import_batches', ['study_id'], unique=False)
    op.create_table('samples',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('study_id', sa.String(length=128), nullable=False),
    sa.Column('sample_id', sa.String(length=128), nullable=False),
    sa.Column('sample_id_raw', sa.String(length=255), nullable=False),
    sa.Column('sample_id_origin', sa.String(length=16), nullable=False),
    sa.Column('genotype', sa.String(length=128), nullable=True),
    sa.Column('cultivar', sa.String(length=128), nullable=True),
    sa.Column('batch', sa.String(length=128), nullable=True),
    sa.Column('lot', sa.String(length=128), nullable=True),
    sa.Column('matrix', sa.String(length=128), nullable=True),
    sa.Column('storage_time', sa.String(length=64), nullable=True),
    sa.Column('storage_condition', sa.String(length=128), nullable=True),
    sa.Column('extra', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('field_origins', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.String(length=32), nullable=False),
    sa.Column('import_batch_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_samples_created_by_users')),
    sa.ForeignKeyConstraint(['import_batch_id'], ['import_batches.id'], name=op.f('fk_samples_import_batch_id_import_batches')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_samples')),
    sa.UniqueConstraint('study_id', 'sample_id', name='uq_samples_study_sample')
    )
    op.create_index(op.f('ix_samples_batch'), 'samples', ['batch'], unique=False)
    op.create_index(op.f('ix_samples_genotype'), 'samples', ['genotype'], unique=False)
    op.create_index(op.f('ix_samples_lot'), 'samples', ['lot'], unique=False)
    op.create_index(op.f('ix_samples_study_id'), 'samples', ['study_id'], unique=False)
    op.create_table('reference_analyses',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('sample_pk', sa.String(length=32), nullable=False),
    sa.Column('parameter', sa.String(length=64), nullable=False),
    sa.Column('value', sa.Float(precision=53), nullable=False),
    sa.Column('unit', sa.String(length=32), nullable=False),
    sa.Column('replicate', sa.Integer(), nullable=False),
    sa.Column('analysis_type', sa.String(length=64), nullable=True),
    sa.Column('method', sa.String(length=128), nullable=True),
    sa.Column('analysis_date', sa.String(length=32), nullable=True),
    sa.Column('laboratory', sa.String(length=128), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('import_batch_id', sa.String(length=32), nullable=True),
    sa.Column('created_by', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_reference_analyses_created_by_users')),
    sa.ForeignKeyConstraint(['import_batch_id'], ['import_batches.id'], name=op.f('fk_reference_analyses_import_batch_id_import_batches')),
    sa.ForeignKeyConstraint(['sample_pk'], ['samples.id'], name=op.f('fk_reference_analyses_sample_pk_samples'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_reference_analyses')),
    sa.UniqueConstraint('sample_pk', 'parameter', 'replicate', name='uq_reference_sample_parameter_replicate')
    )
    op.create_index(op.f('ix_reference_analyses_parameter'), 'reference_analyses', ['parameter'], unique=False)
    op.create_index(op.f('ix_reference_analyses_sample_pk'), 'reference_analyses', ['sample_pk'], unique=False)
    op.create_table('spectra',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('sample_pk', sa.String(length=32), nullable=False),
    sa.Column('axis_id', sa.String(length=32), nullable=False),
    sa.Column('technical_replicate', sa.Integer(), nullable=False),
    sa.Column('signal_type', sa.String(length=16), nullable=False),
    sa.Column('values', postgresql.ARRAY(sa.Float(precision=53)), nullable=False),
    sa.Column('instrument', sa.String(length=128), nullable=True),
    sa.Column('extra', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('provenance', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=False),
    sa.Column('file_hash', sa.String(length=64), nullable=False),
    sa.Column('import_batch_id', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['axis_id'], ['spectral_axes.id'], name=op.f('fk_spectra_axis_id_spectral_axes')),
    sa.ForeignKeyConstraint(['import_batch_id'], ['import_batches.id'], name=op.f('fk_spectra_import_batch_id_import_batches')),
    sa.ForeignKeyConstraint(['sample_pk'], ['samples.id'], name=op.f('fk_spectra_sample_pk_samples'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_spectra')),
    sa.UniqueConstraint('sample_pk', 'technical_replicate', name='uq_spectra_sample_replicate')
    )
    op.create_index(op.f('ix_spectra_sample_pk'), 'spectra', ['sample_pk'], unique=False)


def downgrade() -> None:
    # Gerada por autogenerate a partir das tabelas ORM e revisada.
    op.drop_index(op.f('ix_spectra_sample_pk'), table_name='spectra')
    op.drop_table('spectra')
    op.drop_index(op.f('ix_reference_analyses_sample_pk'), table_name='reference_analyses')
    op.drop_index(op.f('ix_reference_analyses_parameter'), table_name='reference_analyses')
    op.drop_table('reference_analyses')
    op.drop_index(op.f('ix_samples_study_id'), table_name='samples')
    op.drop_index(op.f('ix_samples_lot'), table_name='samples')
    op.drop_index(op.f('ix_samples_genotype'), table_name='samples')
    op.drop_index(op.f('ix_samples_batch'), table_name='samples')
    op.drop_table('samples')
    op.drop_index(op.f('ix_import_batches_study_id'), table_name='import_batches')
    op.drop_index(op.f('ix_import_batches_file_hash'), table_name='import_batches')
    op.drop_table('import_batches')
    op.drop_table('mapping_templates')
    op.drop_table('spectral_axes')
