"""initial migration — all 12 tables + unmatched_studies + indexes

Revision ID: 001_initial
Revises:
Create Date: 2026-06-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSON

# revision identifiers
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Organizations
    op.create_table(
        'organizations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name_ru', sa.String(200), nullable=False),
        sa.Column('name_kz', sa.String(200)),
        sa.Column('license_number', sa.String(50)),
        sa.Column('address', sa.Text),
        sa.Column('phone', sa.String(20)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

    # Services (тарификатор)
    op.create_table(
        'services',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('code_gombp', sa.String(20), nullable=False),
        sa.Column('code_osms', sa.String(20)),
        sa.Column('name_ru', sa.String(300), nullable=False),
        sa.Column('name_kz', sa.String(300)),
        sa.Column('modality', sa.String(10), nullable=False),
        sa.Column('body_part', sa.String(100)),
        sa.Column('tariff_gombp', sa.Numeric(10, 2)),
        sa.Column('tariff_osms', sa.Numeric(10, 2)),
        sa.Column('tariff_paid', sa.Numeric(10, 2)),
        sa.Column('duration_min', sa.Integer, nullable=False, server_default='20'),
        sa.Column('contrast_agent', sa.Boolean, server_default='FALSE'),
        sa.Column('valid_from', sa.Date, nullable=False, server_default=sa.text("'2020-07-01'")),
        sa.Column('valid_to', sa.Date),
        sa.Column('version', sa.Integer, nullable=False, server_default='1'),
        sa.Column('is_active', sa.Boolean, server_default='TRUE'),
    )

    # ICD-10
    op.create_table(
        'diagnosis_icd',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('code', sa.String(10), unique=True, nullable=False),
        sa.Column('name_ru', sa.String(300), nullable=False),
        sa.Column('name_kz', sa.String(300)),
        sa.Column('chapter', sa.String(5)),
        sa.Column('chapter_name_ru', sa.String(200)),
        sa.Column('is_leaf', sa.Boolean, server_default='TRUE'),
    )

    # Devices
    op.create_table(
        'devices',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', UUID(as_uuid=True), sa.ForeignKey('organizations.id')),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('modality_type', sa.String(10), nullable=False),
        sa.Column('ae_title', sa.String(16), unique=True, nullable=False),
        sa.Column('ip_address', sa.String(15)),
        sa.Column('dicom_port', sa.Integer, server_default='104'),
        sa.Column('schedule_start', sa.Time, server_default=sa.text("'08:00'")),
        sa.Column('schedule_end', sa.Time, server_default=sa.text("'18:00'")),
        sa.Column('working_days', ARRAY(sa.Integer), server_default='{1,2,3,4,5}'),
        sa.Column('status', sa.String(20), server_default='ACTIVE'),
        sa.Column('notes', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

    # Protocol Templates
    op.create_table(
        'protocol_templates',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', UUID(as_uuid=True), sa.ForeignKey('organizations.id')),
        sa.Column('name_ru', sa.String(200), nullable=False),
        sa.Column('name_kz', sa.String(200)),
        sa.Column('modality', sa.String(10), nullable=False),
        sa.Column('body_part', sa.String(100)),
        sa.Column('service_id', UUID(as_uuid=True), sa.ForeignKey('services.id')),
        sa.Column('fields_schema', JSON, server_default='[]'),
        sa.Column('description_template', sa.Text),
        sa.Column('conclusion_template', sa.Text),
        sa.Column('version', sa.String(10), nullable=False, server_default='1'),
        sa.Column('is_active', sa.Boolean, server_default='TRUE'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

    # Users
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', UUID(as_uuid=True), sa.ForeignKey('organizations.id')),
        sa.Column('login', sa.String(50), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(200), nullable=False),
        sa.Column('role', sa.String(30), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('middle_name', sa.String(100)),
        sa.Column('specialization', sa.String(200)),
        sa.Column('license_number', sa.String(50)),
        sa.Column('email', sa.String(200)),
        sa.Column('phone', sa.String(20)),
        sa.Column('default_device_id', UUID(as_uuid=True), sa.ForeignKey('devices.id')),
        sa.Column('is_active', sa.Boolean, server_default='TRUE'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

    # Patients
    op.create_table(
        'patients',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', UUID(as_uuid=True), sa.ForeignKey('organizations.id')),
        sa.Column('iin', sa.String(12), unique=True, nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('middle_name', sa.String(100)),
        sa.Column('birth_date', sa.Date, nullable=False),
        sa.Column('gender', sa.String(1), nullable=False),
        sa.Column('phone', sa.String(20)),
        sa.Column('email', sa.String(200)),
        sa.Column('benefit_category', sa.String(20), server_default='NONE'),
        sa.Column('document_type', sa.String(20)),
        sa.Column('document_number', sa.String(50)),
        sa.Column('notes', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id')),
    )

    # Orders
    op.create_table(
        'orders',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', UUID(as_uuid=True), sa.ForeignKey('organizations.id')),
        sa.Column('accession_number', sa.String(16), unique=True, nullable=False),
        sa.Column('patient_id', UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('service_id', UUID(as_uuid=True), sa.ForeignKey('services.id'), nullable=False),
        sa.Column('modality', sa.String(10), nullable=False),
        sa.Column('body_part', sa.String(100)),
        sa.Column('priority', sa.String(10), nullable=False, server_default='ROUTINE'),
        sa.Column('financing_type', sa.String(10), nullable=False, server_default='PAID'),
        sa.Column('referring_physician_id', UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('referring_physician_name', sa.String(200)),
        sa.Column('diagnosis_icd_id', UUID(as_uuid=True), sa.ForeignKey('diagnosis_icd.id')),
        sa.Column('clinical_notes', sa.Text),
        sa.Column('contrast_agent', sa.Boolean, server_default='FALSE'),
        sa.Column('status', sa.String(20), nullable=False, server_default='NEW'),
        sa.Column('cancelled_reason', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id')),
    )

    # Appointments
    op.create_table(
        'appointments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('order_id', UUID(as_uuid=True), sa.ForeignKey('orders.id'), unique=True, nullable=False),
        sa.Column('device_id', UUID(as_uuid=True), sa.ForeignKey('devices.id'), nullable=False),
        sa.Column('technologist_id', UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('slot_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('slot_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notes', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

    # Studies
    op.create_table(
        'studies',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('order_id', UUID(as_uuid=True), sa.ForeignKey('orders.id'), unique=True, nullable=False),
        sa.Column('study_instance_uid', sa.String(64), unique=True),
        sa.Column('orthanc_study_id', sa.String(64)),
        sa.Column('technologist_id', UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('acquired_at', sa.DateTime(timezone=True)),
        sa.Column('qc_status', sa.String(10)),
        sa.Column('qc_attempts', JSON, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

    # Reports
    op.create_table(
        'reports',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('order_id', UUID(as_uuid=True), sa.ForeignKey('orders.id'), nullable=False),
        sa.Column('radiologist_id', UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('protocol_template_id', UUID(as_uuid=True), sa.ForeignKey('protocol_templates.id')),
        sa.Column('structured_fields', JSON, server_default='{}'),
        sa.Column('description_text', sa.Text),
        sa.Column('conclusion_text', sa.Text),
        sa.Column('critical_finding', sa.Boolean, server_default='FALSE'),
        sa.Column('diagnosis_icd_codes', ARRAY(sa.String(10)), server_default='{}'),
        sa.Column('status', sa.String(10), nullable=False, server_default='DRAFT'),
        sa.Column('version', sa.String(10), nullable=False, server_default='1'),
        sa.Column('parent_report_id', UUID(as_uuid=True), sa.ForeignKey('reports.id')),
        sa.Column('second_opinion_of_report_id', UUID(as_uuid=True), sa.ForeignKey('reports.id')),
        sa.Column('signed_at', sa.DateTime(timezone=True)),
        sa.Column('content_hash', sa.String(64)),
        sa.Column('issued_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

    # Audit Log
    op.create_table(
        'audit_log',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', UUID(as_uuid=True)),
        sa.Column('action', sa.String(20), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('before_json', JSON),
        sa.Column('after_json', JSON),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('session_id', sa.String(100)),
    )

    # Unmatched Studies (for DICOM studies without a matching order)
    op.create_table(
        'unmatched_studies',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('study_instance_uid', sa.String(64), unique=True, nullable=False),
        sa.Column('accession_number', sa.String(16)),
        sa.Column('orthanc_study_id', sa.String(64)),
        sa.Column('patient_id_dicom', sa.String(100)),
        sa.Column('patient_name_dicom', sa.String(200)),
        sa.Column('modality', sa.String(10)),
        sa.Column('study_date', sa.String(8)),
        sa.Column('raw_payload', JSON),
        sa.Column('resolved', sa.String(1), server_default='N'),
        sa.Column('resolved_order_id', UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

    # Performance indexes (from EPIC-MVP)
    op.create_index('idx_orders_patient', 'orders', ['patient_id'])
    op.create_index('idx_orders_status', 'orders', ['status'])
    op.create_index('idx_orders_an', 'orders', ['accession_number'])
    op.create_index('idx_reports_order', 'reports', ['order_id'])
    op.create_index('idx_audit_entity', 'audit_log', ['entity_type', 'entity_id'])
    op.create_index('idx_audit_user', 'audit_log', ['user_id', 'timestamp'])
    op.create_index('idx_patients_iin', 'patients', ['iin'])
    op.create_index('idx_appointments_device_slot', 'appointments', ['device_id', 'slot_start'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_appointments_device_slot', table_name='appointments')
    op.drop_index('idx_patients_iin', table_name='patients')
    op.drop_index('idx_audit_user', table_name='audit_log')
    op.drop_index('idx_audit_entity', table_name='audit_log')
    op.drop_index('idx_reports_order', table_name='reports')
    op.drop_index('idx_orders_an', table_name='orders')
    op.drop_index('idx_orders_status', table_name='orders')
    op.drop_index('idx_orders_patient', table_name='orders')

    # Drop tables in reverse order
    op.drop_table('unmatched_studies')
    op.drop_table('audit_log')
    op.drop_table('reports')
    op.drop_table('studies')
    op.drop_table('appointments')
    op.drop_table('orders')
    op.drop_table('patients')
    op.drop_table('users')
    op.drop_table('protocol_templates')
    op.drop_table('devices')
    op.drop_table('diagnosis_icd')
    op.drop_table('services')
    op.drop_table('organizations')
