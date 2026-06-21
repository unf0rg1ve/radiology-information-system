import React, { useState, useEffect } from 'react';
import {
  Card, Tabs, Table, Input, Select, Spin, Typography, Tag, message,
  Button, Modal, Form, Row, Col,
} from 'antd';
import { BookOutlined, SearchOutlined, PlusOutlined, EditOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { refsApi } from '../api/client';
import { FieldConstructor, FieldDefinition } from '../components/templates/FieldConstructor';

const { Title } = Typography;

export const ReferencesPage: React.FC = () => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('services');
  const [loading, setLoading] = useState(false);
  const [services, setServices] = useState<any[]>([]);
  const [devices, setDevices] = useState<any[]>([]);
  const [icd10, setIcd10] = useState<any[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);
  const [org, setOrg] = useState<any>(null);
  const [search, setSearch] = useState('');
  const [icdSearch, setIcdSearch] = useState('');
  const [templateModality, setTemplateModality] = useState<string>('');
  const [deviceModal, setDeviceModal] = useState<{ open: boolean; device: any }>({ open: false, device: null });
  const [templateModal, setTemplateModal] = useState<{ open: boolean; template: any }>({ open: false, template: null });
  const [templateFields, setTemplateFields] = useState<FieldDefinition[]>([]);
  const [orgModal, setOrgModal] = useState(false);
  const [deviceForm] = Form.useForm();
  const [templateForm] = Form.useForm();
  const [orgForm] = Form.useForm();

  const fetchServices = async () => {
    setLoading(true);
    try {
      const response = await refsApi.services({ search: search || undefined });
      setServices(response.data || []);
    } catch (error) {
      message.error(t('common.error'));
    } finally {
      setLoading(false);
    }
  };

  const fetchDevices = async () => {
    setLoading(true);
    try {
      const response = await refsApi.devices();
      setDevices(response.data || []);
    } catch (error) {
      message.error(t('common.error'));
    } finally {
      setLoading(false);
    }
  };

  const fetchICD10 = async () => {
    if (!icdSearch) { setIcd10([]); return; }
    setLoading(true);
    try {
      const response = await refsApi.icd10({ q: icdSearch });
      setIcd10(response.data || []);
    } catch (error) {
      message.error(t('common.error'));
    } finally {
      setLoading(false);
    }
  };

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (templateModality) params.modality = templateModality;
      const response = await refsApi.protocolTemplates(params);
      setTemplates(response.data || []);
    } catch (error) {
      message.error(t('common.error'));
    } finally {
      setLoading(false);
    }
  };

  const fetchOrg = async () => {
    try {
      const response = await refsApi.organization();
      setOrg(response.data);
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    if (activeTab === 'services') fetchServices();
    if (activeTab === 'devices') fetchDevices();
    if (activeTab === 'icd10') fetchICD10();
    if (activeTab === 'templates') fetchTemplates();
    if (activeTab === 'organization') fetchOrg();
  }, [activeTab, search, icdSearch, templateModality]);

  const handleSaveDevice = async (values: any) => {
    try {
      if (deviceModal.device) {
        await refsApi.updateDevice(deviceModal.device.id, values);
      } else {
        await refsApi.createDevice(values);
      }
      message.success(t('common.success'));
      setDeviceModal({ open: false, device: null });
      deviceForm.resetFields();
      fetchDevices();
    } catch (error: any) {
      message.error(error.response?.data?.detail || t('common.error'));
    }
  };

  const handleSaveTemplate = async (values: any) => {
    try {
      const data = { ...values, fields_schema: templateFields };
      if (templateModal.template) {
        await refsApi.updateTemplate(templateModal.template.id, data);
      } else {
        await refsApi.createTemplate(data);
      }
      message.success(t('common.success'));
      setTemplateModal({ open: false, template: null });
      templateForm.resetFields();
      setTemplateFields([]);
      fetchTemplates();
    } catch (error: any) {
      message.error(error.response?.data?.detail || t('common.error'));
    }
  };

  const handleSaveOrg = async (values: any) => {
    try {
      await refsApi.updateOrganization(values);
      message.success(t('common.success'));
      setOrgModal(false);
      fetchOrg();
    } catch (error: any) {
      message.error(error.response?.data?.detail || t('common.error'));
    }
  };

  const serviceColumns = [
    { title: 'Код ГОБМП', dataIndex: 'code_gombp', key: 'code_gombp', width: 110 },
    { title: 'Наименование', dataIndex: 'name_ru', key: 'name', ellipsis: true },
    { title: 'Модальность', dataIndex: 'modality', key: 'modality', width: 90, render: (v: string) => <Tag>{v}</Tag> },
    { title: 'ГОБМП (₸)', dataIndex: 'tariff_gombp', key: 'tg', width: 100, align: 'right' as const, render: (v: number) => v?.toLocaleString() },
    { title: 'ОСМС (₸)', dataIndex: 'tariff_osms', key: 'to', width: 100, align: 'right' as const, render: (v: number) => v?.toLocaleString() },
    { title: 'Платно (₸)', dataIndex: 'tariff_paid', key: 'tp', width: 100, align: 'right' as const, render: (v: number) => v?.toLocaleString() },
    { title: 'Мин', dataIndex: 'duration_min', key: 'dur', width: 60, align: 'right' as const },
  ];

  const deviceColumns = [
    { title: 'Название', dataIndex: 'name', key: 'name', ellipsis: true },
    { title: 'Модальность', dataIndex: 'modality_type', key: 'modality', width: 90, render: (v: string) => <Tag color="blue">{v}</Tag> },
    { title: 'AET', dataIndex: 'ae_title', key: 'aet', width: 130, render: (v: string) => <code style={{ fontSize: 11 }}>{v}</code> },
    { title: 'Статус', dataIndex: 'status', key: 'status', width: 110, render: (v: string) => (
      <Tag color={v === 'ACTIVE' ? 'green' : v === 'MAINTENANCE' ? 'orange' : 'red'}>{v}</Tag>
    )},
    { title: '', key: 'actions', width: 60, render: (_: any, record: any) => (
      <Button type="text" size="small" icon={<EditOutlined />} onClick={() => {
        deviceForm.setFieldsValue(record);
        setDeviceModal({ open: true, device: record });
      }} />
    )},
  ];

  const templateColumns = [
    { title: 'Наименование', dataIndex: 'name_ru', key: 'name', ellipsis: true },
    { title: 'Модальность', dataIndex: 'modality', key: 'modality', width: 90, render: (v: string) => <Tag color="blue">{v}</Tag> },
    { title: 'Часть тела', dataIndex: 'body_part', key: 'body_part', width: 120 },
    { title: 'Поля', dataIndex: 'fields_schema', key: 'fields', width: 80, render: (v: any[]) => `${v?.length || 0}` },
    { title: '', key: 'actions', width: 60, render: (_: any, record: any) => (
      <Button type="text" size="small" icon={<EditOutlined />} onClick={() => {
        templateForm.setFieldsValue({ ...record, fields_schema: undefined });
        setTemplateFields((record.fields_schema || []) as FieldDefinition[]);
        setTemplateModal({ open: true, template: record });
      }} />
    )},
  ];

  const tabItems = [
    {
      key: 'services',
      label: t('references.tariffs'),
      children: (
        <div>
          <Input placeholder="Поиск..." prefix={<SearchOutlined />} value={search}
            onChange={(e) => setSearch(e.target.value)} style={{ maxWidth: 400, marginBottom: 16 }} allowClear />
          <Spin spinning={loading}>
            <Table dataSource={services} columns={serviceColumns} rowKey="id" size="small" pagination={{ pageSize: 20 }} />
          </Spin>
        </div>
      ),
    },
    {
      key: 'devices',
      label: t('references.devices'),
      children: (
        <div>
          <Button type="primary" icon={<PlusOutlined />} size="small" style={{ marginBottom: 16 }}
            onClick={() => { deviceForm.resetFields(); setDeviceModal({ open: true, device: null }); }}>
            {t('common.create')}
          </Button>
          <Spin spinning={loading}>
            <Table dataSource={devices} columns={deviceColumns} rowKey="id" size="small" />
          </Spin>
        </div>
      ),
    },
    {
      key: 'icd10',
      label: t('references.icd10'),
      children: (
        <div>
          <Input placeholder="Поиск по коду или названию..." prefix={<SearchOutlined />}
            value={icdSearch} onChange={(e) => setIcdSearch(e.target.value)}
            onPressEnter={fetchICD10} style={{ maxWidth: 400, marginBottom: 16 }} allowClear />
          <Spin spinning={loading}>
            <Table dataSource={icd10} columns={[
              { title: 'Код', dataIndex: 'code', key: 'code', width: 80, render: (v: string) => <code style={{ fontWeight: 600 }}>{v}</code> },
              { title: 'Наименование', dataIndex: 'name_ru', key: 'name', ellipsis: true },
            ]} rowKey="id" size="small" pagination={{ pageSize: 20 }} />
          </Spin>
        </div>
      ),
    },
    {
      key: 'templates',
      label: t('references.templates'),
      children: (
        <div>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col>
              <Button type="primary" icon={<PlusOutlined />} size="small"
                onClick={() => {
                  templateForm.resetFields();
                  setTemplateFields([]);
                  setTemplateModal({ open: true, template: null });
                }}>
                {t('common.create')}
              </Button>
            </Col>
            <Col>
              <Select
                placeholder="Все модальности"
                allowClear
                style={{ width: 160 }}
                value={templateModality || undefined}
                onChange={(v) => setTemplateModality(v || '')}
                options={['CT', 'MR', 'CR', 'DX', 'US', 'MG', 'RF'].map(m => ({ value: m, label: m }))}
              />
            </Col>
          </Row>
          <Spin spinning={loading}>
            <Table dataSource={templates} columns={templateColumns} rowKey="id" size="small" />
          </Spin>
        </div>
      ),
    },
    {
      key: 'organization',
      label: t('references.organization'),
      children: (
        <div>
          {org ? (
            <div>
              <Tag color="blue">{org.name_ru}</Tag>
              <Tag>Лицензия: {org.license_number || '—'}</Tag>
              <Tag>Адрес: {org.address || '—'}</Tag>
              <Tag>Тел: {org.phone || '—'}</Tag>
              <Button icon={<EditOutlined />} size="small" style={{ marginLeft: 16 }}
                onClick={() => { orgForm.setFieldsValue(org); setOrgModal(true); }}>
                {t('common.edit')}
              </Button>
            </div>
          ) : (
            <Button onClick={() => setOrgModal(true)}>{t('common.create')}</Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24, color: 'var(--c-text)' }}>
        <BookOutlined style={{ marginRight: 8 }} />{t('nav.references')}
      </Title>
      <Card bodyStyle={{ padding: 16 }}>
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
      </Card>

      <Modal title={deviceModal.device ? t('common.edit') : t('references.devices')}
        open={deviceModal.open}
        onCancel={() => { setDeviceModal({ open: false, device: null }); deviceForm.resetFields(); }}
        onOk={() => deviceForm.submit()} width={600}>
        <Form form={deviceForm} layout="vertical" onFinish={handleSaveDevice}>
          <Row gutter={16}>
            <Col span={12}><Form.Item name="name" label="Название" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="modality_type" label="Модальность" rules={[{ required: true }]}>
              <Select options={['CT','MR','CR','DX','US','MG','RF'].map(m => ({ value: m, label: m }))} />
            </Form.Item></Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}><Form.Item name="ae_title" label="AE Title" rules={[{ required: true }]}><Input maxLength={16} /></Form.Item></Col>
            <Col span={8}><Form.Item name="ip_address" label="IP"><Input /></Form.Item></Col>
            <Col span={8}><Form.Item name="status" label="Статус" initialValue="ACTIVE">
              <Select options={[{ value: 'ACTIVE', label: 'ACTIVE' }, { value: 'MAINTENANCE', label: 'MAINTENANCE' }]} />
            </Form.Item></Col>
          </Row>
        </Form>
      </Modal>

      <Modal title={templateModal.template ? t('common.edit') : t('references.templates')}
        open={templateModal.open}
        onCancel={() => { setTemplateModal({ open: false, template: null }); templateForm.resetFields(); setTemplateFields([]); }}
        onOk={() => templateForm.submit()} width={700}>
        <Form form={templateForm} layout="vertical" onFinish={handleSaveTemplate}>
          <Row gutter={16}>
            <Col span={12}><Form.Item name="name_ru" label="Название" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="modality" label="Модальность" rules={[{ required: true }]}>
              <Select options={['CT','MR','CR','DX','US','MG','RF'].map(m => ({ value: m, label: m }))} />
            </Form.Item></Col>
          </Row>
          <Form.Item name="body_part" label="Часть тела"><Input /></Form.Item>
          <Form.Item label="Поля">
            <FieldConstructor value={templateFields} onChange={setTemplateFields} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title={t('references.organization')} open={orgModal}
        onCancel={() => setOrgModal(false)} onOk={() => orgForm.submit()} width={500}>
        <Form form={orgForm} layout="vertical" onFinish={handleSaveOrg}>
          <Form.Item name="name_ru" label="Наименование" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="license_number" label="Лицензия МЗ РК"><Input /></Form.Item>
          <Form.Item name="address" label="Адрес"><Input /></Form.Item>
          <Form.Item name="phone" label="Телефон"><Input /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
