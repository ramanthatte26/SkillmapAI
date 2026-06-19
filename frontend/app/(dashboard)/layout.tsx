'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Navbar from '@/components/layout/Navbar';
import { getToken, clearSession } from '@/lib/auth';
import { authApi } from '@/lib/api';
import { Loader2 } from 'lucide-react';
import { isTokenExpired } from '@/lib/utils';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [isValidating, setIsValidating] = useState(true);

  useEffect(() => {
    let active = true;
    const token = getToken();

    if (!token || isTokenExpired(token)) {
      clearSession();
      router.replace('/login?logged_out=true');
      return;
    }

    // Call /auth/me to validate the token
    authApi.me()
      .then(() => {
        if (active) {
          setIsValidating(false);
        }
      })
      .catch((err) => {
        console.error('Auth validation failed:', err);
        if (active) {
          clearSession();
          router.replace('/login?logged_out=true');
        }
      });


    return () => {
      active = false;
    };
  }, [router, pathname]);

  if (isValidating) {
    return (
      <div style={{
        minHeight: '100dvh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-base)',
        color: 'var(--text-muted)',
        gap: '1rem',
      }}>
        <Loader2 size={36} style={{ animation: 'spin 1.8s linear infinite', color: 'var(--amber-400)' }} />
        <span style={{ fontSize: '0.8rem', fontWeight: 600, letterSpacing: '0.07em', color: 'var(--text-secondary)' }}>
          VERIFYING SESSION...
        </span>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100dvh', background: 'var(--bg-base)', position: 'relative' }}>
      {/* Subtle background glow */}
      <div style={{
        position: 'fixed', top: '-10%', right: '-5%',
        width: '45%', height: '50%', pointerEvents: 'none', zIndex: 0,
        background: 'radial-gradient(ellipse, rgba(245,158,11,0.05) 0%, transparent 70%)',
      }} aria-hidden="true" />
      <Navbar />
      <main style={{ position: 'relative', zIndex: 1 }}>
        {children}
      </main>
    </div>
  );
}

