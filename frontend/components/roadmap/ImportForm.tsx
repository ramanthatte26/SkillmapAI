'use client';

import { useState } from 'react';
import { roadmapsApi } from '@/lib/api';
import { Link2, Loader2, Sparkles } from 'lucide-react';

interface Props {
  onSuccess: () => void;
}

export default function ImportForm({ onSuccess }: Props) {
  const [url, setUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setSuccessMsg('');

    const trimmed = url.trim();
    if (!trimmed) {
      setError('Please enter a YouTube playlist URL.');
      return;
    }
    if (!trimmed.includes('youtube.com') && !trimmed.includes('youtu.be')) {
      setError('Must be a valid YouTube URL.');
      return;
    }

    setIsLoading(true);
    try {
      const result = await roadmapsApi.import({ playlist_url: trimmed });
      setSuccessMsg(`✓ "${result.title}" imported — ${result.total_videos} videos`);
      setUrl('');
      setTimeout(() => {
        setSuccessMsg('');
        onSuccess();
      }, 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed. Check the URL and try again.');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="glass-card" style={{ padding: '1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', marginBottom: '1rem' }}>
        <div style={{
          width: '32px', height: '32px', borderRadius: '9px', flexShrink: 0,
          background: 'linear-gradient(135deg, rgba(245,158,11,0.2) 0%, rgba(239,68,68,0.12) 100%)',
          border: '1px solid rgba(245,158,11,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Sparkles size={16} color="var(--amber-400)" />
        </div>
        <div>
          <h3 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            Import a Playlist
          </h3>
          <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Turn any YouTube playlist into a learning roadmap
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.625rem', flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 280px', position: 'relative' }}>
          <Link2 size={15} color="var(--text-muted)" style={{
            position: 'absolute', left: '0.875rem', top: '50%',
            transform: 'translateY(-50%)', pointerEvents: 'none',
          }} />
          <input
            id="import-url-input"
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://www.youtube.com/playlist?list=PL..."
            className="input-field"
            style={{ paddingLeft: '2.5rem' }}
            disabled={isLoading}
            aria-label="YouTube playlist URL"
          />
        </div>
        <button
          id="import-submit-btn"
          type="submit"
          className="btn-primary"
          disabled={isLoading}
          style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            minWidth: '130px', justifyContent: 'center',
          }}
        >
          {isLoading ? (
            <>
              <Loader2 size={15} style={{ animation: 'spin 0.8s linear infinite' }} />
              Importing…
            </>
          ) : (
            'Import Playlist'
          )}
        </button>
      </form>

      {/* Feedback */}
      {error && (
        <p role="alert" style={{
          marginTop: '0.75rem', fontSize: '0.875rem', color: 'var(--rose-400)',
          padding: '0.625rem 0.875rem', borderRadius: '8px',
          background: 'rgba(244, 63, 94, 0.08)', border: '1px solid rgba(251,113,133,0.2)',
        }}>
          {error}
        </p>
      )}
      {successMsg && (
        <p role="status" style={{
          marginTop: '0.75rem', fontSize: '0.875rem', color: 'var(--emerald-400)',
          padding: '0.625rem 0.875rem', borderRadius: '8px',
          background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(52,211,153,0.2)',
        }}>
          {successMsg}
        </p>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
