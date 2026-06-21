import axios from 'axios';
import { useAuthStore } from '../stores/authStore';
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

export const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token;
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  },
  (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
      window.location.href = '/login';
      return Promise.reject(error);
    }
    return Promise.reject(error);
  }
);

export const authApi = {
  login: (login: string, password: string) =>
    apiClient.post('/auth/login', { login, password }),
  me: () => apiClient.get('/auth/me'),
  logout: () => apiClient.post('/auth/logout', {}),
  refresh: () => apiClient.post('/auth/refresh', {}),
};

export const patientsApi = {
  list: (params?: { search?: string; page?: number; limit?: number }) =>
    apiClient.get('/patients', { params }),
  get: (id: string) => apiClient.get(`/patients/${id}`),
  create: (data: unknown) => apiClient.post('/patients', data),
  update: (id: string, data: unknown) => apiClient.put(`/patients/${id}`, data),
  history: (id: string, params?: { date_from?: string; date_to?: string }) =>
    apiClient.get(`/patients/${id}/history`, { params }),
};

export const ordersApi = {
  list: (params?: { status?: string; patient_id?: string; search?: string; page?: number; limit?: number; without_study?: boolean }) =>
    apiClient.get('/orders', { params }),
  get: (id: string) => apiClient.get(`/orders/${id}`),
  create: (data: unknown) => apiClient.post('/orders', data),
  update: (id: string, data: unknown) => apiClient.put(`/orders/${id}`, data),
  delete: (id: string) => apiClient.delete(`/orders/${id}`),
  history: (id: string) => apiClient.get(`/orders/${id}/history`),
  updateStatus: (id: string, data: unknown) => apiClient.put(`/orders/${id}/status`, data),
  getStudy: (id: string) => apiClient.get(`/orders/${id}/study`),
};

export const reportsApi = {
  list: (params?: { order_id?: string; status?: string }) =>
    apiClient.get('/reports', { params }),
  get: (id: string) => apiClient.get(`/reports/${id}`),
  create: (data: unknown) => apiClient.post('/reports', data),
  update: (id: string, data: unknown) => apiClient.put(`/reports/${id}`, data),
  sign: (id: string) => apiClient.post(`/reports/${id}/sign`, {}),
  issue: (id: string) => apiClient.post(`/reports/${id}/issue`, {}),
  secondOpinion: (reportId: string, data: unknown) =>
    apiClient.post(`/reports/${reportId}/second-opinion`, data),
  newVersion: (reportId: string) =>
    apiClient.post(`/reports/${reportId}/new-version`),
  pdf: (id: string) => apiClient.get(`/reports/${id}/pdf`, { responseType: 'blob' }),
};

export const orderPdfApi = {
  pdf: (id: string) => apiClient.get(`/orders/${id}/pdf`, { responseType: 'blob' }),
};

export const refsApi = {
  services: (params?: { modality?: string; search?: string }) =>
    apiClient.get('/refs/services', { params }),
  createService: (data: unknown) => apiClient.post('/refs/services', data),
  devices: (params?: { modality?: string; status?: string }) =>
    apiClient.get('/refs/devices', { params }),
  createDevice: (data: unknown) => apiClient.post('/refs/devices', data),
  updateDevice: (id: string, data: unknown) => apiClient.put(`/refs/devices/${id}`, data),
  deleteDevice: (id: string) => apiClient.delete(`/refs/devices/${id}`),
  icd10: (params?: { q?: string; chapter?: string; limit?: number }) =>
    apiClient.get('/refs/icd10', { params }),
  protocolTemplates: (params?: { modality?: string; service_id?: string }) =>
    apiClient.get('/refs/protocol-templates', { params }),
  createTemplate: (data: unknown) => apiClient.post('/refs/protocol-templates', data),
  updateTemplate: (id: string, data: unknown) => apiClient.put(`/refs/protocol-templates/${id}`, data),
  organization: () => apiClient.get('/refs/organization'),
  updateOrganization: (data: unknown) => apiClient.put('/refs/organization', data),
};

export const scheduleApi = {
  slots: (params: { device_id: string; date: string }) =>
    apiClient.get('/schedule/slots', { params }),
  createAppointment: (data: unknown) => apiClient.post('/schedule/appointments', data),
  updateAppointment: (id: string, data: unknown) => apiClient.put(`/schedule/appointments/${id}`, data),
  cancelAppointment: (id: string) => apiClient.delete(`/schedule/appointments/${id}`),
};

export const worklistApi = {
  list: (params?: { device_id?: string; status?: string; priority?: string }) =>
    apiClient.get('/worklist', { params }),
  markArrived: (orderId: string) => apiClient.post(`/worklist/${orderId}/arrived`),
  markInProgress: (orderId: string) => apiClient.post(`/worklist/${orderId}/in-progress`),
  qc: (orderId: string, params: { status: string; comment?: string }) =>
    apiClient.post(`/worklist/${orderId}/qc`, null, { params }),
  unmatched: () => apiClient.get('/worklist/unmatched'),
  resolveUnmatched: (unmatchedId: string, orderId: string) =>
    apiClient.post(`/worklist/unmatched/${unmatchedId}/resolve`, { order_id: orderId }),
  retake: (orderId: string, data: { comment?: string }) =>
    apiClient.post(`/worklist/${orderId}/retake`, data),
};

export const statsApi = {
  dashboard: (period?: string) => apiClient.get('/stats/dashboard', { params: { period } }),
  turnaround: (params: { from: string; to: string }) =>
    apiClient.get('/stats/turnaround', { params }),
  export: (params: { format: string; from?: string; to?: string }) =>
    apiClient.get('/stats/export', { params, responseType: 'blob' }),
};

export const adminApi = {
  users: (params?: { role?: string; search?: string }) =>
    apiClient.get('/admin/users', { params }),
  createUser: (data: unknown) => apiClient.post('/admin/users', data),
  updateUser: (id: string, data: unknown) => apiClient.put(`/admin/users/${id}`, data),
  resetPassword: (userId: string, data: { new_password: string }) =>
    apiClient.post(`/admin/users/${userId}/reset-password`, data),
  changePassword: (data: { current_password: string; new_password: string }) =>
    apiClient.post('/admin/change-password', data),
  loginHistory: (userId: string) => apiClient.get(`/admin/users/${userId}/login-history`),
  audit: (params?: { entity_type?: string; page?: number; limit?: number }) =>
    apiClient.get('/admin/audit', { params }),
};

export const dicomApi = {
  getViewerUrl: (studyInstanceUid: string, orthancStudyId?: string) =>
    apiClient.get(`/dicom/viewer-url/${studyInstanceUid}`, {
      params: orthancStudyId ? { orthanc_study_id: orthancStudyId } : undefined,
    }),
};

export const notificationsApi = {
  cito: () => apiClient.get('/notifications/cito'),
  list: () => apiClient.get('/notifications/list'),
  clear: () => apiClient.post('/notifications/clear'),
};
