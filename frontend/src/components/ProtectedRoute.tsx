import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireOnboarding?: boolean;
}

export const ProtectedRoute = ({ children, requireOnboarding = true }: ProtectedRouteProps) => {
  const { isAuthenticated, isLoading, needsOnboarding } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <div className="flex h-screen items-center justify-center">Loading...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requireOnboarding && needsOnboarding) {
    return <Navigate to="/onboarding" replace />;
  }
  
  if (!requireOnboarding && !needsOnboarding && location.pathname === '/onboarding') {
    return <Navigate to="/chat" replace />;
  }

  return <>{children}</>;
};
