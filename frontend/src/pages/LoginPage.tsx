import React, { useState } from 'react';
import { Card, Form, Input, Button, message, Typography, Space, Alert } from 'antd';
import { MedicineBoxOutlined, LoginOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { authApi } from '../api/client';

const ROLE_DEFAULT_ROUTE: Record<string, string> = {
  REGISTRAR: '/patients',
  TECHNOLOGIST: '/worklist',
  RADIOLOGIST: '/worklist',
  HEAD: '/reports',
  REFERRER: '/orders',
  ADMIN: '/dashboard',
};

const { Title, Text } = Typography;

export const LoginPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const { login } = useAuthStore();
  const { t, i18n } = useTranslation();

  const onFinish = async (values: { login: string; password: string }) => {
    setLoading(true);
    setError('');
    try {
      const response = await authApi.login(values.login, values.password);
      const { access_token, user } = response.data;
      login(access_token, user);
      message.success(t('auth.login') + ' выполнен');
      navigate(ROLE_DEFAULT_ROUTE[user?.role] || '/');
    } catch (err: any) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail;
      if (status === 401) {
        setError(detail || t('auth.loginError'));
      } else if (status === 403) {
        setError(t('auth.loginBlocked'));
      } else if (!err.response) {
        setError(t('auth.networkError'));
      } else {
        setError(detail || t('common.error'));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
    }}>
      <Card style={{ width: 420, borderRadius: 12, boxShadow: '0 20px 60px rgba(0,0,0,0.3)', border: 'none' }}
        bodyStyle={{ padding: '40px 32px' }}>
        <Space direction="vertical" align="center" style={{ width: '100%', marginBottom: 32 }}>
          <div style={{
            width: 64, height: 64, borderRadius: 16,
            background: 'linear-gradient(135deg, #2563eb, #1d4ed8)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 32, color: '#fff',
          }}>
            <MedicineBoxOutlined />
          </div>
          <Title level={3} style={{ margin: 0, color: 'var(--c-text)' }}>RIS MVP</Title>
          <Text type="secondary" style={{ fontSize: 13 }}>{t('app.subtitle')}</Text>
          <Text type="secondary" style={{ fontSize: 11 }}>Республика Казахстан</Text>
        </Space>

        {error && (
          <Alert message={error} type="error" showIcon closable
            onClose={() => setError('')} style={{ marginBottom: 16 }} />
        )}

        <Form name="login" onFinish={onFinish} layout="vertical" size="large">
          <Form.Item name="login" rules={[{ required: true, message: t('auth.username') + ' обязателен' }]}>
            <Input placeholder={t('auth.username')} prefix={<span style={{ color: 'var(--c-text2)' }}>@</span>}
              style={{ background: 'var(--c-surface2)' }} />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: t('auth.password') + ' обязателен' }]}>
            <Input.Password placeholder={t('auth.password')} style={{ background: 'var(--c-surface2)' }} />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0, marginTop: 24 }}>
            <Button type="primary" htmlType="submit" loading={loading} block icon={<LoginOutlined />}
              style={{ height: 44, fontSize: 15, fontWeight: 600 }}>
              {t('auth.loginButton')}
            </Button>
          </Form.Item>
        </Form>

        <div style={{ marginTop: 24, textAlign: 'center' }}>
          <Text type="secondary" style={{ fontSize: 11 }}>Демо: admin / admin123</Text>
        </div>
        <div style={{ marginTop: 16, textAlign: 'center' }}>
          <Space size="small">
            <Button size="small" type={i18n.language === 'ru' ? 'primary' : 'text'}
              onClick={() => { i18n.changeLanguage('ru'); localStorage.setItem('ris-lang', 'ru'); }}>
              Рус
            </Button>
            <Button size="small" type={i18n.language === 'kz' ? 'primary' : 'text'}
              onClick={() => { i18n.changeLanguage('kz'); localStorage.setItem('ris-lang', 'kz'); }}>
              Қаз
            </Button>
          </Space>
        </div>
      </Card>
    </div>
  );
};
