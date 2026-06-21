import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Badge, Button, Card, Col, DatePicker, Drawer, Input, List, message, Row, Select, Space, Spin, Table, Tabs, Tag, Tooltip, Typography,
} from 'antd';
import dayjs from 'dayjs';
import {
  CameraOutlined, CheckCircleOutlined, EditOutlined, FileTextOutlined, HistoryOutlined, InfoCircleOutlined,
  MedicineBoxOutlined, PlusOutlined, ReloadOutlined, SearchOutlined, SendOutlined, WarningOutlined, EyeOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { ordersApi, reportsApi } from '../api/client';
import { useAuthStore } from '../stores/authStore';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  DRAFT: { label: 'Черновик', color: 'default' },
  SIGNED: { label: 'Подписано', color: 'success' },
  ISSUED: { label: 'Выдано', color: 'blue' },
};

const MODALITY_OPTIONS = ['CT', 'MR', 'US', 'MG', 'CR', 'XA', 'OT'];

function shortName(fullName: string | undefined): string {
  if (!fullName) return '—';
  const parts = fullName.trim().split(/\s+/);
  if (parts.length === 0) return '—';
  if (parts.length === 1) return parts[0];
  if (parts.length === 2) return `${parts[0]} ${parts[1][0]}.`;
  return `${parts[0]} ${parts[1][0]}.${parts[2][0]}.`;
}

