import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Layout, Button, Avatar, Dropdown, Badge, Typography } from 'antd';
import dayjs from 'dayjs';
import 'dayjs/locale/kk';
import 'dayjs/locale/ru';
import {
  DashboardOutlined,
  TeamOutlined,
  FileTextOutlined,
  CalendarOutlined,
  ExperimentOutlined,
  MedicineBoxOutlined,
  BookOutlined,
  SettingOutlined,
  MoonOutlined,
  SunOutlined,
  LogoutOutlined,
  UserOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  GlobalOutlined,
  BellOutlined,
  AlertOutlined,
  CheckCircleOutlined,
  FileAddOutlined,
  WarningOutlined,
  ExperimentOutlined as LabOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../../stores/authStore';
import { useTheme } from '../../theme/ThemeProvider';
import { notificationsApi } from '../../api/client';
import { useWebSocket } from '../../hooks/useWebSocket';

const { Text } = Typography;

const { Header, Sider, Content } = Layout;

interface AppLayoutProps {
  children: React.ReactNode;
}

const ROLE_MENU_MAP: Record<string, string[]> = {
  REGISTRAR: ['/patients', '/orders', '/schedule'],
  TECHNOLOGIST: ['/worklist'],
  RADIOLOGIST: ['/reports', '/worklist'],
  HEAD: ['/dashboard', '/reports', '/worklist', '/references'],
  REFERRER: ['/patients', '/orders', '/reports'],
  ADMIN: ['/dashboard', '/patients', '/orders', '/schedule', '/worklist', '/reports', '/references', '/admin'],
};

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { logout, user } = useAuthStore();
  const { theme, toggleTheme } = useTheme();
  const { t, i18n } = useTranslation();
  const [citoCount, setCitoCount] = useState(0);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifOpen, setNotifOpen] = useState(false);
  const clearedRef = useRef(false);

  const currentLang = i18n.language;

  const fetchCitoCount = async () => {
    try {
      const res = await notificationsApi.cito();
      setCitoCount((res.data || []).length);
    } catch { /* ignore */ }
  };

  const fetchNotifications = useCallback(async (force = false) => {
    if (clearedRef.current && !force) return;
    clearedRef.current = false;
    try {
      const res = await notificationsApi.list();
      const data = res.data || [];
      setNotifications(data);
      setUnreadCount(data.length);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchCitoCount();
    fetchNotifications();
  }, [fetchNotifications]);

  useWebSocket('cito', (msg) => {
    if (msg.type === 'cito_notification') {
      fetchCitoCount();
      fetchNotifications(true);
    }
  });

  const notifIconMap: Record<string, React.ReactNode> = {
    'CREATE': <FileAddOutlined style={{ color: '#1890ff' }} />,
    'STATUS_UPDATE': <AlertOutlined style={{ color: '#faad14' }} />,
    'ARRIVED': <UserOutlined style={{ color: '#52c41a' }} />,
    'IN_PROGRESS': <ExperimentOutlined style={{ color: '#722ed1' }} />,
    'UNMATCHED_RESOLVED': <LabOutlined style={{ color: '#722ed1' }} />,
    'SIGN': <CheckCircleOutlined style={{ color: '#52c41a' }} />,
    'ISSUE': <FileTextOutlined style={{ color: '#1890ff' }} />,
    'CITO_NOTIFICATION': <AlertOutlined style={{ color: '#ff4d4f' }} />,
    'RETAKE': <WarningOutlined style={{ color: '#faad14' }} />,
  };

  const allMenuItems = [
    { key: '/dashboard', icon: <DashboardOutlined />, label: t('nav.dashboard') },
    { key: '/patients', icon: <TeamOutlined />, label: t('nav.patients') },
    { key: '/orders', icon: <FileTextOutlined />, label: t('nav.orders') },
    { key: '/schedule', icon: <CalendarOutlined />, label: t('nav.schedule') },
    { key: '/worklist', icon: <ExperimentOutlined />, label: t('nav.worklist') },
    { key: '/reports', icon: <MedicineBoxOutlined />, label: t('nav.reports'), badge: citoCount },
    { key: '/references', icon: <BookOutlined />, label: t('nav.references') },
    { key: '/admin', icon: <SettingOutlined />, label: t('nav.admin') },
  ];

  const allowedRoutes = (user?.role && ROLE_MENU_MAP[user.role]) || ROLE_MENU_MAP.ADMIN;
  const menuItems = allMenuItems.filter(item => allowedRoutes.includes(item.key));

  const handleMenuClick = (key: string) => {
    navigate(key);
  };

  const isActive = (key: string) => {
    if (location.pathname === key) return true;
    if (key !== '/' && location.pathname.startsWith(key + '/')) return true;
    return false;
  };

  const toggleLanguage = () => {
    const newLang = currentLang === 'ru' ? 'kz' : 'ru';
    i18n.changeLanguage(newLang);
    localStorage.setItem('ris-lang', newLang);
  };

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: `${user?.last_name || ''} ${user?.first_name || ''}`,
      disabled: true,
    },
    { type: 'divider' as const },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: t('auth.logout'),
      danger: true,
      onClick: logout,
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh', overflowX: 'hidden', maxWidth: '100vw', width: '100%' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        width={220}
        style={{
          background: 'var(--c-sidebar)',
          boxShadow: '2px 0 8px rgba(0,0,0,0.15)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            padding: collapsed ? 0 : '0 16px',
            borderBottom: '1px solid rgba(255,255,255,0.1)',
          }}
        >
          {!collapsed && (
            <div>
              <div style={{ color: '#fff', fontSize: 16, fontWeight: 700, letterSpacing: 0.5 }}>
                RIS MVP
              </div>
              <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: 10, marginTop: 2 }}>
                {t('app.subtitle')}
              </div>
            </div>
          )}
          {collapsed && (
            <div style={{ color: '#fff', fontSize: 18, fontWeight: 700 }}>R</div>
          )}
        </div>

        <div style={{ padding: '8px 0' }}>
          {menuItems.map((item) => (
            <div
              key={item.key}
              onClick={() => handleMenuClick(item.key)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: collapsed ? '12px 0' : '10px 16px',
                margin: '2px 8px',
                borderRadius: 6,
                cursor: 'pointer',
                color: isActive(item.key) ? '#fff' : 'rgba(255,255,255,0.6)',
                background: isActive(item.key) ? 'var(--c-accent)' : 'transparent',
                transition: 'all 0.2s ease',
                justifyContent: collapsed ? 'center' : 'flex-start',
                fontSize: 13,
                fontWeight: location.pathname === item.key ? 600 : 400,
              }}
              onMouseEnter={(e) => {
                if (!isActive(item.key)) {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.08)';
                  e.currentTarget.style.color = '#fff';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive(item.key)) {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = 'rgba(255,255,255,0.6)';
                }
              }}
            >
              <span style={{ fontSize: 16, display: 'flex', alignItems: 'center' }}>
                {item.icon}
              </span>
              {!collapsed && <span>{item.label}</span>}
              {item.badge ? <Badge count={item.badge} size="small" style={{ marginLeft: 6 }} /> : null}
            </div>
          ))}
        </div>
      </Sider>

      <Layout style={{ minWidth: 0 }}>
        <Header
          style={{
            background: 'var(--c-surface)',
            borderBottom: '1px solid var(--c-border)',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            height: 56,
            position: 'sticky',
            top: 0,
            zIndex: 100,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              style={{ color: 'var(--c-text)' }}
            />
            <span style={{ color: 'var(--c-text2)', fontSize: 12 }}>
              {dayjs().locale(currentLang === 'kz' ? 'kk' : 'ru').format('dddd, D MMMM YYYY')}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Dropdown open={notifOpen} menu={{
              items: [
                ...(notifications.length > 0 ? [
                  ...notifications.slice(0, 10).map((n: any) => ({
                    key: n.id,
                    icon: notifIconMap[n.action] || <BellOutlined />,
                    label: (
                      <div style={{ maxWidth: 350 }} onClick={() => { if (n.link) navigate(n.link); }}>
                        <div style={{ fontWeight: 500, fontSize: 13 }}>{n.detail || n.label}</div>
                        <div><Text type="secondary" style={{ fontSize: 10 }}>
                          {n.timestamp ? dayjs(n.timestamp).format('DD.MM.YYYY HH:mm') : ''}
                        </Text></div>
                      </div>
                    ),
                  })),
                  { type: 'divider' as const },
                  {
                    key: 'clear',
                    label: <span style={{ color: '#ff4d4f' }}>Очистить уведомления</span>,
                    onClick: async () => {
                      try { await notificationsApi.clear(); } catch { /* ignore */ }
                      clearedRef.current = true; setNotifications([]); setUnreadCount(0); setNotifOpen(false);
                    },
                  },
                ] : [
                  {
                    key: 'empty',
                    label: <Text type="secondary" style={{ fontSize: 12 }}>Нет новых уведомлений</Text>,
                    disabled: true,
                  },
                ]),
              ],
              style: { maxHeight: 400, overflowY: 'auto' },
            }} trigger={['click']} onOpenChange={(open) => {
              setNotifOpen(open);
              if (open) { fetchNotifications(); setUnreadCount(0); }
            }}>
              <Badge count={unreadCount} size="small">
                <Button
                  type="text"
                  icon={<BellOutlined />}
                  style={{ color: 'var(--c-text)' }}
                />
              </Badge>
            </Dropdown>
            <Button
              type="text"
              icon={<GlobalOutlined />}
              onClick={toggleLanguage}
              style={{ color: 'var(--c-text)', fontSize: 12 }}
            >
              {currentLang === 'ru' ? 'ҚАЗ' : 'РУС'}
            </Button>
            <Button
              type="text"
              icon={theme === 'dark' ? <SunOutlined /> : <MoonOutlined />}
              onClick={toggleTheme}
              style={{ color: 'var(--c-text)' }}
            />
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                <Avatar
                  size="small"
                  style={{
                    background: 'var(--c-accent)',
                    color: '#fff',
                    fontSize: 12,
                    fontWeight: 600,
                  }}
                >
                  {user?.first_name?.[0]}{user?.last_name?.[0]}
                </Avatar>
                <span style={{ color: 'var(--c-text)', fontSize: 13, fontWeight: 500 }}>
                  {user?.last_name} {user?.first_name?.[0]}.
                </span>
              </div>
            </Dropdown>
          </div>
        </Header>

        <Content
          style={{
            margin: 16,
            padding: 20,
            background: 'var(--c-surface)',
            borderRadius: 8,
            border: '1px solid var(--c-border)',
            minHeight: 280,
            overflowY: 'auto',
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};
