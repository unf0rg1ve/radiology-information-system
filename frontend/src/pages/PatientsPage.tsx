import React, { useState, useEffect } from 'react';
import {
  Card, Table, Input, Button, Modal, Form, FormInstance, Select, DatePicker,
  message, Space, Tag, Typography, Row, Col, Spin, Drawer, Descriptions, List,
} from 'antd';
import {
  SearchOutlined, PlusOutlined, UserOutlined,
  FileTextOutlined, HistoryOutlined, EditOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { patientsApi } from '../api/client';
import { handleApiError } from '../api/errorHandler';

const { Title, Text } = Typography;

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  NEW: { label: 'Новое', color: 'blue' },
  SCHEDULED: { label: 'Запланировано', color: 'green' },
  ARRIVED: { label: 'Прибыл', color: 'cyan' },
  IN_PROGRESS: { label: 'В работе', color: 'orange' },
  ACQUIRED: { label: 'Снимки', color: 'purple' },
  TO_REPORT: { label: 'К описанию', color: 'volcano' },
  REPORTING: { label: 'Описывается', color: 'geekblue' },
  SIGNED: { label: 'Подписано', color: 'success' },
  ISSUED: { label: 'Выдано', color: 'default' },
  CANCELLED: { label: 'Отменено', color: 'red' },
};

