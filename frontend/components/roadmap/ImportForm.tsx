'use client';

import { useState } from 'react';
import { roadmapsApi, courseVideoApi } from '@/lib/api';
import { Link2, Loader2, Sparkles } from 'lucide-react';

interface Props {
  onSuccess: () => void;
}

export default function ImportForm({ onSuccess }: Props) {
  const [importType, setImportType] = useState<'playlist' | 'video'>('playlist');
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
      setError(
        importType === 'playlist'
          ? 'Please enter a YouTube playlist URL.'
          : 'Please enter a YouTube course video URL.'
      );
      return;
    }
    if (!trimmed.includes('youtube.com') && !trimmed.includes('youtu.be')) {
      setError('Must be a valid YouTube URL.');
      return;
    }

    setIsLoading(true);
    try {
      if (importType === 'playlist') {
        const result = await roadmapsApi.import({ playlist_url: trimmed });
        setSuccessMsg(`✓ "${result.title}" imported — starting pipeline`);
      } else {
        const result = await courseVideoApi.import({ video_url: trimmed });
        setSuccessMsg(`✓ "${result.title}" imported — generating curriculum`);
      }
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
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', marginBottom: '1.25rem' }}>
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
            {importType === 'playlist' ? 'Import a Playlist' : 'Import Course Video'}
          </h3>
          <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {importType === 'playlist'
              ? 'Turn any YouTube playlist into a learning roadmap'
              : 'Turn any long-form YouTube course video into a structured roadmap'}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div style={{
        display: 'flex',
        gap: '0.375rem',
        marginBottom: '1.25rem',
        background: 'rgba(0,0,0,0.2)',
        padding: '3px',
        borderRadius: '8px',
        width: 'fit-content',
        border: '1px solid var(--border-subtle)'
      }}>
        <button
          type="button"
          onClick={() => { setImportType('playlist'); setUrl(''); setError(''); }}
          style={{
            padding: '0.375rem 0.875rem',
            fontSize: '0.78rem',
            fontWeight: 600,
            borderRadius: '6px',
            cursor: 'pointer',
            border: 'none',
            background: importType === 'playlist' ? 'rgba(255,255,255,0.06)' : 'transparent',
            color: importType === 'playlist' ? 'var(--amber-400)' : 'var(--text-muted)',
            transition: 'all 0.2s',
          }}
        >
          YouTube Playlist
        </button>
        <button
          type="button"
          onClick={() => { setImportType('video'); setUrl(''); setError(''); }}
          style={{
            padding: '0.375rem 0.875rem',
            fontSize: '0.78rem',
            fontWeight: 600,
            borderRadius: '6px',
            cursor: 'pointer',
            border: 'none',
            background: importType === 'video' ? 'rgba(255,255,255,0.06)' : 'transparent',
            color: importType === 'video' ? 'var(--amber-400)' : 'var(--text-muted)',
            transition: 'all 0.2s',
          }}
        >
          Single Course Video
        </button>
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
            placeholder={
              importType === 'playlist'
                ? 'https://www.youtube.com/playlist?list=PL...'
                : 'https://www.youtube.com/watch?v=...'
            }
            className="input-field"
            style={{ paddingLeft: '2.5rem' }}
            disabled={isLoading}
            aria-label={importType === 'playlist' ? 'YouTube playlist URL' : 'YouTube video URL'}
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
            importType === 'playlist' ? 'Import Playlist' : 'Import Video'
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
