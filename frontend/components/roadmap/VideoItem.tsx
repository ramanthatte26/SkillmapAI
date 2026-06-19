'use client';

import { useState } from 'react';
import Image from 'next/image';
import { formatDuration } from '@/lib/utils';
import type { VideoResponse, VideoNotesResponse } from '@/types';
import {
  Play, ExternalLink, CheckCircle2, FileText,
  BookOpen, MessageSquare, Tag, ChevronDown, ChevronUp,
  Loader2, RefreshCw,
} from 'lucide-react';

interface Props {
  video: VideoResponse;
  isCompleted: boolean;
  onToggle: (videoId: string, completed: boolean) => Promise<void>;
  isUpdating?: boolean;
  onGenerateNotes?: (videoId: string) => Promise<VideoNotesResponse | null>;
  isGeneratingNotes?: boolean;
}

export default function VideoItem({
  video,
  isCompleted,
  onToggle,
  isUpdating,
  onGenerateNotes,
  isGeneratingNotes = false,
}: Props) {
  const [imgError, setImgError] = useState(false);
  const [prevCompleted, setPrevCompleted] = useState(isCompleted);
  const [optimisticCompleted, setOptimisticCompleted] = useState(isCompleted);
  const [notesOpen, setNotesOpen] = useState(false);

  // Sync state with props during render
  if (isCompleted !== prevCompleted) {
    setPrevCompleted(isCompleted);
    setOptimisticCompleted(isCompleted);
  }

  async function handleCheck(e: React.ChangeEvent<HTMLInputElement>) {
    const next = e.target.checked;
    setOptimisticCompleted(next); // optimistic UI
    try {
      await onToggle(video.id, next);
    } catch {
      setOptimisticCompleted(!next); // revert on error
    }
  }

  // Parse stored notes from ai_notes JSON blob (may be null or malformed)
  let parsedNotes: VideoNotesResponse | null = null;
  if (video.ai_notes && video.ai_notes_status === 'done') {
    try {
      const raw = JSON.parse(video.ai_notes);
      parsedNotes = {
        video_id: video.id,
        ai_notes_status: video.ai_notes_status,
        summary: raw.summary ?? '',
        key_concepts: raw.key_concepts ?? [],
        important_terms: raw.important_terms ?? [],
        interview_questions: raw.interview_questions ?? [],
      };
    } catch {
      parsedNotes = null;
    }
  }

  const hasNotes = parsedNotes !== null;
  const notesStatusIsPending = video.ai_notes_status === 'pending' || video.ai_notes_status === 'failed';
  const notesStatusIsGenerating = video.ai_notes_status === 'generating' || isGeneratingNotes;

  async function handleGenerateClick(e: React.MouseEvent) {
    e.stopPropagation();
    if (!onGenerateNotes) return;
    await onGenerateNotes(video.id);
    setNotesOpen(true);
  }

  return (
    <div
      id={`video-item-${video.id}`}
      style={{
        borderRadius: '12px',
        border: '1px solid',
        borderColor: optimisticCompleted
          ? 'rgba(52, 211, 153, 0.15)'
          : 'var(--border-subtle)',
        overflow: 'hidden',
        transition: 'all 0.2s ease',
        opacity: isUpdating ? 0.7 : 1,
        background: optimisticCompleted
          ? 'rgba(16, 185, 129, 0.04)'
          : 'transparent',
      }}
    >
      {/* ── Main Row ───────────────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: '1rem',
          padding: '1rem 1.25rem',
        }}
      >
        {/* Position number */}
        <div style={{
          width: '28px', height: '28px', borderRadius: '8px', flexShrink: 0, marginTop: '2px',
          background: optimisticCompleted
            ? 'rgba(16,185,129,0.15)'
            : 'var(--bg-card)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '0.78rem', fontWeight: 700,
          color: optimisticCompleted ? 'var(--emerald-400)' : 'var(--text-muted)',
        }}>
          {optimisticCompleted ? <CheckCircle2 size={14} /> : video.position}
        </div>

        {/* Thumbnail */}
        <div style={{
          width: '100px', height: '58px', borderRadius: '8px',
          background: 'var(--bg-card)', overflow: 'hidden', flexShrink: 0, position: 'relative',
        }}>
          {video.thumbnail_url && !imgError ? (
            <Image
              src={video.thumbnail_url}
              alt={video.title}
              fill
              sizes="100px"
              style={{ objectFit: 'cover' }}
              onError={() => setImgError(true)}
            />
          ) : (
            <div style={{
              width: '100%', height: '100%',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'linear-gradient(135deg, rgba(245,158,11,0.08) 0%, rgba(239,68,68,0.05) 100%)',
            }}>
              <Play size={20} color="rgba(245,158,11,0.4)" strokeWidth={1.5} />
            </div>
          )}
        </div>

        {/* Info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{
            margin: 0, fontSize: '0.9rem', fontWeight: 500,
            color: optimisticCompleted ? 'var(--text-muted)' : 'var(--text-primary)',
            lineHeight: 1.4,
            textDecoration: optimisticCompleted ? 'line-through' : 'none',
            display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
            transition: 'color 0.2s, text-decoration 0.2s',
          }}>
            {video.title}
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginTop: '0.375rem', flexWrap: 'wrap' }}>
            {video.duration_seconds && (
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                {formatDuration(video.duration_seconds)}
              </span>
            )}
            <a
              href={`https://www.youtube.com/watch?v=${video.youtube_id}`}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '3px',
                fontSize: '0.78rem', color: 'var(--amber-500)', textDecoration: 'none', fontWeight: 500,
              }}
            >
              Watch <ExternalLink size={11} />
            </a>

            {/* ── Notes button / status ─────────────────────────── */}
            {onGenerateNotes && (
              notesStatusIsGenerating ? (
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: '4px',
                  fontSize: '0.72rem', color: 'var(--text-muted)',
                }}>
                  <Loader2 size={11} style={{ animation: 'spin 1s linear infinite' }} />
                  Generating notes…
                </span>
              ) : hasNotes ? (
                <button
                  onClick={(e) => { e.stopPropagation(); setNotesOpen((o) => !o); }}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: '3px',
                    fontSize: '0.72rem', color: 'var(--amber-400)', fontWeight: 600,
                    background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.18)',
                    borderRadius: '5px', padding: '2px 8px', cursor: 'pointer',
                  }}
                >
                  <FileText size={11} />
                  {notesOpen ? 'Hide Notes' : 'View Notes'}
                  {notesOpen ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                </button>
              ) : (
                <button
                  id={`generate-notes-btn-${video.id}`}
                  onClick={handleGenerateClick}
                  disabled={isGeneratingNotes}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: '3px',
                    fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 500,
                    background: 'transparent', border: '1px solid var(--border-subtle)',
                    borderRadius: '5px', padding: '2px 8px', cursor: 'pointer',
                    transition: 'all 0.2s',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = 'rgba(245,158,11,0.35)';
                    e.currentTarget.style.color = 'var(--amber-400)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'var(--border-subtle)';
                    e.currentTarget.style.color = 'var(--text-muted)';
                  }}
                >
                  {video.ai_notes_status === 'failed' ? (
                    <><RefreshCw size={11} /> Retry Notes</>
                  ) : (
                    <><FileText size={11} /> Generate Notes</>
                  )}
                </button>
              )
            )}
          </div>
        </div>

        {/* Checkbox */}
        <div style={{ flexShrink: 0, marginTop: '2px' }}>
          <input
            type="checkbox"
            id={`check-${video.id}`}
            className="custom-checkbox"
            checked={optimisticCompleted}
            onChange={handleCheck}
            disabled={isUpdating}
            aria-label={`Mark "${video.title}" as ${optimisticCompleted ? 'incomplete' : 'complete'}`}
          />
        </div>
      </div>

      {/* ── AI Notes Panel ─────────────────────────────────────── */}
      {hasNotes && notesOpen && parsedNotes && (
        <div style={{
          borderTop: '1px solid var(--border-subtle)',
          padding: '1.25rem 1.375rem',
          background: 'rgba(0,0,0,0.14)',
          display: 'flex',
          flexDirection: 'column',
          gap: '1.125rem',
          animation: 'fadeIn 0.2s ease',
        }}>

          {/* Summary */}
          <div>
            <div style={{
              display: 'flex', alignItems: 'center', gap: '5px',
              marginBottom: '0.5rem',
              fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.05em',
              color: 'var(--amber-400)',
            }}>
              <FileText size={12} /> SUMMARY
            </div>
            <p style={{
              margin: 0, fontSize: '0.82rem', lineHeight: 1.6,
              color: 'var(--text-secondary)',
            }}>
              {parsedNotes.summary}
            </p>
          </div>

          {/* Key Concepts + Important Terms side-by-side */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem' }}>

            {/* Key Concepts */}
            {parsedNotes.key_concepts.length > 0 && (
              <div style={{
                background: 'rgba(99,102,241,0.04)',
                border: '1px solid rgba(129,140,248,0.1)',
                borderRadius: '10px', padding: '0.875rem 1rem',
              }}>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '5px',
                  marginBottom: '0.625rem',
                  fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.05em',
                  color: 'rgb(129,140,248)',
                }}>
                  <BookOpen size={12} /> KEY CONCEPTS
                </div>
                <ul style={{
                  margin: 0, paddingLeft: '1.1rem',
                  display: 'flex', flexDirection: 'column', gap: '0.3rem',
                }}>
                  {parsedNotes.key_concepts.map((c, i) => (
                    <li key={i} style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                      {c}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Important Terms */}
            {parsedNotes.important_terms.length > 0 && (
              <div style={{
                background: 'rgba(16,185,129,0.03)',
                border: '1px solid rgba(52,211,153,0.1)',
                borderRadius: '10px', padding: '0.875rem 1rem',
              }}>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '5px',
                  marginBottom: '0.625rem',
                  fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.05em',
                  color: 'var(--emerald-400)',
                }}>
                  <Tag size={12} /> IMPORTANT TERMS
                </div>
                <ul style={{
                  margin: 0, paddingLeft: '1.1rem',
                  display: 'flex', flexDirection: 'column', gap: '0.3rem',
                }}>
                  {parsedNotes.important_terms.map((t, i) => (
                    <li key={i} style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                      {t}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Interview Questions */}
          {parsedNotes.interview_questions.length > 0 && (
            <div style={{
              background: 'rgba(245,158,11,0.03)',
              border: '1px solid rgba(245,158,11,0.1)',
              borderRadius: '10px', padding: '0.875rem 1rem',
            }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '5px',
                marginBottom: '0.625rem',
                fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.05em',
                color: 'var(--amber-400)',
              }}>
                <MessageSquare size={12} /> INTERVIEW QUESTIONS
              </div>
              <ol style={{
                margin: 0, paddingLeft: '1.25rem',
                display: 'flex', flexDirection: 'column', gap: '0.375rem',
              }}>
                {parsedNotes.interview_questions.map((q, i) => (
                  <li key={i} style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    {q}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
