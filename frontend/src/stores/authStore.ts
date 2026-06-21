import { create } from 'zustand';
import { authApi } from '../api/client';

interface User {
  id: string;
  login: string;
  role: string;
  first_name: string;
  last_name: string;
  full_name: string;
}

interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  login: (token: string, user: User) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('ris_token'),
  user: JSON.parse(localStorage.getItem('ris_user') || 'null'),
  isAuthenticated: !!localStorage.getItem('ris_token'),
  
  login: (token: string, user: User) => {
    localStorage.setItem('ris_token', token);
    localStorage.setItem('ris_user', JSON.stringify(user));
    set({ token, user, isAuthenticated: true });
  },
  
  logout: () => {
    authApi.logout().catch(() => { /* ignore */ });
    localStorage.removeItem('ris_token');
    localStorage.removeItem('ris_user');
    set({ token: null, user: null, isAuthenticated: false });
  },
}));
