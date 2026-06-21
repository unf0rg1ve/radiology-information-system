import React, { useState, useEffect } from 'react';
import {
  Table, Button, Select, Tag, message, Typography, Spin, Space, Modal, Form, Input, Tabs, Badge, Popconfirm, Tooltip,
} from 'antd';
import { useNavigate } from 'react-router-dom';
import {
  CheckCircleOutlined, CloseCircleOutlined, ExperimentOutlined, ReloadOutlined, WarningOutlined, LinkOutlined, FileAddOutlined,
  EyeOutlined, CameraOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { worklistApi, refsApi, ordersApi } from '../api/client';
import { useWebSocket } from '../hooks/useWebSocket';
import { useAuthStore } from '../stores/authStore';

const { Title, Text } = Typography;

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  NEW: { label: 'Новое', color: 'default' },
  SCHEDULED: { label: 'Запланировано', color: 'green' },
  ARRIVED: { label: 'Прибыл', color: 'cyan' },
  IN_PROGRESS: { label: 'В работе', color: 'orange' },
  ACQUIRED: { label: 'Снимки получены', color: 'purple' },
  TO_REPORT: { label: 'К описанию', color: 'volcano' },
  REPORTING: { label: 'Описывается', color: 'gold' },
  SIGNED: { label: 'Подписано', color: 'success' },
  ISSUED: { label: 'Выдано', color: 'blue' },
  CANCELLED: { label: 'Отменено', color: 'default' },
};

function shortName(fullName: string | undefined): string {
  if (!fullName) return '—';
  const parts = fullName.trim().split(/\s+/);
  if (parts.length === 0) return '—';
  if (parts.length === 1) return parts[0];
  if (parts.length === 2) return `${parts[0]} ${parts[1][0]}.`;
  return `${parts[0]} ${parts[1][0]}.${parts[2][0]}.`;
}

