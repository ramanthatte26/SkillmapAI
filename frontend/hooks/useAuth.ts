'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { authApi } from '@/lib/api';
import { getToken, getUser, setToken, setUser, clearSession } from '@/lib/auth';
import type { LoginRequest, RegisterRequest, UserResponse } from '@/types';

// Helper: sync token to cookie for middleware
function syncCookieToken(token: string | null) {
  if (typeof document === 'undefined') return;
  if (token) {
    // Expires in 1 day (MVP)
    document.cookie = `skillmap_token=${token}; path=/; max-age=86400; SameSite=Lax`;
  } else {
    document.cookie = 'skillmap_token=; path=/; max-age=0; SameSite=Lax';
  }
}

export function useAuth() {
  const router = useRouter();
  const [user, setUserState] = useState<UserResponse | null>(() => getUser());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = useCallback(
    async (data: LoginRequest) => {
      setIsLoading(true);
      setError(null);
      try {
        const res = await authApi.login(data);
        setToken(res.access_token);
        setUser(res.user);
        setUserState(res.user);
        syncCookieToken(res.access_token);
        router.push('/dashboard');
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Login failed';
        setError(msg);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [router]
  );

  const register = useCallback(
    async (data: RegisterRequest) => {
      setIsLoading(true);
      setError(null);
      try {
        const res = await authApi.register(data);
        setToken(res.access_token);
        setUser(res.user);
        setUserState(res.user);
        syncCookieToken(res.access_token);
        router.push('/dashboard');
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Registration failed';
        setError(msg);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [router]
  );

  const logout = useCallback(() => {
    clearSession();
    syncCookieToken(null);
    setUserState(null);
    router.push('/login');
  }, [router]);

  return {
    user,
    isLoading,
    error,
    isAuthenticated: !!getToken(),
    login,
    register,
    logout,
  };
}
