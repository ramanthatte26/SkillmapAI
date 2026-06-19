'use client';

import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { clampPct, timeAgo } from '@/lib/utils';
import type { RoadmapSummary } from '@/types';
import { Play, CheckCircle2, Clock, ChevronRight } from 'lucide-react';

interface Props {
  roadmap: RoadmapSummary;
}

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  active:     { label: 'Active',      cls: 'badge-active' },
  processing: { label: 'Processing',  cls: 'badge-processing' },
  archived:   { label: 'Archived',    cls: 'badge-archived' },
};

export default function RoadmapCard({ roadmap }: Props) {
  const [imgError, setImgError] = useState(false);
  const pct = clampPct(roadmap.completion_percentage);
  const badge = STATUS_BADGE[roadmap.status] ?? STATUS_BADGE.active;
  const isComplete = pct === 100;

  return (
    <Link
      href={`/roadmaps/${roadmap.id}`}
      id={`roadmap-card-${roadmap.id}`}
      style={{ textDecoration: 'none', display: 'block' }}
    >
      <article
        className="glass-card glass-card-hover fade-in"
        style={{ overflow: 'hidden', cursor: 'pointer', height: '100%', display: 'flex', flexDirection: 'column' }}
      >
        {/* Thumbnail */}
        <div style={{
          position: 'relative', aspectRatio: '16/9',
          background: 'var(--bg-card)',
          overflow: 'hidden', flexShrink: 0,
          borderRadius: '16px 16px 0 0',
        }}>
          {roadmap.thumbnail_url && !imgError ? (
            <Image
              src={roadmap.thumbnail_url}
              alt={roadmap.title}
              fill
              sizes="(max-width: 768px) 100vw, 400px"
              style={{ objectFit: 'cover' }}
              onError={() => setImgError(true)}
            />
          ) : (
            /* Fallback placeholder */
            <div style={{
              width: '100%', height: '100%',
              background: 'linear-gradient(135deg, rgba(245,158,11,0.12) 0%, rgba(239,68,68,0.08) 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Play size={40} color="rgba(245,158,11,0.4)" strokeWidth={1.5} />
            </div>
          )}

          {/* Completion overlay badge */}
          {isComplete && (
            <div style={{
              position: 'absolute', top: '0.625rem', right: '0.625rem',
              background: 'rgba(16,185,129,0.9)', backdropFilter: 'blur(8px)',
              borderRadius: '99px', padding: '3px 10px',
              display: 'flex', alignItems: 'center', gap: '4px',
              fontSize: '0.75rem', fontWeight: 700, color: '#fff',
            }}>
              <CheckCircle2 size={12} />
              Complete
            </div>
          )}
        </div>

        {/* Body */}
        <div style={{ padding: '1.125rem 1.25rem 1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem', flex: 1 }}>

          {/* Status + Date row */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className={`badge ${badge.cls}`}>{badge.label}</span>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '3px' }}>
              <Clock size={11} />
              {timeAgo(roadmap.created_at)}
            </span>
          </div>

          {/* Title */}
          <h3 style={{
            fontSize: '0.9875rem', fontWeight: 600, color: 'var(--text-primary)',
            lineHeight: 1.45, margin: 0,
            display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
          }}>
            {roadmap.title}
          </h3>

          {/* Progress */}
          <div style={{ marginTop: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                {roadmap.completed_videos} / {roadmap.total_videos} videos
              </span>
              <span style={{
                fontSize: '0.8rem', fontWeight: 700,
                color: isComplete ? 'var(--emerald-400)' : 'var(--amber-400)',
              }}>
                {pct}%
              </span>
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${pct}%` }} />
            </div>
          </div>

          {/* CTA row */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
            <span style={{
              fontSize: '0.8rem', color: 'var(--amber-500)', fontWeight: 600,
              display: 'flex', alignItems: 'center', gap: '2px',
              opacity: 0.85,
            }}>
              Open roadmap <ChevronRight size={14} />
            </span>
          </div>
        </div>
      </article>
    </Link>
  );
}
