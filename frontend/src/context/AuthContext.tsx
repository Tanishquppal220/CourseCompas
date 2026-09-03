import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface UserProfile {
  id: number;
  registration_number: string;
  full_name: string;
  current_term: number | null;
  current_cgpa: number | null;
  program_name: string | null;
  admission_year: number | null;
  is_onboarded: boolean;
}

interface AuthState {
  user: UserProfile | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  needsOnboarding: boolean;
}

interface AuthContextType extends AuthState {
  login: (reg_number: string, password: string) => Promise<void>;
  register: (reg_number: string, password: string, full_name?: string) => Promise<void>;
  logout: () => void;
  updateProfile: (data: Partial<UserProfile>) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [state, setState] = useState<AuthState>({
    user: null,
    token: localStorage.getItem('token'),
    isAuthenticated: !!localStorage.getItem('token'),
    isLoading: true,
    needsOnboarding: false,
  });

  const fetchProfile = async (token: string) => {
    try {
      const response = await fetch('/api/auth/me', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const user = await response.json();
        setState(prev => ({
          ...prev,
          user,
          isAuthenticated: true,
          isLoading: false,
          needsOnboarding: !user.is_onboarded,
        }));
      } else {
        throw new Error('Failed to fetch profile');
      }
    } catch (error) {
      localStorage.removeItem('token');
      setState(prev => ({
        ...prev,
        token: null,
        user: null,
        isAuthenticated: false,
        isLoading: false,
      }));
    }
  };

  useEffect(() => {
    if (state.token) {
      fetchProfile(state.token);
    } else {
      setState(prev => ({ ...prev, isLoading: false }));
    }
  }, []);

  const login = async (reg_number: string, password: string) => {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ registration_number: reg_number, password }),
    });

    if (!response.ok) {
      throw new Error('Login failed');
    }

    const data = await response.json();
    localStorage.setItem('token', data.access_token);
    setState(prev => ({
      ...prev,
      token: data.access_token,
      user: data.user,
      isAuthenticated: true,
      needsOnboarding: data.needs_onboarding,
    }));
  };

  const register = async (reg_number: string, password: string, full_name?: string) => {
    const response = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ registration_number: reg_number, password, full_name }),
    });

    if (!response.ok) {
      throw new Error('Registration failed');
    }

    const data = await response.json();
    localStorage.setItem('token', data.access_token);
    setState(prev => ({
      ...prev,
      token: data.access_token,
      user: data.user,
      isAuthenticated: true,
      needsOnboarding: data.needs_onboarding,
    }));
  };

  const logout = () => {
    localStorage.removeItem('token');
    setState({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      needsOnboarding: false,
    });
  };

  const updateProfile = async (data: Partial<UserProfile>) => {
    if (!state.token) return;

    const response = await fetch('/api/auth/profile', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${state.token}`,
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      throw new Error('Failed to update profile');
    }

    const user = await response.json();
    setState(prev => ({
      ...prev,
      user,
      needsOnboarding: !user.is_onboarded,
    }));
  };

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout, updateProfile }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