export const ReportsPage: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [reports, setReports] = useState<any[]>([]);
  const [ordersToReport, setOrdersToReport] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [versionDrawer, setVersionDrawer] = useState<{ open: boolean; versions: any[] }>({ open: false, versions: [] });
  const [versionLoading, setVersionLoading] = useState(false);
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'ADMIN';
  const isRadiologist = ['RADIOLOGIST', 'HEAD', 'ADMIN'].includes(user?.role || '');
  const [activeTab, setActiveTab] = useState('to-report');
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState<string | undefined>(undefined);
  const [filterModality, setFilterModality] = useState<string | undefined>(undefined);
  const [filterDate, setFilterDate] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);

  const fetchReports = async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (debouncedSearch) params.search = debouncedSearch;
      if (filterStatus) params.status = filterStatus;
      if (filterModality) params.modality = filterModality;
      if (filterDate?.[0]) params.date_from = filterDate[0].format('YYYY-MM-DD');
      if (filterDate?.[1]) params.date_to = filterDate[1].format('YYYY-MM-DD');
      const response = await reportsApi.list(params);
      setReports(response.data || []);
    } catch {
      message.error(t('common.error'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [debouncedSearch, filterStatus, filterModality, filterDate]);

  const fetchOrdersToReport = async () => {
    try {
      const response = await ordersApi.list({ status: 'TO_REPORT', limit: 50 });
      setOrdersToReport(response.data || []);
    } catch {
      // silent
    }
  };

  useEffect(() => {
    if (isRadiologist) fetchOrdersToReport();
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    const orderId = searchParams.get('order_id');
    if (orderId) {
      setSearchParams({}, { replace: true });
      if (!isAdmin) {
        navigate(`/reports/new?order_id=${orderId}`, { replace: true });
      }
    }
  }, [searchParams, navigate, setSearchParams, isAdmin]);

  const openVersionHistory = async (orderId: string) => {
    setVersionDrawer({ open: true, versions: [] });
    setVersionLoading(true);
    try {
      const response = await reportsApi.list({ order_id: orderId });
      const sorted = (response.data || []).sort((a: any, b: any) =>
        parseInt(a.version) - parseInt(b.version)
      );
      setVersionDrawer({ open: true, versions: sorted });
    } catch {
      message.error(t('common.error'));
    } finally {
      setVersionLoading(false);
    }
  };

  const handleSign = async (reportId: string) => {
    try {
      await reportsApi.sign(reportId);
      message.success(t('reports.signed'));
      fetchReports();
    } catch (error: any) {
      message.error(error.response?.data?.detail || t('common.error'));
    }
  };

  const handleIssue = async (reportId: string) => {
    try {
      await reportsApi.issue(reportId);
      message.success(t('reports.issued'));
      fetchReports();
    } catch (error: any) {
      message.error(error.response?.data?.detail || t('common.error'));
    }
  };

  const handleNewVersion = async (reportId: string) => {
    try {
      const res = await reportsApi.newVersion(reportId);
      message.success('Новая версия создана');
      navigate(`/reports/${res.data.id}/edit`);
    } catch (error: any) {
      message.error(error.response?.data?.detail || t('common.error'));
    }
  };

  const handleSecondOpinion = async (reportId: string) => {
    try {
      const original = reports.find(r => r.id === reportId);
      const res = await reportsApi.secondOpinion(reportId, {
        order_id: original?.order_id,
        protocol_template_id: original?.protocol_template_id,
        structured_fields: original?.structured_fields,
        description_text: original?.description_text,
        conclusion_text: original?.conclusion_text,
        critical_finding: original?.critical_finding,
        diagnosis_icd_codes: original?.diagnosis_icd_codes,
      });
      message.success(t('reports.secondOpinion') + ' создано');
      navigate(`/reports/${res.data.id}/edit`);
    } catch (error: any) {
      message.error(error.response?.data?.detail || t('common.error'));
    }
  };

  const handleDownloadPdf = (reportId: string) => {
    const token = useAuthStore.getState().token;
    window.open(`/api/reports/${reportId}/pdf?token=${token}`, '_blank');
  };

  const toReportColumns = [
    {
      title: 'Пациент',
      key: 'patient',
      render: (_: any, record: any) => (
        <div>
          <span style={{ fontWeight: 600 }}>{shortName(record.patient_name)}</span>
          <div style={{ fontSize: 10, color: 'var(--c-text2)' }}>{record.patient_iin || ''}</div>
        </div>
      ),
    },
    {
      title: 'Исследование',
      key: 'study',
      render: (_: any, record: any) => (
        <div>
          <Tag color="blue" style={{ marginRight: 4 }}>{record.modality}</Tag>
          <span style={{ fontSize: 12 }}>{record.service_name || '—'}</span>
        </div>
      ),
    },
    {
      title: 'Приоритет',
      dataIndex: 'priority',
      key: 'priority',
      width: 100,
      render: (v: string) => {
        if (v === 'URGENT') return <Tag color="orange">Срочный</Tag>;
        return <Tag>{v === 'ROUTINE' ? 'Плановый' : v}</Tag>;
      },
    },
    {
      title: 'Готовность',
      key: 'ready_at',
      width: 130,
      render: (_: any, record: any) => {
        const dt = record.updated_at || record.created_at;
        return dt ? (
          <div style={{ fontSize: 11 }}>
            <div>{dayjs(dt).format('DD.MM.YYYY HH:mm')}</div>
          </div>
        ) : '—';
      },
    },
    {
      title: 'Действия',
      key: 'actions',
      width: 200,
      render: (_: any, record: any) => (
        <Space size="small">
          <Button
            type="primary" size="small" icon={<EditOutlined />}
            onClick={() => navigate(`/reports/new?order_id=${record.id}`)}
          >
            Описать
          </Button>
          <Tooltip title="Просмотр снимков">
            <Button size="small" icon={<EyeOutlined />} onClick={() => navigate(`/viewer/${record.id}`)} />
          </Tooltip>
        </Space>
      ),
    },
  ];

  const columns = [
    {
      title: t('orders.patient'),
      key: 'patient',
      render: (_: any, record: any) => (
        <div>
          <span style={{ fontWeight: 600 }}>{shortName(record.patient_name)}</span>
          <br />
          <code>AN: {record.accession_number || '—'}</code>
        </div>
      ),
    },
    {
      title: t('admin.radiologist'),
      dataIndex: 'radiologist_name',
      key: 'doctor',
      width: 170,
    },
    {
      title: 'Дата заключения',
      key: 'date',
      width: 140,
      render: (_: any, record: any) => {
        const dt = record.signed_at || record.created_at;
        return dt ? dayjs(dt).format('DD.MM.YYYY HH:mm') : '—';
      },
      sorter: (a: any, b: any) => {
        const da = a.signed_at || a.created_at || '';
        const db = b.signed_at || b.created_at || '';
        return da.localeCompare(db);
      },
    },
    {
      title: t('reports.conclusion'),
      key: 'text',
      ellipsis: true,
      render: (_: any, record: any) => (
        <div>
          <Text ellipsis style={{ maxWidth: 280 }}>
            {record.conclusion_text || '—'}
          </Text>
          {record.critical_finding && (
            <Tag color="red" icon={<WarningOutlined />} style={{ marginLeft: 8, fontSize: 10 }}>
              {t('reports.criticalFinding')}
            </Tag>
          )}
        </div>
      ),
    },
    {
      title: t('common.filter'),
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (v: string) => (
        <Tag color={(STATUS_MAP[v] || { color: 'default' }).color}>
          {(STATUS_MAP[v] || { label: v }).label}
        </Tag>
      ),
    },
    {
      title: t('common.edit'),
      key: 'actions',
      width: 300,
      render: (_: any, record: any) => (
        <Space size="small" wrap>
          {isAdmin ? (
            <Button
              size="small"
              icon={<EyeOutlined />}
              onClick={() => navigate(`/reports/${record.id}/edit`)}
            >
              Просмотр
            </Button>
          ) : (
            <>
              <Button
                size="small"
                icon={<EditOutlined />}
                onClick={() => navigate(`/reports/${record.id}/edit`)}
              >
                {record.status === 'DRAFT' ? t('common.edit') : 'Открыть'}
              </Button>
              {record.status === 'DRAFT' && (
                <Button size="small" type="primary" icon={<CheckCircleOutlined />} onClick={() => handleSign(record.id)}>
                  {t('reports.sign')}
                </Button>
              )}
              {(record.status === 'SIGNED' || record.status === 'ISSUED') && user?.id === record.radiologist_id && (
                <Button size="small" icon={<EditOutlined />} onClick={() => handleNewVersion(record.id)}>
                  Новая версия
                </Button>
              )}
              {record.status === 'SIGNED' && (
                <Button size="small" type="primary" icon={<SendOutlined />} onClick={() => handleIssue(record.id)}>
                  {t('reports.issue')}
                </Button>
              )}
              {record.status === 'ISSUED' && (
                <Button size="small" icon={<InfoCircleOutlined />} onClick={() => handleSecondOpinion(record.id)}>
                  {t('reports.secondOpinion')}
                </Button>
              )}
            </>
          )}
          <Tooltip title="История версий">
            <Button size="small" icon={<HistoryOutlined />}
              onClick={() => openVersionHistory(record.order_id)} />
          </Tooltip>
          <Tooltip title="Скачать PDF">
            <Button size="small" icon={<FileTextOutlined />} onClick={() => handleDownloadPdf(record.id)} />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Title level={4} style={{ margin: 0, color: 'var(--c-text)' }}>
            <MedicineBoxOutlined style={{ marginRight: 8 }} />
            {t('reports.title')}
          </Title>
        </Col>
        <Col>
          <Space>
            {!isAdmin && (
              <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/reports/new')}>
                {t('reports.create')}
              </Button>
            )}
            <Button icon={<ReloadOutlined />} onClick={fetchReports} loading={loading}>
              {t('common.refresh')}
            </Button>
          </Space>
        </Col>
      </Row>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={[12, 12]}>
          <Col xs={24} sm={12} md={6}>
            <Input placeholder="Поиск по пациенту, ИИН..." prefix={<SearchOutlined />}
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

      <Tabs
        activeKey={activeTab}
        onChange={(key) => { setActiveTab(key); if (key === 'to-report') fetchOrdersToReport(); }}
        items={[
          ...(isRadiologist ? [{
            key: 'to-report',
            label: (
              <span>
                <CameraOutlined /> Снимки к описанию
                <Badge count={ordersToReport.length} style={{ backgroundColor: 'var(--c-warn)', marginLeft: 6 }} />
              </span>
            ),
            children: (
              <Spin spinning={loading}>
                <Table
                  dataSource={ordersToReport}
                  columns={toReportColumns}
                  rowKey="id"
                  size="small"
                  pagination={{ pageSize: 15, showSizeChanger: false }}
                  scroll={{ x: 'max-content' }}
                  rowClassName={(record: any) => record.priority === 'URGENT' ? 'urgent-row' : ''}
                  locale={{
                    emptyText: (
                      <div style={{ padding: 60, textAlign: 'center', color: 'var(--c-text2)' }}>
                        <CameraOutlined style={{ fontSize: 40, marginBottom: 12, opacity: 0.3 }} />
                        <div style={{ fontSize: 14, fontWeight: 500 }}>Нет снимков, ожидающих описания</div>
                        <div style={{ fontSize: 12, marginTop: 4 }}>
                          Снимки появятся здесь автоматически после того, как лаборант примет их (QC ACCEPTED)
                        </div>
                      </div>
                    ),
                  }}
                />
              </Spin>
            ),
          }] : []),
          {
            key: 'reports',
            label: (
              <span>
                <FileTextOutlined /> Заключения
                <Badge count={reports.length} style={{ backgroundColor: 'var(--c-accent)', marginLeft: 6 }} />
              </span>
            ),
            children: (
              <Spin spinning={loading}>
                <Table
                  dataSource={reports}
                  columns={columns}
                  rowKey="id"
                  size="small"
                  scroll={{ x: 'max-content' }}
                  pagination={{ pageSize: 20 }}
                />
              </Spin>
            ),
          },
        ]}
      />

      <Drawer title="История версий заключения" open={versionDrawer.open} width={500}
        onClose={() => setVersionDrawer({ open: false, versions: [] })}>
        <Spin spinning={versionLoading}>
          <List
            dataSource={versionDrawer.versions}
            renderItem={(item: any) => (
              <List.Item>
                <Space direction="vertical" size={0} style={{ width: '100%' }}>
                  <Space>
                    <Tag color={item.status === 'DRAFT' ? 'default' : item.status === 'SIGNED' ? 'success' : 'blue'}>
                      {item.status === 'DRAFT' ? 'Черновик' : item.status === 'SIGNED' ? 'Подписано' : 'Выдано'}
                    </Tag>
                    <code style={{ fontSize: 12 }}>v{item.version}</code>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {item.created_at ? dayjs(item.created_at).format('DD.MM.YYYY HH:mm') : ''}
                    </Text>
                  </Space>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {item.radiologist_name || '—'}
                  </Text>
                  {item.signed_at && (
                    <Text style={{ fontSize: 11 }}>
                      Подписано: {dayjs(item.signed_at).format('DD.MM.YYYY HH:mm')}
                    </Text>
                  )}
                  {item.issued_at && (
                    <Text style={{ fontSize: 11 }}>
                      Выдано: {dayjs(item.issued_at).format('DD.MM.YYYY HH:mm')}
                    </Text>
                  )}
                  {item.critical_finding && (
                    <Tag color="red" style={{ fontSize: 10 }}>Критическая находка</Tag>
                  )}
                </Space>
              </List.Item>
            )}
          />
        </Spin>
      </Drawer>
    </div>
  );
};
