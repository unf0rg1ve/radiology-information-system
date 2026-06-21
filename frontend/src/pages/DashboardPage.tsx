import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Table, Badge, Typography, Spin, Select, Button, Space } from 'antd';
import {
  ExperimentOutlined, ClockCircleOutlined, ExclamationCircleOutlined,
  CheckCircleOutlined, MedicineBoxOutlined, DownloadOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { statsApi, ordersApi } from '../api/client';
import { useAuthStore } from '../stores/authStore';

const { Title } = Typography;

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
};

export const DashboardPage: React.FC = () => {
  const { t } = useTranslation();
  const [stats, setStats] = useState<any>(null);
  const [recentOrders, setRecentOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('today');
  const navigate = useNavigate();
  const { user } = useAuthStore();

  const fetchData = async () => {
    setLoading(true);
    try {
      const [statsRes, ordersRes] = await Promise.all([
        statsApi.dashboard(period),
        ordersApi.list({ limit: 10 }),
      ]);
      setStats(statsRes.data);
      setRecentOrders(ordersRes.data || []);
    } catch (error) {
      console.error('Failed to load dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [period]);

  const handleExport = async (format: string) => {
    try {
      const response = await statsApi.export({ format });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `ris-stats.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Export failed:', error);
    }
  };

  const columns = [
    {
      title: 'AN',
      dataIndex: 'accession_number',
      key: 'an',
      width: 120,
      render: (v: string) => <code style={{ fontSize: 11 }}>{v}</code>,
    },
    {
      title: t('orders.patient'),
      dataIndex: 'patient_name',
      key: 'patient',
      render: (v: string, record: any) => (
        <span>
          {v}
          <br />
          <span style={{ fontSize: 11, color: 'var(--c-text2)' }}>{record.modality}</span>
        </span>
      ),
    },
    {
      title: t('orders.service'),
      dataIndex: 'service_name',
      key: 'service',
      ellipsis: true,
    },
    {
      title: t('orders.priority'),
      dataIndex: 'priority',
      key: 'priority',
      width: 100,
      render: (v: string) => {
        const colors: Record<string, string> = { URGENT: 'orange', ROUTINE: 'default' };
        const labels: Record<string, string> = { URGENT: 'Срочный', ROUTINE: 'Плановый' };
        return <Badge status={colors[v] as any} text={labels[v] || v} />;
      },
    },
    {
      title: t('common.filter'),
      dataIndex: 'status',
      key: 'status',
      width: 130,
      render: (v: string) => {
        const status = STATUS_MAP[v] || { label: v, color: 'default' };
        return <span className={`status-badge status-${v.toLowerCase()}`}>{status.label}</span>;
      },
    },
  ];

  if (loading) {
    return <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}><Spin size="large" /></div>;
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <Title level={4} style={{ margin: 0, color: 'var(--c-text)' }}>{t('stats.dashboard')}</Title>
          <span style={{ color: 'var(--c-text2)', fontSize: 12 }}>
            {t('auth.loginSubtitle')}, {user?.first_name} {user?.last_name}
          </span>
        </div>
        <Space>
          <Select value={period} onChange={setPeriod} size="small" style={{ width: 140 }}
            options={[
              { value: 'today', label: t('common.today') },
              { value: 'week', label: t('common.week') },
              { value: 'month', label: t('common.month') },
            ]}
          />
          <Button icon={<DownloadOutlined />} size="small" onClick={() => handleExport('csv')}>{t('stats.exportCsv')}</Button>
          <Button icon={<DownloadOutlined />} size="small" onClick={() => handleExport('xlsx')}>{t('stats.exportXlsx')}</Button>
        </Space>
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card className="card-hover" bodyStyle={{ padding: 16 }}>
            <Statistic title={<span style={{ fontSize: 12 }}>{t('stats.totalStudies')}</span>}
              value={stats?.total_studies || 0}
              prefix={<ExperimentOutlined style={{ color: 'var(--c-accent)' }} />}
              valueStyle={{ color: 'var(--c-text)', fontSize: 28, fontWeight: 700 }} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="card-hover" bodyStyle={{ padding: 16 }}>
            <Statistic title={<span style={{ fontSize: 12 }}>{t('nav.worklist')}</span>}
              value={stats?.to_report || 0}
              prefix={<ClockCircleOutlined style={{ color: 'var(--c-warn)' }} />}
              valueStyle={{ color: 'var(--c-warn)', fontSize: 28, fontWeight: 700 }} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="card-hover" bodyStyle={{ padding: 16 }}>
            <Statistic title={<span style={{ fontSize: 12 }}>{t('stats.avgTat')}</span>}
              value={stats?.avg_tat_hours || 0} suffix="ч"
              prefix={<CheckCircleOutlined style={{ color: 'var(--c-success)' }} />}
              valueStyle={{ color: 'var(--c-success)', fontSize: 28, fontWeight: 700 }} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="card-hover" bodyStyle={{ padding: 16 }}>
            <Statistic title={<span style={{ fontSize: 12 }}>{t('stats.overdue')}</span>}
              value={stats?.overdue_count || 0}
              prefix={<ExclamationCircleOutlined style={{ color: 'var(--c-danger)' }} />}
              valueStyle={{ color: 'var(--c-danger)', fontSize: 28, fontWeight: 700 }} />
          </Card>
        </Col>
      </Row>

      {stats?.by_modality && Object.keys(stats.by_modality).length > 0 && (
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          {Object.entries(stats.by_modality).map(([modality, count]) => (
            <Col key={modality} xs={12} sm={8} md={6} lg={4}>
              <Card bodyStyle={{ padding: '12px 16px', textAlign: 'center' }}>
                <MedicineBoxOutlined style={{ fontSize: 20, color: 'var(--c-accent)', marginBottom: 4 }} />
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--c-text)' }}>{count as number}</div>
                <div style={{ fontSize: 11, color: 'var(--c-text2)' }}>{modality}</div>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {stats?.by_financing && Object.keys(stats.by_financing).length > 0 && (
          <Col xs={24} lg={12}>
            <Card title={t('stats.byFinancing')} bodyStyle={{ padding: 16 }}>
              {Object.entries(stats.by_financing).map(([type, count]) => {
                const labels: Record<string, string> = { GOMBP: 'ГОБМП', OSMS: 'ОСМС', PAID: 'Платно' };
                return (
                  <div key={type} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--c-border)' }}>
                    <span>{labels[type] || type}</span>
                    <span style={{ fontWeight: 600 }}>{count as number}</span>
                  </div>
                );
              })}
            </Card>
          </Col>
        )}
        {stats?.by_doctor && stats.by_doctor.length > 0 && (
          <Col xs={24} lg={12}>
            <Card title={t('stats.byDoctor') || 'По врачам'} bodyStyle={{ padding: 0 }}>
              {stats.by_doctor.map((d: any, i: number) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 16px', borderBottom: '1px solid var(--c-border)' }}>
                  <Space><UserOutlined style={{ color: 'var(--c-text2)' }} /><span>{d.name}</span></Space>
                  <span style={{ fontWeight: 600 }}>{d.count}</span>
                </div>
              ))}
            </Card>
          </Col>
        )}
        {stats?.by_device && stats.by_device.length > 0 && (
          <Col xs={24}>
            <Card title={t('stats.byDevice') || 'По аппаратам'} bodyStyle={{ padding: 0 }}>
              {stats.by_device.map((d: any, i: number) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 16px', borderBottom: '1px solid var(--c-border)' }}>
                  <Space><MedicineBoxOutlined style={{ color: 'var(--c-text2)' }} /><span>{d.name}</span><Badge count={d.modality} style={{ backgroundColor: 'var(--c-accent)' }} /></Space>
                  <span style={{ fontWeight: 600 }}>{d.count}</span>
                </div>
              ))}
            </Card>
          </Col>
        )}
      </Row>

      <Card title={t('nav.orders')}
        extra={<a onClick={() => navigate('/orders')} style={{ fontSize: 12, cursor: 'pointer' }}>{t('common.all')} →</a>}
        bodyStyle={{ padding: 0 }}>
        <Table dataSource={recentOrders} columns={columns} rowKey="id" size="small" pagination={false}
          rowClassName={(record: any) => record.priority === 'URGENT' ? 'urgent-row' : ''}
          onRow={(_record: any) => ({ onClick: () => navigate('/orders'), style: { cursor: 'pointer' } })}
          locale={{ emptyText: <div style={{ padding: 40, textAlign: 'center', color: 'var(--c-text2)' }}>
            <MedicineBoxOutlined style={{ fontSize: 32, marginBottom: 8, opacity: 0.3 }} />
            <div>{t('orders.noOrders')}</div>
            <div style={{ fontSize: 12, marginTop: 4 }}>{t('orders.noOrdersHint')}</div>
          </div> }} />
      </Card>
    </div>
  );
};
