import React, { useState, useEffect, useMemo } from 'react';
import {
  Table, Button, Modal, Form, FormInstance, Select, Input, message,
  Space, Tag, Typography, Spin, Row, Col, Popconfirm, Drawer, List, Card,
  DatePicker,
} from 'antd';
import {
  PlusOutlined, FileTextOutlined, StopOutlined, DownloadOutlined,
  EditOutlined, DeleteOutlined, SearchOutlined, HistoryOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import { ordersApi, patientsApi, refsApi } from '../api/client';
import { useAuthStore } from '../stores/authStore';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  NEW: { label: 'Новое', color: 'blue' },
  SCHEDULED: { label: 'Запланировано', color: 'green' },
  ARRIVED: { label: 'Прибыл', color: 'cyan' },
  IN_PROGRESS: { label: 'В работе', color: 'orange' },
  ACQUIRED: { label: 'Снимки получены', color: 'purple' },
  TO_REPORT: { label: 'К описанию', color: 'volcano' },
  REPORTING: { label: 'Описывается', color: 'geekblue' },
  SIGNED: { label: 'Подписано', color: 'success' },
  ISSUED: { label: 'Выдано', color: 'default' },
  CANCELLED: { label: 'Отменено', color: 'red' },
};

const MODALITY_OPTIONS = ['CT', 'MR', 'US', 'MG', 'CR', 'XA', 'OT'];

