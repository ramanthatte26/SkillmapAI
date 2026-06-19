'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import { Eye, EyeOff, UserPlus, BookOpen } from 'lucide-react';

export default function RegisterPage() {
  const { register, isLoading, error } = useAuth();
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [localError, setLocalError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLocalError('');

    if (!email || !username || !password) {
      setLocalError('All fields are required.');
      return;
    }
    if (username.length < 3) {
      setLocalError('Username must be at least 3 characters.');
      return;
    }
    if (password.length < 8) {
      setLocalError('Password must be at least 8 characters.');
      return;
    }

    try {
      await register({ email, username, password });
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Registration failed');
    }
  }

  const displayError = localError || error;

  return (
    <div style={{ maxWidth: '420px', margin: '0 auto' }}>
      {/* Logo */}
      <div style={{ textAlign: 'center', marginBottom: '2.5rem' }} className="fade-in">
        <div style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          width: '56px', height: '56px', borderRadius: '16px',
          background: 'linear-gradient(135deg, #f59e0b 0%, #ef4444 100%)',
          marginBottom: '1rem', boxShadow: '0 8px 24px rgba(245,158,11,0.3)',
        }}>
          <BookOpen size={28} color="white" strokeWidth={2} />
        </div>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em', margin: 0 }}>
          SkillMap AI
        </h1>
        <p style={{ color: 'var(--text-muted)', marginTop: '0.375rem', fontSize: '0.9rem' }}>
          Start building your learning roadmap
        </p>
      </div>

      {/* Card */}
      <div className="glass-card fade-in" style={{ padding: '2rem', animationDelay: '0.1s' }}>
        <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '1.5rem', color: 'var(--text-primary)' }}>
          Create your account
        </h2>

        <form onSubmit={handleSubmit} noValidate>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.125rem' }}>

            {/* Email */}
            <div>
              <label htmlFor="reg-email" className="form-label">Email address</label>
              <input
                id="reg-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="input-field"
                disabled={isLoading}
                required
              />
            </div>

            {/* Username */}
            <div>
              <label htmlFor="reg-username" className="form-label">Username</label>
              <input
                id="reg-username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="learner_42"
                className="input-field"
                disabled={isLoading}
                minLength={3}
                maxLength={30}
                required
              />
              <p style={{ marginTop: '0.25rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Letters, numbers, and underscores only
              </p>
            </div>

            {/* Password */}
            <div>
              <label htmlFor="reg-password" className="form-label">Password</label>
              <div style={{ position: 'relative' }}>
                <input
                  id="reg-password"
                  type={showPw ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min. 8 characters"
                  className="input-field"
                  style={{ paddingRight: '3rem' }}
                  disabled={isLoading}
                  minLength={8}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  style={{
                    position: 'absolute', right: '0.875rem', top: '50%',
                    transform: 'translateY(-50%)', background: 'none', border: 'none',
                    cursor: 'pointer', color: 'var(--text-muted)', padding: '0.25rem',
                    display: 'flex', alignItems: 'center',
                  }}
                  aria-label={showPw ? 'Hide password' : 'Show password'}
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {/* Password strength mini-bar */}
              {password.length > 0 && (
                <div style={{ marginTop: '0.5rem', display: 'flex', gap: '4px' }}>
                  {[1, 2, 3, 4].map((level) => (
                    <div key={level} style={{
                      flex: 1, height: '3px', borderRadius: '99px',
                      background: password.length >= level * 2
                        ? level <= 1 ? '#ef4444'
                          : level <= 2 ? '#f59e0b'
                          : level <= 3 ? '#84cc16'
                          : '#10b981'
                        : 'var(--bg-elevated)',
                      transition: 'background 0.2s',
                    }} />
                  ))}
                </div>
              )}
            </div>

            {/* Error */}
            {displayError && (
              <div role="alert" style={{
                padding: '0.75rem 1rem', borderRadius: '8px',
                background: 'rgba(244, 63, 94, 0.1)',
                border: '1px solid rgba(251, 113, 133, 0.25)',
                color: 'var(--rose-400)', fontSize: '0.875rem',
              }}>
                {displayError}
              </div>
            )}

            {/* Submit */}
            <button
              id="register-submit-btn"
              type="submit"
              className="btn-primary"
              disabled={isLoading}
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginTop: '0.25rem' }}
            >
              {isLoading ? (
                <span className="dot-pulse">Creating account</span>
              ) : (
                <>
                  <UserPlus size={16} />
                  Create account
                </>
              )}
            </button>

            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textAlign: 'center', lineHeight: 1.5 }}>
              By creating an account you agree to our Terms of Service and Privacy Policy.
            </p>
          </div>
        </form>
      </div>

      {/* Footer link */}
      <p style={{ textAlign: 'center', marginTop: '1.5rem', color: 'var(--text-muted)', fontSize: '0.9rem' }} className="fade-in">
        Already have an account?{' '}
        <Link href="/login" style={{ color: 'var(--amber-400)', fontWeight: 600, textDecoration: 'none' }}
          onMouseEnter={(e) => (e.currentTarget.style.textDecoration = 'underline')}
          onMouseLeave={(e) => (e.currentTarget.style.textDecoration = 'none')}
        >
          Sign in
        </Link>
      </p>
    </div>
  );
}