export const PatientsPage: React.FC = () => {
  const { t } = useTranslation();
  const [patients, setPatients] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editModal, setEditModal] = useState<{ open: boolean; patient: any }>({ open: false, patient: null });
  const [historyDrawer, setHistoryDrawer] = useState<{ open: boolean; patientId: string; data: any }>({
    open: false, patientId: '', data: null,
  });
  const [historyLoading, setHistoryLoading] = useState(false);
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();
  const navigate = useNavigate();

  const fetchPatients = async () => {
    setLoading(true);
    try {
      const response = await patientsApi.list({ search: debouncedSearch || undefined, limit: 50 });
      setPatients(response.data || []);
    } catch (error) {
      message.error(t('common.error'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPatients();
  }, [debouncedSearch]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const handleCreate = async (values: any) => {
    try {
      await patientsApi.create({
        ...values,
        birth_date: values.birth_date.format('YYYY-MM-DD'),
      });
      message.success(t('common.success'));
      setModalOpen(false);
      form.resetFields();
      fetchPatients();
    } catch (error: any) {
      handleApiError(error, form);
    }
  };

  const handleEdit = async (values: any) => {
    try {
      await patientsApi.update(editModal.patient.id, {
        ...values,
        birth_date: values.birth_date?.format('YYYY-MM-DD'),
      });
      message.success(t('common.success'));
      setEditModal({ open: false, patient: null });
      editForm.resetFields();
      fetchPatients();
    } catch (error: any) {
      handleApiError(error, editForm);
    }
  };

  const openHistory = async (patientId: string) => {
    setHistoryDrawer({ open: true, patientId, data: null });
    setHistoryLoading(true);
    try {
      const response = await patientsApi.history(patientId);
      setHistoryDrawer({ open: true, patientId, data: response.data });
    } catch (error) {
      message.error(t('common.error'));
    } finally {
      setHistoryLoading(false);
    }
  };

  const openEdit = (patient: any) => {
    editForm.setFieldsValue({
      ...patient,
      birth_date: patient.birth_date ? dayjs(patient.birth_date) : null,
    });
    setEditModal({ open: true, patient });
  };

  const columns = [
    {
      title: t('patients.iin'),
      dataIndex: 'iin',
      key: 'iin',
      width: 120,
      render: (v: string) => <code style={{ fontSize: 11 }}>{v}</code>,
    },
    {
      title: t('patients.lastName'),
      dataIndex: 'full_name',
      key: 'name',
      render: (v: string) => (
        <Space><UserOutlined style={{ color: 'var(--c-accent)' }} /><span style={{ fontWeight: 500 }}>{v}</span></Space>
      ),
    },
    {
      title: t('patients.birthDate'),
      dataIndex: 'birth_date',
      key: 'birth_date',
      width: 120,
      render: (v: string) => v ? dayjs(v).format('DD.MM.YYYY') : '-',
    },
    {
      title: t('patients.phone'),
      dataIndex: 'phone',
      key: 'phone',
      width: 140,
    },
    {
      title: t('patients.benefitCategory'),
      dataIndex: 'benefit_category',
      key: 'benefit',
      width: 100,
      render: (v: string) => {
        const colors: Record<string, string> = { GOMBP: 'blue', OSMS: 'green', DISABLED: 'orange', NONE: 'default' };
        const labels: Record<string, string> = { GOMBP: 'ГОБМП', OSMS: 'ОСМС', DISABLED: 'Инвалид', NONE: '-' };
        return v !== 'NONE' ? <Tag color={colors[v]}>{labels[v]}</Tag> : '-';
      },
    },
    {
      title: t('patients.lastStatus'),
      dataIndex: 'last_order_status',
      key: 'lastOrderStatus',
      width: 100,
      render: (v: string) => v ? (
        <span className={`status-badge status-${v.toLowerCase()}`}>
          {(STATUS_MAP[v] || { label: v }).label}
        </span>
      ) : '—',
    },
    {
      title: t('patients.arrivedAt'),
      dataIndex: 'last_order_arrived_at',
      key: 'lastOrderArrivedAt',
      width: 140,
      render: (v: string) => v ? dayjs(v).format('DD.MM.YYYY HH:mm') : '—',
    },
    {
      title: '',
      key: 'actions',
      width: 160,
      render: (_: any, record: any) => (
        <Space size="small">
          <Button type="text" size="small" icon={<EditOutlined />}
            onClick={() => openEdit(record)} title={t('common.edit')} />
          <Button type="text" size="small" icon={<HistoryOutlined />}
            onClick={() => openHistory(record.id)} title={t('patients.history')} />
          <Button type="text" size="small" icon={<FileTextOutlined />}
            onClick={() => navigate(`/orders?patient_id=${record.id}`)} title={t('nav.orders')} />
        </Space>
      ),
    },
  ];

  const renderPatientFormFields = (patientForm: FormInstance) => (
    <>
      <Row gutter={16}>
        <Col span={12}>
          <Form.Item
            name="iin"
            label={t('patients.iin')}
            rules={[
              { required: true, message: 'Введите ИИН' },
              { len: 12, message: 'ИИН должен содержать 12 цифр' },
              { pattern: /^\d{12}$/, message: 'ИИН должен содержать только цифры' },
              {
                validator: (_, value) => {
                  if (!value || value.length < 12) return Promise.resolve();
                  const birthDate = patientForm.getFieldValue('birth_date');
                  if (!birthDate) return Promise.resolve();
                  const year = value.substring(0, 2);
                  const month = value.substring(2, 4);
                  const day = value.substring(4, 6);
                  const iinDate = `${day}.${month}.${year}`;
                  const bd = birthDate.format('DD.MM.YY');
                  if (iinDate !== bd) {
                    return Promise.reject(
                      `Дата рождения не соответствует ИИН (ИИН: ${day}.${month}.${year})`
                    );
                  }
                  return Promise.resolve();
                },
              },
            ]}
          >
            <Input
              maxLength={12}
              placeholder="880312400215"
              onChange={() => patientForm.validateFields(['birth_date', 'iin'])}
            />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="birth_date" label={t('patients.birthDate')} rules={[{ required: true }]}>
            <DatePicker style={{ width: '100%' }} format="DD.MM.YYYY" onChange={() => patientForm.validateFields(['iin'])} />
          </Form.Item>
        </Col>
      </Row>
      <Row gutter={16}>
        <Col span={8}>
          <Form.Item
            name="last_name"
            label={t('patients.lastName')}
            rules={[
              { required: true, message: 'Обязательное поле' },
              {
                pattern: /^[а-яёА-ЯЁa-zA-Z\s\-]+$/,
                message: 'Только буквы и дефис',
              },
            ]}
          >
            <Input />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item
            name="first_name"
            label={t('patients.firstName')}
            rules={[
              { required: true, message: 'Обязательное поле' },
              {
                pattern: /^[а-яёА-ЯЁa-zA-Z\s\-]+$/,
                message: 'Только буквы и дефис',
              },
            ]}
          >
            <Input />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="middle_name" label={t('patients.middleName')}>
            <Input />
          </Form.Item>
        </Col>
      </Row>
      <Row gutter={16}>
        <Col span={8}>
          <Form.Item name="gender" label={t('patients.gender')} rules={[{ required: true }]}>
            <Select options={[{ value: 'M', label: t('patients.male') }, { value: 'F', label: t('patients.female') }]} />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item
            name="phone"
            label={t('patients.phone')}
            rules={[
              {
                pattern: /^(\+7|8|7)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$/,
                message: 'Формат: +7 (777) 123-45-67',
              },
            ]}
          >
            <Input
              placeholder="+7 (701) 234-56-78"
              onChange={(e) => {
                const digits = e.target.value.replace(/\D/g, '');
                let formatted = '';
                if (digits.length > 0) formatted = '+7';
                if (digits.length > 1) formatted += ' (' + digits.substring(1, Math.min(4, digits.length));
                if (digits.length > 4) formatted += ') ' + digits.substring(4, Math.min(7, digits.length));
                if (digits.length > 7) formatted += '-' + digits.substring(7, Math.min(9, digits.length));
                if (digits.length > 9) formatted += '-' + digits.substring(9, Math.min(11, digits.length));
                patientForm.setFieldValue('phone', formatted);
              }}
            />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="benefit_category" label={t('patients.benefitCategory')} initialValue="NONE">
            <Select options={[
              { value: 'NONE', label: t('patients.none') },
              { value: 'GOMBP', label: t('patients.gombp') },
              { value: 'OSMS', label: t('patients.osms') },
            ]} />
          </Form.Item>
        </Col>
      </Row>
      <Form.Item name="notes" label="Примечания">
        <Input.TextArea rows={2} />
      </Form.Item>
    </>
  );

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col><Title level={4} style={{ margin: 0, color: 'var(--c-text)' }}>{t('nav.patients')}</Title></Col>
        <Col><Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>{t('patients.create')}</Button></Col>
      </Row>

      <Card style={{ marginBottom: 16 }} bodyStyle={{ padding: 12 }}>
        <Input placeholder={t('patients.search')} prefix={<SearchOutlined />}
          value={search} onChange={(e) => setSearch(e.target.value)} allowClear style={{ maxWidth: 400 }} />
      </Card>

      <Spin spinning={loading}>
        <Table dataSource={patients} columns={columns} rowKey="id" size="small" pagination={{ pageSize: 20 }} />
      </Spin>

      <Modal title={t('patients.create')} open={modalOpen}
        onCancel={() => { setModalOpen(false); form.resetFields(); }}
        onOk={() => form.submit()} width={600}>
        <Form form={form} layout="vertical" onFinish={handleCreate}>{renderPatientFormFields(form)}</Form>
      </Modal>

      <Modal title={t('common.edit')} open={editModal.open}
        onCancel={() => { setEditModal({ open: false, patient: null }); editForm.resetFields(); }}
        onOk={() => editForm.submit()} width={600}>
        <Form form={editForm} layout="vertical" onFinish={handleEdit}>{renderPatientFormFields(editForm)}</Form>
      </Modal>

      <Drawer title={t('patients.history')} open={historyDrawer.open} width={500}
        onClose={() => setHistoryDrawer({ open: false, patientId: '', data: null })}>
        <Spin spinning={historyLoading}>
          {historyDrawer.data ? (
            <>
              <Descriptions bordered size="small" column={1} style={{ marginBottom: 16 }}>
                <Descriptions.Item label={t('patients.lastName')}>{historyDrawer.data.patient_name}</Descriptions.Item>
                <Descriptions.Item label="Всего">{historyDrawer.data.total} исследований</Descriptions.Item>
              </Descriptions>
              <List
                dataSource={historyDrawer.data.orders || []}
                renderItem={(order: any) => (
                  <List.Item>
                    <Space direction="vertical" size={0} style={{ width: '100%' }}>
                      <Space>
                        <code style={{ fontSize: 11 }}>{order.accession_number}</code>
                        <Tag>{order.modality}</Tag>
                        <span className={`status-badge status-${order.status?.toLowerCase()}`}>
                          {STATUS_MAP[order.status]?.label || order.status}
                        </span>
                      </Space>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        {order.service_name} · {order.body_part || '—'} · {order.created_at ? dayjs(order.created_at).format('DD.MM.YYYY HH:mm') : ''}
                      </Text>
                    </Space>
                  </List.Item>
                )}
              />
            </>
          ) : (
            <Text type="secondary">{t('common.noData')}</Text>
          )}
        </Spin>
      </Drawer>
    </div>
  );
};
