import React, { useState, useEffect } from 'react';
import {
  Card, Tabs, Table, Button, Input, Select, Tag, message,
  Typography, Spin, Form, Modal, Switch, Row, Col, Space, Popconfirm, List,
} from 'antd';
import {
  SettingOutlined, PlusOutlined, KeyOutlined, HistoryOutlined, UserOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { adminApi } from '../api/client';

const { Title, Text } = Typography;

const ROLE_MAP: Record<string, { label: string; color: string }> = {
  REGISTRAR: { label: 'Регистратор', color: 'blue' },
  TECHNOLOGIST: { label: 'Технолог', color: 'green' },
  RADIOLOGIST: { label: 'Радиолог', color: 'purple' },
  HEAD: { label: 'Заведующий', color: 'orange' },
  REFERRER: { label: 'Направитель', color: 'cyan' },
  ADMIN: { label: 'Админ', color: 'red' },
};

export const AdminPage: React.FC = () => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('users');
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState<any[]>([]);
  const [audit, setAudit] = useState<any[]>([]);
  const [userModal, setUserModal] = useState(false);
  const [userForm] = Form.useForm();
  const [resetModal, setResetModal] = useState<{ open: boolean; userId: string }>({ open: false, userId: '' });
  const [resetForm] = Form.useForm();
  const [loginHistory, setLoginHistory] = useState<{ open: boolean; userId: string; data: any[] }>({
    open: false, userId: '', data: [],
  });
  const [historyLoading, setHistoryLoading] = useState(false);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const response = await adminApi.users();
      setUsers(response.data || []);
    } catch (error) {
      message.error(t('common.error'));
    } finally {
      setLoading(false);
    }
  };

  const fetchAudit = async () => {
    setLoading(true);
    try {
      const response = await adminApi.audit({ limit: 200 });
      setAudit(response.data || []);
    } catch (error) {
      message.error(t('common.error'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'users') fetchUsers();
    if (activeTab === 'audit') fetchAudit();
  }, [activeTab]);

  const handleCreateUser = async (values: any) => {
    try {
      await adminApi.createUser(values);
      message.success(t('common.success'));
      setUserModal(false);
      userForm.resetFields();
      fetchUsers();
    } catch (error: any) {
      message.error(error.response?.data?.detail || t('common.error'));
    }
  };

  const handleResetPassword = async () => {
    try {
      const values = await resetForm.validateFields();
      await adminApi.resetPassword(resetModal.userId, values.new_password);
      message.success('Пароль сброшен');
      setResetModal({ open: false, userId: '' });
      resetForm.resetFields();
    } catch (error: any) {
      if (error.response) message.error(error.response?.data?.detail || t('common.error'));
    }
  };

  const fetchLoginHistory = async (userId: string) => {
    setLoginHistory({ open: true, userId, data: [] });
    setHistoryLoading(true);
    try {
      const response = await adminApi.loginHistory(userId);
      setLoginHistory({ open: true, userId, data: response.data || [] });
    } catch (error) {
      message.error(t('common.error'));
    } finally {
      setHistoryLoading(false);
    }
  };

  const userColumns = [
    { title: 'Login', dataIndex: 'login', key: 'login', width: 100, render: (v: string) => <code>{v}</code> },
    { title: t('admin.role'), key: 'name', render: (_: any, r: any) => (
      <Space><UserOutlined style={{ color: 'var(--c-accent)' }} /><span>{r.last_name} {r.first_name}</span></Space>
    )},
    { title: t('admin.role'), dataIndex: 'role', key: 'role', width: 120, render: (v: string) => (
      <Tag color={(ROLE_MAP[v] || { color: 'default' }).color}>{(ROLE_MAP[v] || { label: v }).label}</Tag>
    )},
    { title: 'Email', dataIndex: 'email', key: 'email', ellipsis: true },
    { title: '', key: 'actions', width: 160, render: (_: any, record: any) => (
      <Space size="small">
        <Popconfirm title="Сбросить пароль?" onConfirm={() => setResetModal({ open: true, userId: record.id })}>
          <Button type="text" size="small" icon={<KeyOutlined />} />
        </Popconfirm>
        <Button type="text" size="small" icon={<HistoryOutlined />}
          onClick={() => fetchLoginHistory(record.id)} />
      </Space>
    )},
  ];

  const auditColumns = [
    { title: 'Тип', dataIndex: 'entity_type', key: 'type', width: 100, render: (v: string) => <Tag>{v}</Tag> },
    { title: 'Действие', dataIndex: 'action', key: 'action', width: 100, render: (v: string) => {
      const colors: Record<string, string> = { CREATE: 'green', UPDATE: 'blue', LOGIN: 'cyan', SIGN: 'orange', ISSUE: 'purple', CANCEL: 'red' };
      return <Tag color={colors[v] || 'default'}>{v}</Tag>;
    }},
    { title: 'Пользователь', dataIndex: 'user_id', key: 'user', width: 200, render: (v: string) => <code>{v}</code> },
    { title: 'Время', dataIndex: 'timestamp', key: 'time', width: 160, render: (v: string) => v ? new Date(v).toLocaleString('ru-RU') : '-' },
    { title: 'IP', dataIndex: 'ip_address', key: 'ip', width: 120 },
  ];

  const tabItems = [
    {
      key: 'users',
      label: <span>{t('admin.users')} <Badge count={users.length} /></span>,
      children: (
        <div>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setUserModal(true)} style={{ marginBottom: 16 }}>
            {t('admin.createUser')}
          </Button>
          <Spin spinning={loading}>
            <Table dataSource={users} columns={userColumns} rowKey="id" size="small" pagination={{ pageSize: 20 }} />
          </Spin>
        </div>
      ),
    },
    {
      key: 'audit',
      label: t('admin.auditLog'),
      children: (
        <Spin spinning={loading}>
          <Table dataSource={audit} columns={auditColumns} rowKey="id" size="small" pagination={{ pageSize: 50 }} />
        </Spin>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24, color: 'var(--c-text)' }}>
        <SettingOutlined style={{ marginRight: 8 }} />{t('nav.admin')}
      </Title>
      <Card bodyStyle={{ padding: 16 }}>
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
      </Card>

      <Modal title={t('admin.createUser')} open={userModal}
        onCancel={() => { setUserModal(false); userForm.resetFields(); }}
        onOk={() => userForm.submit()} width={600}>
        <Form form={userForm} layout="vertical" onFinish={handleCreateUser}>
          <Row gutter={16}>
            <Col span={12}><Form.Item name="login" label={t('auth.username')} rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="password" label={t('auth.password')} rules={[{ required: true, min: 8 }]}><Input.Password /></Form.Item></Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}><Form.Item name="last_name" label={t('patients.lastName')} rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={8}><Form.Item name="first_name" label={t('patients.firstName')} rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={8}><Form.Item name="middle_name" label={t('patients.middleName')}><Input /></Form.Item></Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}><Form.Item name="role" label={t('admin.role')} rules={[{ required: true }]}>
              <Select options={Object.entries(ROLE_MAP).map(([k, v]) => ({ value: k, label: v.label }))} />
            </Form.Item></Col>
            <Col span={12}><Form.Item name="email" label="Email"><Input /></Form.Item></Col>
          </Row>
          <Form.Item name="is_active" valuePropName="checked" initialValue={true}>
            <Switch checkedChildren="Активен" unCheckedChildren="Заблокирован" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="Сброс пароля" open={resetModal.open}
        onCancel={() => { setResetModal({ open: false, userId: '' }); resetForm.resetFields(); }}
        onOk={resetForm.submit}>
        <Form form={resetForm} layout="vertical" onFinish={handleResetPassword}>
          <Form.Item name="new_password" label={t('auth.password')} rules={[{ required: true, min: 8 }]}>
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="Журнал входов" open={loginHistory.open} width={500}
        onCancel={() => setLoginHistory({ open: false, userId: '', data: [] })} footer={null}>
        <Spin spinning={historyLoading}>
          {loginHistory.data.length > 0 ? (
            <List dataSource={loginHistory.data} renderItem={(item: any) => (
              <List.Item>
                <Space direction="vertical" size={0}>
                  <Text>{item.timestamp ? new Date(item.timestamp).toLocaleString('ru-RU') : '—'}</Text>
                  <Text type="secondary">IP: {item.ip_address || '—'}</Text>
                </Space>
              </List.Item>
            )} />
          ) : (
            <Text type="secondary">{t('common.noData')}</Text>
          )}
        </Spin>
      </Modal>
    </div>
  );
};

const Badge = ({ count, ...props }: any) => (
  <span style={{ background: 'var(--c-accent)', color: '#fff', borderRadius: 10, padding: '0 6px', fontSize: 11, fontWeight: 600, marginLeft: 4 }} {...props}>
    {count}
  </span>
);
