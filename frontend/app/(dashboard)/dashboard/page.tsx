'use client';

import { useState } from 'react';
import { useRoadmaps } from '@/hooks/useRoadmaps';
import { useAuth } from '@/hooks/useAuth';
import RoadmapCard from '@/components/roadmap/RoadmapCard';
import ImportForm from '@/components/roadmap/ImportForm';
import { BookOpen, TrendingUp, CheckCircle, Clock } from 'lucide-react';
import { roadmapsApi } from '@/lib/api';

function StatPill({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: string | number }) {
  return (
    <div className="glass-card" style={{
      padding: '1rem 1.25rem',
      display: 'flex', alignItems: 'center', gap: '0.875rem',
    }}>
      <div style={{
        width: '38px', height: '38px', borderRadius: '10px', flexShrink: 0,
        background: 'linear-gradient(135deg, rgba(245,158,11,0.15) 0%, rgba(239,68,68,0.08) 100%)',
        border: '1px solid rgba(245,158,11,0.15)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon size={18} color="var(--amber-400)" strokeWidth={1.8} />
      </div>
      <div>
        <p style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1 }}>
          {value}
        </p>
        <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
          {label}
        </p>
      </div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="glass-card" style={{ overflow: 'hidden' }}>
      <div className="skeleton" style={{ aspectRatio: '16/9', borderRadius: '16px 16px 0 0' }} />
      <div style={{ padding: '1.125rem 1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        <div className="skeleton" style={{ height: '20px', width: '60%' }} />
        <div className="skeleton" style={{ height: '36px' }} />
        <div className="skeleton" style={{ height: '6px', borderRadius: '99px' }} />
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const { roadmaps, isLoading, error, refetch } = useRoadmaps();
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Derived stats
  const totalVideos = roadmaps.reduce((s, r) => s + r.total_videos, 0);
  const completedVideos = roadmaps.reduce((s, r) => s + r.completed_videos, 0);
  const avgCompletion = roadmaps.length > 0
    ? Math.round(roadmaps.reduce((s, r) => s + r.completion_percentage, 0) / roadmaps.length)
    : 0;

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  const confirmDelete = async () => {
    if (!deletingId) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await roadmapsApi.delete(deletingId);
      await refetch();
      setDeletingId(null);
    } catch (err: any) {
      setDeleteError(err.message || 'Failed to delete roadmap.');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '2rem 1.5rem 4rem' }}>

      {/* Greeting */}
      <div className="fade-in" style={{ marginBottom: '2rem' }}>
        <h1 style={{
          fontSize: 'clamp(1.5rem, 3vw, 2rem)', fontWeight: 700,
          color: 'var(--text-primary)', letterSpacing: '-0.025em', margin: 0,
        }}>
          {greeting},{' '}
          <span className="gradient-text">{user?.username ?? 'learner'}</span> 👋
        </h1>
        <p style={{ color: 'var(--text-muted)', marginTop: '0.375rem', fontSize: '0.9375rem' }}>
          {roadmaps.length === 0 ? 'Import your first playlist to get started.' : `You have ${roadmaps.length} roadmap${roadmaps.length !== 1 ? 's' : ''} in progress.`}
        </p>
      </div>

      {/* Stats row */}
      {roadmaps.length > 0 && (
        <div className="fade-in" style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '0.875rem', marginBottom: '2rem', animationDelay: '0.05s',
        }}>
          <StatPill icon={BookOpen}     label="Roadmaps"          value={roadmaps.length} />
          <StatPill icon={Clock}        label="Total videos"       value={totalVideos} />
          <StatPill icon={CheckCircle}  label="Videos completed"   value={completedVideos} />
          <StatPill icon={TrendingUp}   label="Avg. completion"    value={`${avgCompletion}%`} />
        </div>
      )}

      {/* Import form */}
      <div className="fade-in" style={{ marginBottom: '2.5rem', animationDelay: '0.1s' }}>
        <ImportForm onSuccess={refetch} />
      </div>

      {/* Section heading */}
      {(isLoading || roadmaps.length > 0) && (
        <div style={{ marginBottom: '1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h2 style={{ margin: 0, fontSize: '1.0625rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            Your Roadmaps
          </h2>
          {!isLoading && (
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              {roadmaps.length} total
            </span>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div role="alert" style={{
          padding: '1rem 1.25rem', borderRadius: '12px',
          background: 'rgba(244, 63, 94, 0.08)', border: '1px solid rgba(251,113,133,0.2)',
          color: 'var(--rose-400)', marginBottom: '1.5rem',
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Loading skeletons */}
      {isLoading && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1.25rem' }}>
          {[1, 2, 3].map((i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {/* Roadmap grid */}
      {!isLoading && roadmaps.length > 0 && (
        <div
          className="stagger"
          style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1.25rem' }}
          aria-label="Your roadmaps"
        >
          {roadmaps.map((roadmap) => (
            <RoadmapCard
              key={roadmap.id}
              roadmap={roadmap}
              onDelete={(id) => {
                setDeletingId(id);
                setDeleteError(null);
              }}
            />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && roadmaps.length === 0 && !error && (
        <div className="glass-card fade-in" style={{
          padding: '4rem 2rem', textAlign: 'center',
          background: 'var(--gradient-subtle)',
        }}>
          <div style={{
            width: '64px', height: '64px', borderRadius: '20px', margin: '0 auto 1.25rem',
            background: 'linear-gradient(135deg, rgba(245,158,11,0.15) 0%, rgba(239,68,68,0.08) 100%)',
            border: '1px solid rgba(245,158,11,0.15)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <BookOpen size={30} color="var(--amber-400)" strokeWidth={1.5} />
          </div>
          <h3 style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 0.5rem' }}>
            No roadmaps yet
          </h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', maxWidth: '320px', margin: '0 auto' }}>
            Paste a YouTube playlist URL above to generate your first structured learning roadmap.
          </p>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deletingId && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(9, 9, 11, 0.8)', backdropFilter: 'blur(8px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 9999, padding: '1rem',
        }}>
          <div className="glass-card fade-in" style={{
            maxWidth: '440px', width: '100%', padding: '1.75rem',
            background: 'var(--bg-surface)', border: '1px solid var(--border-strong)',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.8)',
            display: 'flex', flexDirection: 'column', gap: '1.25rem',
          }}>
            <div>
              <h3 style={{ fontSize: '1.18rem', fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 0.5rem' }}>
                Delete Roadmap?
              </h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', lineHeight: 1.5, margin: 0 }}>
                This will permanently delete this learning path, all associated videos, progress status, notes, and ChromaDB search vectors. This action cannot be undone.
              </p>
            </div>

            {deleteError && (
              <div style={{
                padding: '0.75rem 1rem', borderRadius: '8px',
                background: 'rgba(244, 63, 94, 0.08)', border: '1px solid rgba(251,113,133,0.2)',
                color: 'var(--rose-400)', fontSize: '0.8rem',
              }}>
                <strong>Error:</strong> {deleteError}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.25rem' }}>
              <button
                onClick={() => {
                  setDeletingId(null);
                  setDeleteError(null);
                }}
                disabled={isDeleting}
                style={{
                  background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-default)',
                  borderRadius: '8px', padding: '0.5rem 1rem', fontSize: '0.85rem', fontWeight: 600,
                  color: 'var(--text-primary)', cursor: 'pointer', transition: 'background 0.2s',
                }}
                onMouseEnter={(e) => { if (!isDeleting) e.currentTarget.style.background = 'rgba(255,255,255,0.08)'; }}
                onMouseLeave={(e) => { if (!isDeleting) e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; }}
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={isDeleting}
                style={{
                  background: 'var(--rose-500)', border: 'none',
                  borderRadius: '8px', padding: '0.5rem 1rem', fontSize: '0.85rem', fontWeight: 600,
                  color: '#fff', cursor: 'pointer', transition: 'background 0.2s',
                  display: 'flex', alignItems: 'center', gap: '6px',
                }}
                onMouseEnter={(e) => { if (!isDeleting) e.currentTarget.style.background = '#e11d48'; }}
                onMouseLeave={(e) => { if (!isDeleting) e.currentTarget.style.background = 'var(--rose-500)'; }}
              >
                {isDeleting ? 'Deleting...' : 'Delete Permanently'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
