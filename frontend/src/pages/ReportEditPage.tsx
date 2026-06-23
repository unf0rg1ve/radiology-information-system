import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  Alert, Button, Checkbox, Descriptions, Divider, Form, Input, InputNumber, message,
  Select, Space, Spin, Tag, Tooltip, Typography,
} from 'antd';
import {
  ArrowLeftOutlined, CheckCircleOutlined, EyeOutlined, FileDoneOutlined,
  SaveOutlined, SendOutlined, FullscreenOutlined, FullscreenExitOutlined,
} from '@ant-design/icons';
import { ordersApi, refsApi, reportsApi } from '../api/client';
import { useAuthStore } from '../stores/authStore';
import { DicomViewer } from '../components/dicom/DicomViewer';

const { Title, Text } = Typography;
const { TextArea } = Input;

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  DRAFT: { label: 'Черновик', color: 'default' },
  SIGNED: { label: 'Подписано', color: 'success' },
  ISSUED: { label: 'Выдано', color: 'blue' },
};

const emptyReportPayload = {
  structured_fields: {},
  description_text: '',
  conclusion_text: '',
  critical_finding: false,
  diagnosis_icd_codes: [],
};

export const ReportEditPage: React.FC = () => {
  const { reportId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const descriptionRef = useRef<any>(null);

  const [report, setReport] = useState<any>(null);
  const [orderInfo, setOrderInfo] = useState<any>(null);
  const [templates, setTemplates] = useState<any[]>([]);
  const [icd10, setIcd10] = useState<any[]>([]);
  const [orderOptions, setOrderOptions] = useState<any[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [signing, setSigning] = useState(false);
  const [issuing, setIssuing] = useState(false);
  const [viewerVisible, setViewerVisible] = useState(true);
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'ADMIN';

  const searchRef = useRef('');

  const currentOrderId = Form.useWatch('order_id', form);
  const readonly = !!report && report.status !== 'DRAFT';
  const currentTemplate = useMemo(
    () => templates.find((tpl: any) => tpl.id === selectedTemplateId),
    [templates, selectedTemplateId],
  );

  const loadTemplatesForOrder = async (order: any, preferredTemplateId?: string | null) => {
    const params: any = {};
    if (order?.service_id) params.service_id = order.service_id;
    if (!order?.service_id && order?.modality) params.modality = order.modality;

    const res = await refsApi.protocolTemplates(params);
    let nextTemplates = res.data || [];

    if (nextTemplates.length === 0 && order?.modality) {
      const fallback = await refsApi.protocolTemplates({ modality: order.modality });
      nextTemplates = fallback.data || [];
    }

    setTemplates(nextTemplates);
    const nextTemplateId = preferredTemplateId || nextTemplates[0]?.id || null;
    setSelectedTemplateId(nextTemplateId);
    form.setFieldValue('protocol_template_id', nextTemplateId);

    if (!reportId && nextTemplateId) {
      applyTemplate(nextTemplates.find((tpl: any) => tpl.id === nextTemplateId), false);
    }
  };

  const loadOrder = async (orderId: string, preferredTemplateId?: string | null) => {
    const res = await ordersApi.get(orderId);
    const order = res.data || null;
    setOrderInfo(order);
    if (order) {
      setOrderOptions([{
        value: order.id,
        label: `${order.accession_number} — ${order.patient_name || '—'} (${order.service_name || order.modality})`,
      }]);
    }
    await loadTemplatesForOrder(order, preferredTemplateId);
  };

  const loadReport = async (id: string) => {
    const res = await reportsApi.get(id);
    const data = res.data;
    setReport(data);
    form.setFieldsValue({
      order_id: data.order_id,
      protocol_template_id: data.protocol_template_id,
      structured_fields: data.structured_fields || {},
      description_text: data.description_text || '',
      conclusion_text: data.conclusion_text || '',
      critical_finding: !!data.critical_finding,
      diagnosis_icd_codes: data.diagnosis_icd_codes || [],
    });
    await loadOrder(data.order_id, data.protocol_template_id);
  };

  const loadInitial = async () => {
    setLoading(true);
    try {
      const icdRes = await refsApi.icd10({ limit: 100 });
      setIcd10(icdRes.data || []);

      if (reportId) {
        await loadReport(reportId);
        return;
      }

      form.setFieldsValue(emptyReportPayload);
      const orderId = searchParams.get('order_id');
      if (orderId) {
        form.setFieldValue('order_id', orderId);
        await loadOrder(orderId);
      } else {
        const [allTemplates, recentOrders] = await Promise.all([
          refsApi.protocolTemplates(),
          ordersApi.list({ limit: 30 }),
        ]);
        setTemplates(allTemplates.data || []);
        setOrderOptions((recentOrders.data || []).map((order: any) => ({
          value: order.id,
          label: `${order.accession_number} — ${order.patient_name || '—'} (${order.service_name || order.modality})`,
        })));
      }
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Не удалось открыть редактор');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInitial();
  }, [reportId, isAdmin]);

  const reportPayload = () => {
    const values = form.getFieldsValue(true);
    return {
      order_id: values.order_id,
      protocol_template_id: values.protocol_template_id || null,
      structured_fields: values.structured_fields || {},
      description_text: values.description_text || '',
      conclusion_text: values.conclusion_text || '',
      critical_finding: !!values.critical_finding,
      diagnosis_icd_codes: values.diagnosis_icd_codes || [],
    };
  };

  const saveDraft = async (silent = false) => {
    if (readonly) return report;
    const values = await form.validateFields();
    const payload = {
      ...reportPayload(),
      order_id: values.order_id,
    };

    setSaving(true);
    try {
      let res;
      if (report?.id) {
        res = await reportsApi.update(report.id, payload);
      } else {
        res = await reportsApi.create(payload);
        navigate(`/reports/${res.data.id}/edit`, { replace: true });
      }
      setReport(res.data);
      if (!silent) message.success('Черновик сохранён');
      return res.data;
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Не удалось сохранить черновик');
      throw error;
    } finally {
      setSaving(false);
    }
  };

  const signReport = async () => {
    if (readonly) return;
    setSigning(true);
    try {
      const draft = await saveDraft(true);
      const res = await reportsApi.sign(draft.id);
      setReport(res.data);
      form.setFieldsValue({
        description_text: res.data.description_text || '',
        conclusion_text: res.data.conclusion_text || '',
      });
      message.success('Заключение подписано');
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Не удалось подписать заключение');
    } finally {
      setSigning(false);
    }
  };

  const issueReport = async () => {
    if (!report?.id || report.status !== 'SIGNED') return;
    setIssuing(true);
    try {
      const res = await reportsApi.issue(report.id);
      setReport(res.data);
      message.success('Заключение выдано');
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Не удалось выдать заключение');
    } finally {
      setIssuing(false);
    }
  };

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        saveDraft();
      }
      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        event.preventDefault();
        signReport();
      }
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'i') {
        event.preventDefault();
        descriptionRef.current?.focus?.();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [report, readonly]);

  const handleOrderSearch = useCallback(async (value: string) => {
    searchRef.current = value;
    try {
      const params: any = { limit: 30 };
      if (value.length >= 2) params.search = value;
      const res = await ordersApi.list(params);
      if (searchRef.current !== value) return;
      setOrderOptions((res.data || []).map((order: any) => ({
        value: order.id,
        label: `${order.accession_number} — ${order.patient_name || '—'} (${order.service_name || order.modality})`,
      })));
    } catch {
      if (searchRef.current !== value) return;
      setOrderOptions([]);
    }
  }, []);

  const loadRecentOrders = useCallback(async () => {
    try {
      const res = await ordersApi.list({ limit: 30 });
      setOrderOptions((res.data || []).map((order: any) => ({
        value: order.id,
        label: `${order.accession_number} — ${order.patient_name || '—'} (${order.service_name || order.modality})`,
      })));
    } catch {
      setOrderOptions([]);
    }
  }, []);

  const applyTemplate = (template: any, overwrite = true) => {
    if (!template || readonly) return;
    const current = form.getFieldsValue(true);
    const structuredFields: Record<string, any> = overwrite ? {} : (current.structured_fields || {});

    (template.fields_schema || []).forEach((field: any) => {
      if (structuredFields[field.field_key] === undefined) {
        structuredFields[field.field_key] = field.default ?? undefined;
      }
    });

    form.setFieldsValue({
      protocol_template_id: template.id,
      structured_fields: structuredFields,
      description_text: overwrite || !current.description_text
        ? template.description_template || current.description_text || ''
        : current.description_text,
      conclusion_text: overwrite || !current.conclusion_text
        ? template.conclusion_template || current.conclusion_text || ''
        : current.conclusion_text,
    });
  };

  const handleTemplateChange = (templateId: string | undefined) => {
    setSelectedTemplateId(templateId || null);
    const template = templates.find((tpl: any) => tpl.id === templateId);
    applyTemplate(template, false);
  };

  const insertNormalTemplate = () => {
    if (!currentTemplate || readonly) return;
    applyTemplate(currentTemplate, true);
    message.success('Шаблон применён');
  };

  const renderDynamicFields = (fieldsSchema: any[]) => {
    if (!fieldsSchema || fieldsSchema.length === 0) {
      return <Text type="secondary">У выбранного шаблона нет структурированных полей</Text>;
    }

    return fieldsSchema.map((field: any) => {
      const namePath = ['structured_fields', field.field_key];
      const label = field.label_ru + (field.unit ? ` (${field.unit})` : '');
      const commonProps = { disabled: readonly };

      switch (field.type) {
        case 'textarea':
          return (
            <Form.Item key={field.field_key} name={namePath} label={label}>
              <TextArea rows={3} placeholder={field.label_ru} {...commonProps} />
            </Form.Item>
          );
        case 'number':
          return (
            <Form.Item key={field.field_key} name={namePath} label={label}>
              <InputNumber style={{ width: '100%' }} placeholder={field.label_ru} {...commonProps} />
            </Form.Item>
          );
        case 'select':
        case 'radio':
          return (
            <Form.Item key={field.field_key} name={namePath} label={label}>
              <Select
                placeholder={field.label_ru}
                allowClear
                options={(field.options || []).map((o: any) => ({ value: o, label: o }))}
                disabled={readonly}
              />
            </Form.Item>
          );
        case 'checkbox':
          return (
            <Form.Item key={field.field_key} name={namePath} valuePropName="checked">
              <Checkbox disabled={readonly}>{field.label_ru}</Checkbox>
            </Form.Item>
          );
        case 'text':
        default:
          return (
            <Form.Item key={field.field_key} name={namePath} label={label}>
              <Input placeholder={field.label_ru} {...commonProps} />
            </Form.Item>
          );
      }
    });
  };

  if (loading) {
    return (
      <div style={{ minHeight: 420, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spin tip="Открытие редактора..." />
      </div>
    );
  }

  return (
    <div>
      <Form form={form} layout="vertical">
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 16,
          marginBottom: 16,
        }}>
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/reports')}>
              Назад
            </Button>
            <div>
              <Title level={4} style={{ margin: 0, color: 'var(--c-text)' }}>
                {report ? `Заключение v${report.version}` : 'Новое заключение'}
              </Title>
              <Space size="small">
                <Text type="secondary">{orderInfo?.accession_number || 'Направление не выбрано'}</Text>
                {report && <Tag color={STATUS_MAP[report.status]?.color}>{STATUS_MAP[report.status]?.label || report.status}</Tag>}
              </Space>
            </div>
          </Space>
          <Space wrap>
            <Tooltip title={viewerVisible ? 'Скрыть снимок (только заключение)' : 'Показать снимок рядом с заключением (сплит-скрин)'}>
              <Button
                icon={viewerVisible ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
                disabled={!currentOrderId}
                onClick={() => setViewerVisible(!viewerVisible)}
              >
                {viewerVisible ? 'Скрыть снимок' : 'Снимок рядом'}
              </Button>
            </Tooltip>
            <Tooltip title="Открыть снимок в отдельной вкладке (для второго монитора)">
              <Button
                icon={<EyeOutlined />}
                disabled={!currentOrderId}
                onClick={() => window.open(`/viewer/${currentOrderId}`, '_blank')}
              >
                Отдельная вкладка
              </Button>
            </Tooltip>
            {!isAdmin && (
              <>
                <Button
                  icon={<SaveOutlined />}
                  onClick={() => saveDraft()}
                  loading={saving}
                  disabled={readonly}
                >
                  Сохранить
                </Button>
                <Button
                  type="primary"
                  icon={<CheckCircleOutlined />}
                  onClick={signReport}
                  loading={signing}
                  disabled={readonly}
                >
                  Подписать
                </Button>
                {report?.status === 'SIGNED' && (
                  <Button icon={<SendOutlined />} onClick={issueReport} loading={issuing}>
                    Выдать
                  </Button>
                )}
              </>
            )}
          </Space>
        </div>

        {readonly && (
          <Alert
            message={isAdmin ? 'Режим просмотра' : 'Документ подписан'}
            description={
              isAdmin
                ? 'Администратор может просматривать заключение без возможности правки, подписи или выдачи.'
                : 'Поля заключения доступны только для чтения. Для изменения создайте новую версию из списка заключений.'
            }
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
          />
        )}

        <div className={viewerVisible ? "report-editor-grid report-editor-grid-with-viewer" : "report-editor-grid"}>
          {viewerVisible && currentOrderId && (
            <section className="report-editor-panel report-editor-viewer-panel">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <Title level={5} style={{ margin: 0 }}>Снимок</Title>
                <Button size="small" icon={<EyeOutlined />} onClick={() => window.open(`/viewer/${currentOrderId}`, '_blank')}>
                  Развернуть
                </Button>
              </div>
              <DicomViewer orderId={currentOrderId} height={520} />
            </section>
          )}
          <section className="report-editor-panel">
            <Title level={5} style={{ marginTop: 0 }}>Направление</Title>
            {orderInfo ? (
              <Descriptions column={1} size="small">
                <Descriptions.Item label="Пациент">{orderInfo.patient_name || '—'}</Descriptions.Item>
                <Descriptions.Item label="AN">{orderInfo.accession_number || '—'}</Descriptions.Item>
                <Descriptions.Item label="Услуга">{orderInfo.service_name || '—'}</Descriptions.Item>
                <Descriptions.Item label="Модальность">{orderInfo.modality || '—'}</Descriptions.Item>
                <Descriptions.Item label="Область">{orderInfo.body_part || '—'}</Descriptions.Item>
                <Descriptions.Item label="Приоритет">{orderInfo.priority || '—'}</Descriptions.Item>
                <Descriptions.Item label="Финансирование">{orderInfo.financing_type || '—'}</Descriptions.Item>
                <Descriptions.Item label="Клиника">{orderInfo.clinical_notes || '—'}</Descriptions.Item>
              </Descriptions>
            ) : (
              <Text type="secondary">Выберите направление для начала описания</Text>
            )}
            <Divider />
            <Form.Item name="order_id" label="Направление" rules={[{ required: true, message: 'Выберите направление' }]}>
              <Select
                showSearch
                disabled={!!report || readonly}
                placeholder="AN, ИИН или ФИО пациента"
                filterOption={false}
                onSearch={handleOrderSearch}
                onFocus={() => { if (orderOptions.length === 0) loadRecentOrders(); }}
                options={orderOptions}
                onChange={(orderId) => loadOrder(orderId)}
              />
            </Form.Item>
            <Form.Item name="protocol_template_id" label="Шаблон протокола">
              <Select
                placeholder="Выберите шаблон"
                allowClear
                disabled={readonly}
                options={templates.map((tpl: any) => ({ value: tpl.id, label: tpl.name_ru }))}
                onChange={handleTemplateChange}
              />
            </Form.Item>
            <Button
              block
              icon={<FileDoneOutlined />}
              disabled={!currentTemplate || readonly}
              onClick={insertNormalTemplate}
            >
              Вставить норму
            </Button>
            {report?.content_hash && (
              <>
                <Divider />
                <Text type="secondary">SHA-256</Text>
                <code style={{ display: 'block', marginTop: 6, wordBreak: 'break-all', fontSize: 10 }}>
                  {report.content_hash}
                </code>
              </>
            )}
          </section>

          <section className="report-editor-panel">
            <Form.Item name="description_text" label="Описание исследования">
              <TextArea
                ref={descriptionRef}
                rows={10}
                placeholder="Подробное описание исследования..."
                disabled={readonly}
                style={{ fontFamily: 'var(--font-main)', fontSize: 13 }}
              />
            </Form.Item>
            <Form.Item name="conclusion_text" label="Заключение" rules={[{ required: true, message: 'Заполните заключение' }]}>
              <TextArea
                rows={5}
                placeholder="Краткое диагностическое заключение..."
                disabled={readonly}
                style={{ fontFamily: 'var(--font-main)', fontSize: 13 }}
              />
            </Form.Item>
          </section>

          <section className="report-editor-panel">
            <Title level={5} style={{ marginTop: 0 }}>Структура и диагноз</Title>
            {currentTemplate && (
              <>
                <Text strong>{currentTemplate.name_ru}</Text>
                <Divider style={{ margin: '12px 0' }} />
              </>
            )}
            {renderDynamicFields(currentTemplate?.fields_schema || [])}
            <Divider />
            <Form.Item name="diagnosis_icd_codes" label="Диагнозы МКБ-10">
              <Select
                mode="tags"
                placeholder="Выберите или введите коды"
                disabled={readonly}
                options={icd10.map((c: any) => ({ value: c.code, label: `${c.code} — ${c.name_ru}` }))}
                filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
              />
            </Form.Item>
            <Form.Item name="critical_finding" valuePropName="checked">
              <Checkbox disabled={readonly}>Критическая находка</Checkbox>
            </Form.Item>
          </section>
        </div>
      </Form>
    </div>
  );
};
