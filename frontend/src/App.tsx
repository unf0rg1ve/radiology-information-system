import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './stores/authStore';
import { AppLayout } from './components/layout/AppLayout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { PatientsPage } from './pages/PatientsPage';
import { OrdersPage } from './pages/OrdersPage';
import { SchedulePage } from './pages/SchedulePage';
import { WorklistPage } from './pages/WorklistPage';
import { ReportsPage } from './pages/ReportsPage';
import { ReferencesPage } from './pages/ReferencesPage';
import { AdminPage } from './pages/AdminPage';
import { DicomViewerPage } from './pages/DicomViewerPage';
import { ReportEditPage } from './pages/ReportEditPage';

const ROLE_DEFAULT_ROUTE: Record<string, string> = {
  REGISTRAR: '/patients',
  TECHNOLOGIST: '/worklist',
  RADIOLOGIST: '/worklist',
  HEAD: '/reports',
  REFERRER: '/orders',
  ADMIN: '/dashboard',
};

function App() {
  const { isAuthenticated, user } = useAuthStore();

  if (!isAuthenticated) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<Navigate to={user?.role ? (ROLE_DEFAULT_ROUTE[user.role] || '/dashboard') : '/dashboard'} replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/patients" element={<PatientsPage />} />
        <Route path="/orders" element={<OrdersPage />} />
        <Route path="/schedule" element={<SchedulePage />} />
        <Route path="/worklist" element={<WorklistPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/reports/new" element={<ReportEditPage />} />
        <Route path="/reports/:reportId/edit" element={<ReportEditPage />} />
        <Route path="/viewer/:orderId" element={<DicomViewerPage />} />
        <Route path="/references" element={<ReferencesPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppLayout>
  );
}

export default App;