export const WorklistPage: React.FC = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { user } = useAuthStore();
  const canMarkArrived = ['REGISTRAR', 'TECHNOLOGIST', 'ADMIN'].includes(user?.role || '');
  const canRunStudy = ['TECHNOLOGIST', 'ADMIN'].includes(user?.role || '');
  const canResolveUnmatched = ['TECHNOLOGIST', 'RADIOLOGIST', 'ADMIN'].includes(user?.role || '');
  const canWriteReport = ['RADIOLOGIST', 'HEAD'].includes(user?.role || '');
  const canRetake = ['TECHNOLOGIST', 'ADMIN'].includes(user?.role || '');
  const roleStatusOptions: Record<string, string[]> = {
    REGISTRAR: ['SCHEDULED', 'ARRIVED'],
    TECHNOLOGIST: ['SCHEDULED', 'ARRIVED', 'IN_PROGRESS', 'ACQUIRED', 'TO_REPORT'],
    RADIOLOGIST: ['TO_REPORT', 'REPORTING'],
    HEAD: ['TO_REPORT', 'REPORTING', 'SIGNED'],
    REFERRER: ['SIGNED', 'ISSUED'],
    ADMIN: Object.keys(STATUS_MAP),
  };
  const statusOptions = (roleStatusOptions[user?.role || ''] || Object.keys(STATUS_MAP))
    .map((key) => ({ value: key, label: STATUS_MAP[key]?.label || key }));
  const [orders, setOrders] = useState<any[]>([]);
  const [devices, setDevices] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState<string | undefined>(undefined);
  const [selectedStatus, setSelectedStatus] = useState<string | undefined>(undefined);
  const [qcModal, setQcModal] = useState<{ open: boolean; orderId: string; status: string }>({
    open: false, orderId: '', status: 'ACCEPTED',
  });
  const [qcComment, setQcComment] = useState('');
  const [retakeModal, setRetakeModal] = useState<{ open: boolean; orderId: string }>({ open: false, orderId: '' });
  const [retakeComment, setRetakeComment] = useState('');
  const [unmatched, setUnmatched] = useState<any[]>([]);
  const [unmatchedLoading, setUnmatchedLoading] = useState(false);
  const [resolveModal, setResolveModal] = useState<{ open: boolean; unmatchedId: string; studyUid: string }>({
    open: false, unmatchedId: '', studyUid: '',
  });
  const [orderOptions, setOrderOptions] = useState<any[]>([]);
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [resolveLoading, setResolveLoading] = useState(false);

  const fetchWorklist = async () => {
    setLoading(true);
    try {
      const response = await worklistApi.list({ device_id: selectedDevice, status: selectedStatus });
      setOrders(response.data || []);
    } catch (error) {
      message.error(t('common.error'));
    } finally {
      setLoading(false);
    }
  };

  const fetchDevices = async () => {
    try {
      const response = await refsApi.devices();
      setDevices((response.data || []).filter((d: any) => d.status === 'ACTIVE'));
    } catch (error) {
      console.error(error);
    }
  };

  const fetchUnmatched = async () => {
    if (!canResolveUnmatched) {
      setUnmatched([]);
      return;
    }
    setUnmatchedLoading(true);
    try {
      const response = await worklistApi.unmatched();
      setUnmatched(response.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setUnmatchedLoading(false);
    }
  };

  useEffect(() => {
    fetchDevices();
    fetchWorklist();
    fetchUnmatched();
  }, [selectedDevice, selectedStatus]);

  useWebSocket('worklist', (msg) => {
    if (['status_changed', 'study_acquired', 'unmatched_study', 'unmatched_resolved', 'retake'].includes(msg.type)) {
      fetchWorklist();
      fetchUnmatched();
    }
  });

  const handleAction = async (orderId: string, action: string) => {
    try {
      if (action === 'arrived') {
        await worklistApi.markArrived(orderId);
      } else if (action === 'in-progress') {
        await worklistApi.markInProgress(orderId);
      } else if (action === 'qc') {
        setQcModal({ open: true, orderId, status: 'ACCEPTED' });
        return;
      }
      message.success(t('common.success'));
      fetchWorklist();
    } catch (error: any) {
      message.error(error.response?.data?.detail || t('common.error'));
    }
  };

  const handleQC = async () => {
    try {
      await worklistApi.qc(qcModal.orderId, { status: qcModal.status, comment: qcComment });
      message.success('QC выполнен');
      setQcModal({ open: false, orderId: '', status: 'ACCEPTED' });
      setQcComment('');
      fetchWorklist();
    } catch (error: any) {
      message.error(error.response?.data?.detail || t('common.error'));
    }
  };

  const handleRetake = async () => {
    try {
      const res = await worklistApi.retake(retakeModal.orderId, {
        comment: retakeComment || 'Снимок забракован лаборантом',
      });
      message.success(res.data?.message || 'Снимок забракован, требуется пересъёмка');
      setRetakeModal({ open: false, orderId: '' });
      setRetakeComment('');
      fetchWorklist();
    } catch (error: any) {
      message.error(error.response?.data?.detail || t('common.error'));
    }
  };

  const loadUnmatchedOrders = async () => {
    try {
      const res = await ordersApi.list({ without_study: true, limit: 100 });
      const attachableStatuses = ['NEW', 'SCHEDULED', 'ARRIVED', 'IN_PROGRESS', 'ACQUIRED'];
      const filtered = (res.data || []).filter((o: any) => attachableStatuses.includes(o.status));
      setOrderOptions(filtered.map((o: any) => ({
        value: o.id,
        label: `${o.accession_number} — ${o.patient_name || '—'} (${o.status})`,
      })));
    } catch { setOrderOptions([]); }
  };

  const handleOrderSearch = async (value: string) => {
    if (value.length < 2) { setOrderOptions([]); return; }
    try {
      const res = await ordersApi.list({ search: value, limit: 50, without_study: true });
      const attachableStatuses = ['NEW', 'SCHEDULED', 'ARRIVED', 'IN_PROGRESS', 'ACQUIRED'];
      const filtered = (res.data || []).filter((o: any) => attachableStatuses.includes(o.status));
      setOrderOptions(filtered.map((o: any) => ({
        value: o.id,
        label: `${o.accession_number} — ${o.patient_name || '—'} (${o.status})`,
      })));
    } catch { setOrderOptions([]); }
  };

  const handleResolve = async () => {
    if (!selectedOrderId) { message.warning('Выберите направление'); return; }
    setResolveLoading(true);
    try {
      await worklistApi.resolveUnmatched(resolveModal.unmatchedId, selectedOrderId);
      message.success('Студия привязана к направлению');
      setResolveModal({ open: false, unmatchedId: '', studyUid: '' });
      setSelectedOrderId(null);
      setOrderOptions([]);
      fetchUnmatched();
      fetchWorklist();
    } catch (error: any) {
      message.error(error.response?.data?.detail || t('common.error'));
    } finally {
      setResolveLoading(false);
    }
  };

  const columns = [
    {
      title: 'AN',
      dataIndex: 'accession_number',
      key: 'an',
      width: 120,
      render: (v: string) => <code style={{ fontSize: 10, fontWeight: 600 }}>{v}</code>,
    },
    {
      title: t('orders.patient'),
      key: 'patient',
      width: 150,
      render: (_: any, record: any) => (
        <div>
          <div style={{ fontWeight: 500 }}>{shortName(record.patient_name)}</div>
          <div style={{ fontSize: 10, color: 'var(--c-text2)' }}>
            {record.modality} · {record.service_name?.substring(0, 30) || '—'}
          </div>
        </div>
      ),
    },
    {
      title: t('orders.priority'),
      dataIndex: 'priority',
      key: 'priority',
      width: 90,
      render: (v: string) => {
        if (v === 'URGENT') return <Tag color="orange">{t('orders.urgent')}</Tag>;
        return <Tag>{t('orders.routine')}</Tag>;
      },
    },
    {
      title: t('common.filter'),
      dataIndex: 'status',
      key: 'status',
      width: 130,
      render: (v: string) => (
        <span className={`status-badge status-${v.toLowerCase()}`}>{(STATUS_MAP[v] || { label: v }).label}</span>
      ),
    },
    {
      title: t('common.edit'),
      key: 'actions',
      width: 200,
      render: (_: any, record: any) => {
        const actions = [];
        if (record.status === 'SCHEDULED' && canMarkArrived) {
          actions.push(<Button key="arr" size="small" type="primary" onClick={() => handleAction(record.id, 'arrived')}>{t('worklist.arrived')}</Button>);
        }
        if (record.status === 'ARRIVED' && canRunStudy) {
          actions.push(<Button key="prog" size="small" type="primary" onClick={() => handleAction(record.id, 'in-progress')}>{t('worklist.inProgress')}</Button>);
        }
        if (record.status === 'ACQUIRED' && canRunStudy) {
          actions.push(<Button key="qc" size="small" type="primary" icon={<CheckCircleOutlined />} onClick={() => handleAction(record.id, 'qc')}>QC</Button>);
        }
        if (['ACQUIRED', 'TO_REPORT'].includes(record.status) && canRetake) {
          actions.push(
            <Popconfirm
              key="retake"
              title="Переснять снимок?"
              description="Снимок будет забракован. Сделайте новый — он привяжется к этому же направлению."
              onConfirm={() => setRetakeModal({ open: true, orderId: record.id })}
              okText="Переснять"
              cancelText="Отмена"
              okButtonProps={{ danger: true }}
            >
              <Button size="small" icon={<CloseCircleOutlined />} danger>Переснять</Button>
            </Popconfirm>
          );
        }
        if (record.status === 'TO_REPORT' && canWriteReport) {
          actions.push(<Button key="report" size="small" type="primary" icon={<FileAddOutlined />} onClick={() => navigate(`/reports/new?order_id=${record.id}`)}>Написать заключение</Button>);
        }
        if (['ACQUIRED', 'TO_REPORT', 'REPORTING', 'SIGNED', 'ISSUED'].includes(record.status)) {
          actions.push(
            <Tooltip key="viewer" title="Просмотр снимков">
              <Button size="small" icon={<EyeOutlined />} onClick={() => navigate(`/viewer/${record.id}`)} />
            </Tooltip>
          );
        }
        return <Space size="small" wrap>{actions}</Space>;
      },
    },
  ];

  const unmatchedColumns = [
    {
      title: 'Study UID',
      dataIndex: 'study_instance_uid',
      key: 'uid',
      ellipsis: true,
      render: (v: string) => <code style={{ fontSize: 10 }}>{v}</code>,
    },
    {
      title: 'AN',
      dataIndex: 'accession_number',
      key: 'an',
      render: (v: string) => v || <Tag color="orange">Нет AN</Tag>,
    },
    {
      title: t('orders.patient'),
      dataIndex: 'patient_name_dicom',
      key: 'patient',
      render: (_: string, record: any) => record.patient_name_dicom || record.patient_id_dicom || '—',
    },
    {
      title: 'Patient ID',
      dataIndex: 'patient_id_dicom',
      key: 'patientId',
      render: (v: string) => v || '—',
    },
    {
      title: t('orders.modality'),
      dataIndex: 'modality',
      key: 'modality',
      width: 80,
      render: (v: string) => v || '—',
    },
    {
      title: 'Дата',
      dataIndex: 'study_date',
      key: 'studyDate',
      width: 100,
      render: (v: string) => v || '—',
    },
    {
      title: t('common.edit'),
      key: 'actions',
      width: 120,
      render: (_: any, record: any) => (
        <Button size="small" icon={<LinkOutlined />} onClick={() => {
          setSelectedOrderId(null);
          setOrderOptions([]);
          setResolveModal({ open: true, unmatchedId: record.id, studyUid: record.study_instance_uid });
        }}>
          {t('worklist.match') || 'Связать'}
        </Button>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0, color: 'var(--c-text)' }}>
          <ExperimentOutlined style={{ marginRight: 8 }} />{t('nav.worklist')}
        </Title>
        <Space>
          <Select placeholder={t('schedule.device')} allowClear style={{ width: 200 }}
            value={selectedDevice} onChange={setSelectedDevice}
            options={devices.map((d: any) => ({ value: d.id, label: d.name }))} />
          <Select placeholder={t('common.filter')} allowClear style={{ width: 150 }}
            value={selectedStatus} onChange={setSelectedStatus}
            options={statusOptions} />
          <Button icon={<ReloadOutlined />} onClick={() => { fetchWorklist(); fetchUnmatched(); }} loading={loading} />
        </Space>
      </div>

      <Tabs items={[
        {
          key: 'worklist',
          label: <span>{t('nav.worklist')} <Badge count={orders.length} style={{ backgroundColor: 'var(--c-accent)' }} /></span>,
          children: (
            <Spin spinning={loading}>
              <Table dataSource={orders} columns={columns} rowKey="id" size="small"
                pagination={{ pageSize: 20, showSizeChanger: false }}
                scroll={{ x: 800 }}
                rowClassName={(record: any) => record.priority === 'URGENT' ? 'urgent-row' : ''}
                locale={{
                  emptyText: (
                    <div style={{ padding: 60, textAlign: 'center', color: 'var(--c-text2)' }}>
                      <ExperimentOutlined style={{ fontSize: 40, marginBottom: 12, opacity: 0.3 }} />
                      <div style={{ fontSize: 14, fontWeight: 500 }}>Очередь пуста</div>
                      <div style={{ fontSize: 12, marginTop: 4 }}>
                        {canRunStudy
                          ? 'Записи появятся после того, как регистратор запишет пациентов на ваш аппарат'
                          : 'Выберите статус или аппарат для просмотра'}
                      </div>
                    </div>
                  ),
                }}
              />
            </Spin>
          ),
        },
        ...(canResolveUnmatched ? [{
          key: 'unmatched',
          label: <span><WarningOutlined /> Несопоставленные <Badge count={unmatched.length} style={{ backgroundColor: 'var(--c-warn)' }} /></span>,
          children: (
            <Spin spinning={unmatchedLoading}>
              <Table dataSource={unmatched} columns={unmatchedColumns} rowKey="id" size="small" pagination={false}
                scroll={{ x: 700 }}
                locale={{ emptyText: 'Нет несопоставленных студий' }} />
            </Spin>
          ),
        }] : []),
      ]} />

      <Modal title={t('worklist.qc')} open={qcModal.open}
        onCancel={() => setQcModal({ open: false, orderId: '', status: 'ACCEPTED' })}
        onOk={handleQC}>
        <Form layout="vertical">
          <Form.Item label={t('worklist.qc')}>
            <Select value={qcModal.status} onChange={(v) => setQcModal({ ...qcModal, status: v })}
              options={[
                { value: 'ACCEPTED', label: t('worklist.accept') },
                { value: 'RETAKE', label: t('worklist.retake') },
              ]} />
          </Form.Item>
          <Form.Item label={t('worklist.qcComment')}>
            <Input.TextArea value={qcComment} onChange={(e) => setQcComment(e.target.value)}
              rows={3} placeholder={t('worklist.qcComment')} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Пересъёмка снимка"
        open={retakeModal.open}
        onCancel={() => { setRetakeModal({ open: false, orderId: '' }); setRetakeComment(''); }}
        onOk={handleRetake}
        okText="Забраковать и переснять"
        okButtonProps={{ danger: true }}
      >
        <div style={{ marginBottom: 12, padding: 12, background: 'var(--c-surface2)', borderRadius: 6 }}>
          <CameraOutlined style={{ marginRight: 8, color: 'var(--c-warn)' }} />
          <Text strong>Снимок будет забракован.</Text>
          <br />
          <Text type="secondary" style={{ fontSize: 12 }}>
            Направление <strong>не нужно создавать заново</strong> — новый снимок автоматически привяжется
            к этому же направлению. Статус вернётся в «В работе», и вы сможете сделать новый снимок.
          </Text>
        </div>
        <Form layout="vertical">
          <Form.Item label="Причина пересъёмки (необязательно)">
            <Input.TextArea
              value={retakeComment}
              onChange={(e) => setRetakeComment(e.target.value)}
              rows={3}
              placeholder="Например: пациент дёрнулся, муть, недостаточная экспозиция..."
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="Связать студию с направлением" open={resolveModal.open}
        onCancel={() => { setResolveModal({ open: false, unmatchedId: '', studyUid: '' }); setSelectedOrderId(null); setOrderOptions([]); }}
        onOk={handleResolve} confirmLoading={resolveLoading} okButtonProps={{ disabled: !selectedOrderId }}
        afterOpenChange={(open) => { if (open) loadUnmatchedOrders(); }}>
        <div style={{ marginBottom: 12 }}>
          <Typography.Text type="secondary">Study UID: </Typography.Text>
          <code style={{ fontSize: 11 }}>{resolveModal.studyUid}</code>
        </div>
        <Form layout="vertical">
          <Form.Item label="Направление (пациенты без снимков)">
            <Select
              showSearch
              value={selectedOrderId}
              onSearch={handleOrderSearch}
              onChange={setSelectedOrderId}
              filterOption={false}
              placeholder="Выберите пациента или введите AN..."
              options={orderOptions}
              notFoundContent="Нет пациентов без привязки"
              style={{ width: '100%' }}
            />
          </Form.Item>
        </Form>
      </Modal>

    </div>
  );
};