export const OrdersPage: React.FC = () => {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [cancelModal, setCancelModal] = useState<{ open: boolean; orderId: string }>({ open: false, orderId: '' });
  const [patients, setPatients] = useState<any[]>([]);
  const [services, setServices] = useState<any[]>([]);
  const [icd10, setIcd10] = useState<any[]>([]);
  const [form] = Form.useForm();
  const [cancelForm] = Form.useForm();
  const [editForm] = Form.useForm();
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState<string | undefined>(undefined);
  const [filterModality, setFilterModality] = useState<string | undefined>(undefined);
  const [filterDate, setFilterDate] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);
  const [editModal, setEditModal] = useState<{ open: boolean; order: any }>({ open: false, order: null });
  const [historyDrawer, setHistoryDrawer] = useState<{ open: boolean; orderId: string; data: any }>({
    open: false, orderId: '', data: null,
  });
  const [historyLoading, setHistoryLoading] = useState(false);

  const patientIdFilter = searchParams.get('patient_id');

  const fetchOrders = async () => {
    setLoading(true);
    try {
      const params: any = { limit: 50 };
      if (patientIdFilter) params.patient_id = patientIdFilter;
      if (debouncedSearch) params.search = debouncedSearch;
      if (filterStatus) params.status = filterStatus;
      if (filterModality) params.modality = filterModality;
      if (filterDate?.[0]) params.date_from = filterDate[0].format('YYYY-MM-DD');
      if (filterDate?.[1]) params.date_to = filterDate[1].format('YYYY-MM-DD');
      const response = await ordersApi.list(params);
      setOrders(response.data || []);
    } catch (error) {
      message.error(t('common.error'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders();
  }, [patientIdFilter, debouncedSearch, filterStatus, filterModality, filterDate]);

  const fetchRefs = async () => {
    try {
      const [patRes, svcRes, icdRes] = await Promise.all([
        patientsApi.list({ limit: 100 }),
        refsApi.services(),
        refsApi.icd10({ limit: 100 }),
      ]);
      setPatients(patRes.data || []);
      setServices(svcRes.data || []);
      setIcd10(icdRes.data || []);
    } catch (error) {
      console.error('Failed to load references:', error);
    }
  };

  useEffect(() => {
    fetchRefs();
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const handleCreate = async (values: any) => {
    try {
      const service = services.find((s: any) => s.id === values.service_id);
      await ordersApi.create({
        ...values,
        modality: service?.modality || 'CT',
      });
      message.success(t('common.success'));
      setModalOpen(false);
      form.resetFields();
      fetchOrders();
    } catch (error: any) {
      message.error(error.response?.data?.detail || t('common.error'));
    }
  };

  const handleCancel = async () => {
    try {
      const values = await cancelForm.validateFields();
      await ordersApi.updateStatus(cancelModal.orderId, {
        status: 'CANCELLED',
        reason: values.reason,
      });
      message.success(t('orders.cancel') + 'ено');
      setCancelModal({ open: false, orderId: '' });
      cancelForm.resetFields();
      fetchOrders();
    } catch (error: any) {
      if (error.response) {
        message.error(error.response?.data?.detail || t('common.error'));
      }
    }
  };

  const handleDownloadPdf = (orderId: string) => {
    const token = useAuthStore.getState().token;
    window.open(`/api/orders/${orderId}/pdf?token=${token}`, '_blank');
  };

  const handleEdit = async (values: any) => {
    try {
      await ordersApi.update(editModal.order.id, values);
      message.success(t('orders.updateSuccess'));
      setEditModal({ open: false, order: null });
      editForm.resetFields();
      fetchOrders();
    } catch (error: any) {
      message.error(error.response?.data?.detail || t('common.error'));
    }
  };

  const handleDelete = async (orderId: string) => {
    try {
      await ordersApi.delete(orderId);
      message.success(t('orders.deleteSuccess'));
      fetchOrders();
    } catch (error: any) {
      if (error.response?.status === 409) {
        message.error(t('orders.deleteErrorLinked'));
      } else {
        message.error(error.response?.data?.detail || t('common.error'));
      }
    }
  };

  const openOrderHistory = async (orderId: string) => {
    setHistoryDrawer({ open: true, orderId, data: null });
    setHistoryLoading(true);
    try {
      const response = await ordersApi.history(orderId);
      setHistoryDrawer({ open: true, orderId, data: response.data });
    } catch (error) {
      message.error(t('common.error'));
    } finally {
      setHistoryLoading(false);
    }
  };

  const openEdit = (order: any) => {
    editForm.setFieldsValue({
      patient_id: order.patient_id,
      service_id: order.service_id,
      modality: order.modality,
      body_part: order.body_part,
      diagnosis_icd_id: order.diagnosis_icd_id,
      priority: order.priority,
      financing_type: order.financing_type,
      contrast_agent: order.contrast_agent,
      clinical_notes: order.clinical_notes,
    });
    setEditModal({ open: true, order });
  };

  const renderOrderFormFields = (orderForm: FormInstance) => (
    <>
      <Row gutter={16}>
        <Col span={12}>
          <Form.Item name="patient_id" label={t('orders.patient')} rules={[{ required: true }]}>
            <Select showSearch placeholder="Выберите пациента"
              options={patients.map((p: any) => ({ value: p.id, label: `${p.full_name} (${p.iin})` }))}
              filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())} />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="service_id" label={t('orders.service')} rules={[{ required: true }]}>
            <Select showSearch placeholder="Выберите услугу"
              options={services.map((s: any) => ({ value: s.id, label: `${s.name_ru} (${s.modality})` }))}
              onChange={(val) => {
                const s = services.find((svc: any) => svc.id === val);
                orderForm.setFieldsValue({ modality: s?.modality || '' });
              }}
              filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())} />
          </Form.Item>
        </Col>
      </Row>
      <Row gutter={16}>
        <Col span={8}>
          <Form.Item name="modality" label={t('orders.modality')}>
            <Input disabled placeholder="Модальность из услуги" />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="body_part" label={t('orders.bodyPart')}>
            <Input placeholder="Головной мозг, грудная клетка..." />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="diagnosis_icd_id" label={t('orders.diagnosis')}>
            <Select showSearch placeholder="МКБ-10" allowClear
              options={icd10.map((c: any) => ({ value: c.id, label: `${c.code} — ${c.name_ru}` }))}
              filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())} />
          </Form.Item>
        </Col>
      </Row>
      <Row gutter={16}>
        <Col span={8}>
          <Form.Item name="priority" label={t('orders.priority')} initialValue="ROUTINE">
            <Select options={[
              { value: 'ROUTINE', label: t('orders.routine') },
              { value: 'URGENT', label: t('orders.urgent') },
            ]} />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="financing_type" label={t('orders.financingType')} initialValue="PAID">
            <Select options={[
              { value: 'PAID', label: t('orders.paid') },
              { value: 'GOMBP', label: 'ГОБМП' },
              { value: 'OSMS', label: 'ОСМС' },
            ]} />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="contrast_agent" label="Контраст" initialValue={false}>
            <Select options={[
              { value: false, label: 'Без контраста' },
              { value: true, label: 'С контрастом' },
            ]} />
          </Form.Item>
        </Col>
      </Row>
      <Form.Item name="clinical_notes" label={t('orders.clinicalNotes')}>
        <Input.TextArea rows={3} placeholder="Жалобы, анамнез, направление..." />
      </Form.Item>
    </>
  );

  const columns = useMemo(() => [
    {
      title: 'AN',
      dataIndex: 'accession_number',
      key: 'an',
      width: 110,
      sorter: (a: any, b: any) => a.accession_number?.localeCompare(b.accession_number),
      render: (v: string) => <code style={{ fontSize: 11, fontWeight: 600 }}>{v}</code>,
    },
    {
      title: t('orders.patient'),
      dataIndex: 'patient_name',
      key: 'patient',
      width: 200,
      ellipsis: true,
      render: (v: string, record: any) => (
        <div>
          <span style={{ fontWeight: 500 }}>{v}</span>
          {record.body_part && (
            <>
              <br />
              <span style={{ fontSize: 11, color: 'var(--c-text2)' }}>{record.body_part}</span>
            </>
          )}
        </div>
      ),
    },
    {
      title: t('orders.modality'),
      dataIndex: 'modality',
      key: 'modality',
      width: 80,
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: t('orders.diagnosis'),
      key: 'diagnosis',
      width: 200,
      ellipsis: true,
      sorter: (a: any, b: any) => (a.diagnosis_icd_name || '').localeCompare(b.diagnosis_icd_name || ''),
      render: (_: any, record: any) => {
        if (record.diagnosis_icd_code && record.diagnosis_icd_name) {
          return `${record.diagnosis_icd_code} — ${record.diagnosis_icd_name}`;
        }
        return record.diagnosis_icd_name || '—';
      },
    },
    {
      title: t('orders.priority'),
      dataIndex: 'priority',
      key: 'priority',
      width: 90,
      sorter: (a: any, b: any) => {
        const order: Record<string, number> = { URGENT: 0, ROUTINE: 1 };
        return (order[a.priority] ?? 99) - (order[b.priority] ?? 99);
      },
      render: (v: string) => {
        const config: Record<string, { color: string; label: string }> = {
          URGENT: { color: 'orange', label: 'Срочный' },
          ROUTINE: { color: 'default', label: 'Плановый' },
        };
        return <Tag color={config[v]?.color}>{config[v]?.label || v}</Tag>;
      },
    },
    {
      title: t('orders.status'),
      dataIndex: 'status',
      key: 'status',
      width: 110,
      sorter: (a: any, b: any) => (a.status || '').localeCompare(b.status || ''),
      render: (v: string) => (
        <span className={`status-badge status-${v.toLowerCase()}`}>
          {(STATUS_MAP[v] || { label: v }).label}
        </span>
      ),
    },
    {
      title: t('orders.createdAt'),
      dataIndex: 'created_at',
      key: 'createdAt',
      width: 140,
      render: (v: string) => v ? dayjs(v).format('DD.MM.YYYY HH:mm') : '—',
      sorter: true,
    },
    {
      title: '',
      key: 'actions',
      width: 140,
      render: (_: any, record: any) => (
        <Space size="small">
          <Button type="text" size="small" icon={<DownloadOutlined />}
            onClick={() => handleDownloadPdf(record.id)} title={t('orders.print')} />
          {['NEW', 'SCHEDULED'].includes(record.status) && (
            <Button type="text" size="small" icon={<EditOutlined />}
              onClick={() => openEdit(record)} title={t('orders.edit')} />
          )}
          {record.status === 'NEW' && (
            <Popconfirm title={t('orders.deleteConfirm')} onConfirm={() => handleDelete(record.id)}>
              <Button type="text" size="small" icon={<DeleteOutlined />} danger title={t('orders.delete')} />
            </Popconfirm>
          )}
          <Button type="text" size="small" icon={<HistoryOutlined />}
            onClick={() => openOrderHistory(record.id)} title={t('orders.history')} />
          {['NEW', 'SCHEDULED'].includes(record.status) && (
            <Popconfirm title={t('orders.cancel') + '?'} onConfirm={() => setCancelModal({ open: true, orderId: record.id })}>
              <Button type="text" size="small" icon={<StopOutlined />} danger />
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ], [t]);

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Title level={4} style={{ margin: 0, color: 'var(--c-text)' }}>{t('nav.orders')}</Title>
        </Col>
        <Col>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            {t('orders.create')}
          </Button>
        </Col>
      </Row>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={[12, 12]}>
          <Col xs={24} sm={12} md={6}>
            <Input placeholder="Поиск по AN, пациенту..." prefix={<SearchOutlined />}
              value={search} onChange={(e) => setSearch(e.target.value)} allowClear />
          </Col>
          <Col xs={12} sm={6} md={4}>
            <Select placeholder="Статус" allowClear style={{ width: '100%' }}
              value={filterStatus} onChange={setFilterStatus}
              options={Object.entries(STATUS_MAP).map(([k, v]) => ({ value: k, label: v.label }))} />
          </Col>
          <Col xs={12} sm={6} md={4}>
            <Select placeholder="Модальность" allowClear style={{ width: '100%' }}
              value={filterModality} onChange={setFilterModality}
              options={MODALITY_OPTIONS.map((m) => ({ value: m, label: m }))} />
          </Col>
          <Col xs={24} sm={12} md={6}>
            <RangePicker style={{ width: '100%' }}
              value={filterDate as any} onChange={(v) => setFilterDate(v as any)} />
          </Col>
        </Row>
      </Card>

      <Spin spinning={loading}>
        <Table dataSource={orders} columns={columns} rowKey="id" size="small"
          scroll={{ x: 'max-content' }}
          pagination={{ pageSize: 20 }}
          rowClassName={(record: any) => record.priority === 'URGENT' ? 'urgent-row' : ''}
          locale={{ emptyText: <div style={{ padding: 60, textAlign: 'center', color: 'var(--c-text2)' }}>
            <FileTextOutlined style={{ fontSize: 40, marginBottom: 12, opacity: 0.3 }} />
            <div style={{ fontSize: 14, fontWeight: 500 }}>{t('orders.noOrders')}</div>
            <div style={{ fontSize: 12, marginTop: 4 }}>{t('orders.noOrdersHint')}</div>
          </div> }} />
      </Spin>

      <Modal title={t('orders.create')} open={modalOpen}
        onCancel={() => { setModalOpen(false); form.resetFields(); }}
        onOk={() => form.submit()} width={700}>
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          {renderOrderFormFields(form)}
        </Form>
      </Modal>

      <Modal title={t('orders.cancel')} open={cancelModal.open}
        onCancel={() => { setCancelModal({ open: false, orderId: '' }); cancelForm.resetFields(); }}
        onOk={cancelForm.submit} okButtonProps={{ danger: true }}>
        <Form form={cancelForm} layout="vertical" onFinish={handleCancel}>
          <Form.Item name="reason" label={t('orders.cancelReason')} rules={[{ required: true }]}>
            <Input.TextArea rows={3} placeholder="Укажите причину отмены..." />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title={t('orders.editTitle')} open={editModal.open}
        onCancel={() => { setEditModal({ open: false, order: null }); editForm.resetFields(); }}
        onOk={() => editForm.submit()} width={700}>
        <Form form={editForm} layout="vertical" onFinish={handleEdit}>
          {renderOrderFormFields(editForm)}
        </Form>
      </Modal>

      <Drawer title={t('orders.history')} open={historyDrawer.open} width={500}
        onClose={() => setHistoryDrawer({ open: false, orderId: '', data: null })}>
        <Spin spinning={historyLoading}>
          {historyDrawer.data ? (
            <List
              dataSource={historyDrawer.data || []}
              renderItem={(entry: any) => (
                <List.Item>
                  <Space direction="vertical" size={0} style={{ width: '100%' }}>
                    <Space>
                      <Tag>{entry.action}</Tag>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        {entry.timestamp ? dayjs(entry.timestamp).format('DD.MM.YYYY HH:mm') : ''}
                      </Text>
                    </Space>
                    <Text style={{ fontSize: 12 }}>{entry.user_name || entry.user_id}</Text>
                  </Space>
                </List.Item>
              )}
            />
          ) : (
            <Text type="secondary">{t('common.noData')}</Text>
          )}
        </Spin>
      </Drawer>
    </div>
  );
};
