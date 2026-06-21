import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ConfigProvider, theme as antdTheme } from 'antd'
import ru_RU from 'antd/locale/ru_RU'
import { ThemeProvider, useTheme } from './theme/ThemeProvider'
import App from './App'
import './i18n'
import './index.css'

const ThemedApp: React.FC = () => {
  const { theme } = useTheme()
  return (
    <ConfigProvider
      locale={ru_RU}
      theme={{
        algorithm: theme === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        token: {
          colorPrimary: theme === 'dark' ? '#58a6ff' : '#2563eb',
          colorBgContainer: theme === 'dark' ? '#161b22' : '#ffffff',
          colorBgElevated: theme === 'dark' ? '#21262d' : '#ffffff',
          colorBgLayout: theme === 'dark' ? '#0d1117' : '#f0f2f5',
          colorBorder: theme === 'dark' ? '#30363d' : '#e2e8f0',
          colorText: theme === 'dark' ? '#e6edf3' : '#0f172a',
          colorTextSecondary: theme === 'dark' ? '#8b949e' : '#64748b',
          colorSuccess: theme === 'dark' ? '#3fb950' : '#16a34a',
          colorWarning: theme === 'dark' ? '#d29922' : '#d97706',
          colorError: theme === 'dark' ? '#f85149' : '#dc2626',
          fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
          fontSize: 13,
          borderRadius: 6,
        },
        components: {
          Table: {
            headerBg: theme === 'dark' ? '#21262d' : '#f8f9fa',
            headerColor: theme === 'dark' ? '#e6edf3' : '#0f172a',
            rowHoverBg: theme === 'dark' ? '#1c2128' : '#f1f5f9',
          },
          Menu: {
            darkItemBg: 'transparent',
          },
          Modal: {
            contentBg: theme === 'dark' ? '#161b22' : '#ffffff',
            headerBg: theme === 'dark' ? '#161b22' : '#ffffff',
          },
          Card: {
            colorBgContainer: theme === 'dark' ? '#161b22' : '#ffffff',
          },
          Select: {
            optionSelectedBg: theme === 'dark' ? '#1c2128' : '#eff6ff',
          },
          Drawer: {
            colorBgElevated: theme === 'dark' ? '#161b22' : '#ffffff',
          },
        },
      }}
    >
      <App />
    </ConfigProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <ThemedApp />
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
