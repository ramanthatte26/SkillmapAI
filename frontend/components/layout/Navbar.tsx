'use client';

import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import { BookOpen, LogOut, LayoutDashboard } from 'lucide-react';

export default function Navbar() {
  const { user, logout } = useAuth();

  return (
    <header style={{
      position: 'sticky', top: 0, zIndex: 50,
      background: 'rgba(9, 9, 11, 0.85)',
      backdropFilter: 'blur(12px)',
      WebkitBackdropFilter: 'blur(12px)',
      borderBottom: '1px solid var(--border-subtle)',
    }}>
      <div style={{
        maxWidth: '1200px', margin: '0 auto',
        padding: '0 1.5rem',
        height: '60px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        {/* Brand */}
        <Link href="/dashboard" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
          <div style={{
            width: '32px', height: '32px', borderRadius: '9px',
            background: 'linear-gradient(135deg, #f59e0b 0%, #ef4444 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
          }}>
            <BookOpen size={17} color="white" strokeWidth={2.2} />
          </div>
          <span style={{
            fontWeight: 700, fontSize: '1.0625rem',
            color: 'var(--text-primary)', letterSpacing: '-0.01em',
          }}>
            SkillMap <span className="gradient-text">AI</span>
          </span>
        </Link>

        {/* Right side */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {/* Dashboard link (icon on mobile) */}
          <Link
            href="/dashboard"
            id="nav-dashboard-link"
            style={{
              display: 'flex', alignItems: 'center', gap: '0.4rem',
              color: 'var(--text-secondary)', textDecoration: 'none',
              fontSize: '0.875rem', fontWeight: 500, padding: '0.375rem 0.625rem',
              borderRadius: '8px', transition: 'color 0.15s, background 0.15s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--text-primary)';
              e.currentTarget.style.background = 'var(--bg-card)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--text-secondary)';
              e.currentTarget.style.background = 'transparent';
            }}
          >
            <LayoutDashboard size={15} />
            <span style={{ display: 'none' }} className="sm-show">Dashboard</span>
          </Link>

          {/* User chip */}
          {user && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '0.5rem',
              padding: '0.25rem 0.75rem 0.25rem 0.25rem',
              background: 'var(--bg-card)', borderRadius: '99px',
              border: '1px solid var(--border-default)',
            }}>
              {/* Avatar circle */}
              <div style={{
                width: '26px', height: '26px', borderRadius: '50%',
                background: 'linear-gradient(135deg, #f59e0b 0%, #ef4444 100%)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '0.75rem', fontWeight: 700, color: 'white', flexShrink: 0,
              }}>
                {user.username.charAt(0).toUpperCase()}
              </div>
              <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', fontWeight: 500, maxWidth: '100px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {user.username}
              </span>
            </div>
          )}

          {/* Logout */}
          <button
            id="nav-logout-btn"
            onClick={logout}
            style={{
              display: 'flex', alignItems: 'center', gap: '0.375rem',
              background: 'transparent', border: '1px solid var(--border-default)',
              borderRadius: '8px', padding: '0.375rem 0.75rem',
              color: 'var(--text-muted)', cursor: 'pointer',
              fontSize: '0.875rem', fontWeight: 500, fontFamily: 'inherit',
              transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--rose-400)';
              e.currentTarget.style.borderColor = 'rgba(251,113,133,0.4)';
              e.currentTarget.style.background = 'rgba(244,63,94,0.06)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--text-muted)';
              e.currentTarget.style.borderColor = 'var(--border-default)';
              e.currentTarget.style.background = 'transparent';
            }}
            aria-label="Sign out"
          >
            <LogOut size={14} />
            <span>Sign out</span>
          </button>
        </div>
      </div>
    </header>
  );
}
