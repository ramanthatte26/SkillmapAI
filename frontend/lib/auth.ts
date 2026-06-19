// ─────────────────────────────────────────────────────────────────
// SkillMap AI — Token & User Storage Helpers
// ─────────────────────────────────────────────────────────────────

import type { UserResponse } from '@/types';

const TOKEN_KEY = 'skillmap_access_token';
const USER_KEY = 'skillmap_user';

// ── Token ─────────────────────────────────────────────────────────

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(TOKEN_KEY);
}

// ── User ──────────────────────────────────────────────────────────

export function getUser(): UserResponse | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as UserResponse;
  } catch {
    return null;
  }
}

export function setUser(user: UserResponse): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function removeUser(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(USER_KEY);
}

// ── Session ───────────────────────────────────────────────────────

export function isAuthenticated(): boolean {
  return !!getToken();
}

export function clearSession(): void {
  removeToken();
  removeUser();
  if (typeof document !== 'undefined') {
    document.cookie = 'skillmap_token=; path=/; max-age=0; SameSite=Lax';
  }
}

