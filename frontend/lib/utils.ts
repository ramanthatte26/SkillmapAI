import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

// shadcn/ui standard utility
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Format seconds → "4h 32m" or "45m" or "2m 30s"
export function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s > 0 ? `${s}s` : ''}`.trim();
  return `${s}s`;
}

// Format ISO date → "Jun 18, 2026"
export function formatDate(dateStr: string): string {
  try {
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }).format(new Date(dateStr));
  } catch {
    return dateStr;
  }
}

// Relative time → "3 days ago"
export function timeAgo(dateStr: string): string {
  try {
    const diff = Date.now() - new Date(dateStr).getTime();
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;
    return formatDate(dateStr);
  } catch {
    return dateStr;
  }
}

// Clamp completion percentage to [0, 100]
export function clampPct(pct: number): number {
  return Math.min(100, Math.max(0, Math.round(pct)));
}

// Check if a JWT is expired or invalid
export function isTokenExpired(token: string | null | undefined): boolean {
  if (!token) return true;
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return true;

    // Base64Url decode the payload (the second part)
    let payloadStr = parts[1];
    payloadStr = payloadStr.replace(/-/g, '+').replace(/_/g, '/');
    while (payloadStr.length % 4) {
      payloadStr += '=';
    }

    // atob is globally available in browser and next.js edge runtime
    const decoded = atob(payloadStr);
    const payload = JSON.parse(decoded);

    if (payload.exp && typeof payload.exp === 'number') {
      const now = Math.floor(Date.now() / 1000);
      return payload.exp < now;
    }
    return false;
  } catch {
    return true;
  }
}

