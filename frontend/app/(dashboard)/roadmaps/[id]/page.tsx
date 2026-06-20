'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Image from 'next/image';
import { roadmapsApi, progressApi, videosApi, searchApi } from '@/lib/api';
import VideoItem from '@/components/roadmap/VideoItem';
import { clampPct, formatDate, formatDuration } from '@/lib/utils';
import type { RoadmapDetailResponse, ModuleResponse, RoadmapInsightsResponse, VideoNotesResponse, SearchResult } from '@/types';
import {
  ArrowLeft, ExternalLink, Play, CheckCircle2,
  Video, BarChart3, Calendar, Sparkles, ChevronDown, ChevronUp,
  Brain, Lightbulb, Clock, Check, AlertCircle,
  FileText, BookOpen, MessageSquare, Tag, Loader2
} from 'lucide-react';

function formatSeconds(secs: number | null | undefined): string {
  if (secs === null || secs === undefined) return '00:00';
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  return h > 0 
    ? `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
    : `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function SkeletonDetail() {
  return (
    <div style={{ maxWidth: '900px', margin: '0 auto', padding: '2rem 1.5rem' }}>
      <div className="skeleton" style={{ height: '20px', width: '100px', marginBottom: '2rem', borderRadius: '8px' }} />
      <div className="skeleton" style={{ height: '200px', borderRadius: '16px', marginBottom: '2rem' }} />
      <div className="skeleton" style={{ height: '32px', width: '60%', marginBottom: '1rem', borderRadius: '8px' }} />
      {[1,2,3,4,5].map(i => (
        <div key={i} className="skeleton" style={{ height: '80px', marginBottom: '0.625rem', borderRadius: '12px' }} />
      ))}
    </div>
  );
}

function highlightText(text: string, query: string) {
  if (!query || !query.trim() || !text) return <span>{text}</span>;
  const words = query.split(/\s+/).map(w => w.replace(/[^\w]/g, '')).filter(w => w.length > 2);
  if (words.length === 0) return <span>{text}</span>;
  const escapedWords = words.map(w => w.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&'));
  const regex = new RegExp(`(${escapedWords.join('|')})`, 'gi');
  const parts = text.split(regex);
  return (
    <span>
      {parts.map((part, index) => 
        regex.test(part) ? (
          <mark key={index} style={{ backgroundColor: 'rgba(245, 158, 11, 0.3)', color: 'var(--amber-200)', borderRadius: '2px', padding: '0 2px' }}>
            {part}
          </mark>
        ) : (
          part
        )
      )}
    </span>
  );
}


function PipelineFailed({ roadmapTitle, onGoBack }: { roadmapTitle: string; onGoBack: () => void }) {
  return (
    <div style={{ maxWidth: '540px', margin: '4rem auto', padding: '0 1.5rem' }}>
      <button
        onClick={onGoBack}
        className="btn-secondary"
        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', marginBottom: '2rem' }}
      >
        <ArrowLeft size={15} /> Back to Dashboard
      </button>

      <div className="glass-card fade-in" style={{
        padding: '2.5rem 2rem', display: 'flex', flexDirection: 'column', gap: '1.25rem',
        border: '1px solid rgba(239, 68, 68, 0.2)', background: 'rgba(239, 68, 68, 0.02)',
        textAlign: 'center', alignItems: 'center'
      }}>
        <div style={{
          width: '48px', height: '48px', borderRadius: '50%',
          background: 'rgba(239, 68, 68, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--rose-400)',
        }}>
          <AlertCircle size={24} />
        </div>
        <div>
          <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 0.5rem' }}>
            Roadmap Generation Failed
          </h2>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            We encountered an issue while generating modules, notes, or search vectors for <strong>{roadmapTitle}</strong>. This could be due to API limit restrictions, video access restrictions, or server overload.
          </p>
        </div>
        <button
          onClick={onGoBack}
          className="btn-primary"
          style={{ marginTop: '0.5rem' }}
        >
          Return to Dashboard
        </button>
      </div>
    </div>
  );
}


function PipelineChecklist({ status, roadmapTitle, onGoBack }: { status: string; roadmapTitle: string; onGoBack: () => void }) {
  const steps = [
    {
      key: 'importing',
      label: 'Ingesting Playlist Videos & Transcripts',
      description: 'Fetching video metadata and grabbing available captions.',
      isDone: ['generating_modules', 'generating_notes', 'building_search_index', 'ready'].includes(status),
      isActive: ['importing', 'processing'].includes(status),
    },
    {
      key: 'modules',
      label: 'Structuring Learning Modules',
      description: 'Grouping related concepts into logical chapters using AI.',
      isDone: ['generating_notes', 'building_search_index', 'ready'].includes(status),
      isActive: status === 'generating_modules',
    },
    {
      key: 'notes',
      label: 'Generating AI Video Notes',
      description: 'Summarizing key topics, terms, and interview questions.',
      isDone: ['building_search_index', 'ready'].includes(status),
      isActive: status === 'generating_notes',
    },
    {
      key: 'index',
      label: 'Building Transcript Search Index',
      description: 'Mapping transcripts to the database for transcript-aware search.',
      isDone: status === 'ready',
      isActive: status === 'building_search_index',
    },
  ];

  return (
    <div style={{ maxWidth: '540px', margin: '4rem auto', padding: '0 1.5rem' }}>
      <button
        onClick={onGoBack}
        className="btn-secondary"
        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', marginBottom: '2rem' }}
      >
        <ArrowLeft size={15} /> Back to Dashboard
      </button>

      <div className="glass-card fade-in" style={{ padding: '2.25rem 2rem', display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
        <div>
          <span className="badge badge-processing" style={{ marginBottom: '0.75rem' }}>Generating Roadmap</span>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 0.5rem', lineHeight: 1.35 }}>
            {roadmapTitle}
          </h2>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
            We are constructing your personalized study guide. This might take a minute depending on the size of the playlist. Feel free to leave this page and check back later.
          </p>
        </div>

        {/* Progress Line/Checklist */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', position: 'relative', paddingLeft: '0.5rem' }}>
          {steps.map((step, idx) => {
            const state = step.isDone ? 'done' : step.isActive ? 'active' : 'pending';
            return (
              <div key={step.key} style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start' }}>
                {/* Indicator Node */}
                <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <div style={{
                    width: '24px', height: '24px', borderRadius: '50%',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: state === 'done' ? 'rgba(16,185,129,0.15)' : state === 'active' ? 'rgba(245,158,11,0.15)' : 'rgba(255,255,255,0.02)',
                    border: `1.5px solid ${state === 'done' ? 'var(--emerald-400)' : state === 'active' ? 'var(--amber-400)' : 'var(--border-default)'}`,
                    color: state === 'done' ? 'var(--emerald-400)' : state === 'active' ? 'var(--amber-400)' : 'var(--text-muted)',
                    fontSize: '0.75rem', fontWeight: 600, flexShrink: 0, zIndex: 2,
                  }}>
                    {state === 'done' ? <Check size={12} strokeWidth={3} /> : idx + 1}
                  </div>
                  {idx < steps.length - 1 && (
                    <div style={{
                      position: 'absolute', top: '24px', bottom: '-24px', width: '2px',
                      background: step.isDone ? 'var(--emerald-500)' : 'var(--border-subtle)',
                      zIndex: 1,
                    }} />
                  )}
                </div>

                {/* Text Details */}
                <div style={{ flex: 1, paddingTop: '1px' }}>
                  <h4 style={{
                    margin: '0 0 2px', fontSize: '0.9rem', fontWeight: 600,
                    color: state === 'done' ? 'var(--emerald-400)' : state === 'active' ? 'var(--text-primary)' : 'var(--text-muted)',
                  }}>
                    {step.label}
                    {state === 'active' && (
                      <span style={{
                        display: 'inline-block', width: '6px', height: '6px',
                        borderRadius: '50%', background: 'var(--amber-400)',
                        marginLeft: '8px', animation: 'ping 1s infinite alternate',
                      }} />
                    )}
                  </h4>
                  <p style={{ margin: 0, fontSize: '0.78rem', color: state === 'pending' ? 'var(--text-muted)' : 'var(--text-secondary)', lineHeight: 1.45 }}>
                    {step.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}


export default function RoadmapDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [roadmap, setRoadmap] = useState<RoadmapDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [completedIds, setCompletedIds] = useState<Set<string>>(new Set());
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [imgError, setImgError] = useState(false);

  const [modules, setModules] = useState<ModuleResponse[]>([]);
  const [isGeneratingModules, setIsGeneratingModules] = useState(false);
  const [openModuleIds, setOpenModuleIds] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState<'modules' | 'list' | 'search'>('modules');

  const isSingleVideo = modules.some((m) => m.module_start_time !== null && m.module_start_time !== undefined);

  useEffect(() => {
    if (isSingleVideo && activeTab === 'list') {
      setActiveTab('modules');
    }
  }, [isSingleVideo, activeTab]);

  const [insights, setInsights] = useState<RoadmapInsightsResponse | null>(null);
  const [isLoadingInsights, setIsLoadingInsights] = useState(false);
  const [insightsError, setInsightsError] = useState('');

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [hasSearched, setHasSearched] = useState(false);

  // Notes state: Set of videoIds currently being generated, and a cache of returned notes
  const [generatingNotes, setGeneratingNotes] = useState<Set<string>>(new Set());
  const [videoNotesCache, setVideoNotesCache] = useState<Record<string, VideoNotesResponse>>({});

  // Fetch insights helper
  const fetchInsights = useCallback((roadmapId: string, forceRefresh = false) => {
    setIsLoadingInsights(true);
    setInsightsError('');
    roadmapsApi.getInsights(roadmapId, forceRefresh)
      .then((data) => {
        setInsights(data);
      })
      .catch((err) => {
        console.error('Failed to load insights:', err);
        setInsightsError(err instanceof Error ? err.message : 'Failed to load insights');
      })
      .finally(() => setIsLoadingInsights(false));
  }, []);

  // Fetch modules helper
  const fetchModules = useCallback((roadmapId: string) => {
    return roadmapsApi.getModules(roadmapId)
      .then((data) => {
        setModules(data);
        setOpenModuleIds(new Set(data.map((m) => m.id)));
      })
      .catch((err) => {
        console.error('Failed to load modules:', err);
      });
  }, []);

  // Fetch roadmap detail and modules
  useEffect(() => {
    if (!id) return;
    setIsLoading(true);

    roadmapsApi.get(id)
      .then((data) => {
        setRoadmap(data);
        const completed = new Set(
          data.videos.filter((v) => v.is_completed).map((v) => v.id)
        );
        setCompletedIds(completed);

        // If the roadmap is ready or active, fetch modules and insights
        if (data.status === 'ready' || data.status === 'active') {
          Promise.all([
            fetchModules(id),
            fetchInsights(id)
          ]).finally(() => {
            setIsLoading(false);
          });
        } else {
          setIsLoading(false);
        }
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load roadmap');
        setIsLoading(false);
      });
  }, [id, fetchInsights, fetchModules]);

  // Polling logic when roadmap status is processing/importing etc.
  useEffect(() => {
    if (!id || !roadmap) return;
    
    const isProcessing = [
      'processing',
      'importing',
      'generating_modules',
      'generating_notes',
      'building_search_index'
    ].includes(roadmap.status);

    if (!isProcessing) return;

    let pollInterval = setInterval(() => {
      roadmapsApi.get(id)
        .then((data) => {
          setRoadmap(data);
          const completed = new Set(
            data.videos.filter((v) => v.is_completed).map((v) => v.id)
          );
          setCompletedIds(completed);

          // If transition to ready/active, fetch modules and insights
          if (data.status === 'ready' || data.status === 'active') {
            fetchModules(id);
            fetchInsights(id);
          }
        })
        .catch((err) => {
          console.error('Polling error:', err);
        });
    }, 3000);

    return () => clearInterval(pollInterval);
  }, [id, roadmap?.status, fetchModules, fetchInsights]);

  // Toggle video completion
  const handleToggle = useCallback(async (videoId: string, completed: boolean) => {
    setUpdatingId(videoId);
    try {
      await progressApi.updateVideo(videoId, { is_completed: completed });
      setCompletedIds((prev) => {
        const next = new Set(prev);
        if (completed) {
          next.add(videoId);
        } else {
          next.delete(videoId);
        }
        return next;
      });
      // Update roadmap completed_videos counter locally
      setRoadmap((prev) => {
        if (!prev) return prev;
        const delta = completed ? 1 : -1;
        const newCount = Math.max(0, Math.min(prev.total_videos, prev.completed_videos + delta));
        return {
          ...prev,
          completed_videos: newCount,
          completion_percentage: prev.total_videos > 0
            ? (newCount / prev.total_videos) * 100
            : 0,
        };
      });
    } finally {
      setUpdatingId(null);
    }
  }, []);

  // Generate learning modules
  const handleGenerateModules = useCallback(async () => {
    setIsGeneratingModules(true);
    try {
      await roadmapsApi.generateModules(id);
      const data = await roadmapsApi.getModules(id);
      setModules(data);
      setOpenModuleIds(new Set(data.map((m) => m.id)));
      setActiveTab('modules');
      // Refresh insights to reflect the new module structure
      fetchInsights(id);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to generate modules');
    } finally {
      setIsGeneratingModules(false);
    }
  }, [id, fetchInsights]);

  // Semantic search query handler
  const handleSearch = useCallback(async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    setSearchError('');
    setHasSearched(true);

    try {
      const data = await searchApi.search({
        roadmap_id: id,
        query: searchQuery,
      });
      setSearchResults(data.results);
    } catch (err) {
      console.error('Failed to perform search:', err);
      setSearchError(err instanceof Error ? err.message : 'Search failed. Please try again.');
    } finally {
      setIsSearching(false);
    }
  }, [id, searchQuery]);

  // Generate AI notes for a single video
  const handleGenerateNotes = useCallback(async (videoId: string): Promise<VideoNotesResponse | null> => {
    setGeneratingNotes((prev) => new Set([...prev, videoId]));
    try {
      const notes = await videosApi.generateNotes(videoId);
      // Cache the result
      setVideoNotesCache((prev) => ({ ...prev, [videoId]: notes }));
      // Also update the video's ai_notes in the local roadmap state so VideoItem
      // can parse it immediately without a full page refresh.
      setRoadmap((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          videos: prev.videos.map((v) =>
            v.id === videoId
              ? { ...v, ai_notes: JSON.stringify({
                  summary: notes.summary,
                  key_concepts: notes.key_concepts,
                  important_terms: notes.important_terms,
                  interview_questions: notes.interview_questions,
                }), ai_notes_status: 'done' as const }
              : v
          ),
        };
      });
      // Update module videos state too
      setModules((prev) =>
        prev.map((mod) => ({
          ...mod,
          videos: mod.videos.map((v) =>
            v.id === videoId
              ? { ...v, ai_notes: JSON.stringify({
                  summary: notes.summary,
                  key_concepts: notes.key_concepts,
                  important_terms: notes.important_terms,
                  interview_questions: notes.interview_questions,
                }), ai_notes_status: 'done' as const }
              : v
          ),
        }))
      );
      return notes;
    } catch (err) {
      console.error('Failed to generate notes for video', videoId, err);
      // Mark as failed in local state
      setRoadmap((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          videos: prev.videos.map((v) =>
            v.id === videoId ? { ...v, ai_notes_status: 'failed' as const } : v
          ),
        };
      });
      setModules((prev) =>
        prev.map((mod) => ({
          ...mod,
          videos: mod.videos.map((v) =>
            v.id === videoId ? { ...v, ai_notes_status: 'failed' as const } : v
          ),
        }))
      );
      return null;
    } finally {
      setGeneratingNotes((prev) => {
        const next = new Set(prev);
        next.delete(videoId);
        return next;
      });
    }
  }, []);

  // Toggle single module card expansion
  const toggleModule = useCallback((moduleId: string) => {
    setOpenModuleIds((prev) => {
      const next = new Set(prev);
      if (next.has(moduleId)) {
        next.delete(moduleId);
      } else {
        next.add(moduleId);
      }
      return next;
    });
  }, []);

  // Compute dynamic module progress based on completedIds set
  const getModuleProgress = useCallback((moduleVideos: any[]) => {
    const completed = moduleVideos.filter((v) => completedIds.has(v.id)).length;
    const total = moduleVideos.length;
    const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
    return { completed, total, pct };
  }, [completedIds]);

  if (isLoading) return <SkeletonDetail />;

  if (error || !roadmap) {
    return (
      <div style={{ maxWidth: '900px', margin: '0 auto', padding: '2rem 1.5rem' }}>
        <button
          onClick={() => router.push('/dashboard')}
          className="btn-secondary"
          style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '2rem' }}
        >
          <ArrowLeft size={15} /> Back
        </button>
        <div className="glass-card" style={{
          padding: '3rem', textAlign: 'center',
          color: 'var(--rose-400)', background: 'rgba(244,63,94,0.06)',
        }}>
          <strong>Error:</strong> {error || 'Roadmap not found.'}
        </div>
      </div>
    );
  }

  if (roadmap.status === 'failed') {
    return <PipelineFailed roadmapTitle={roadmap.title} onGoBack={() => router.push('/dashboard')} />;
  }

  const isProcessing = [
    'processing',
    'importing',
    'generating_modules',
    'generating_notes',
    'building_search_index'
  ].includes(roadmap.status);

  if (isProcessing) {
    return <PipelineChecklist status={roadmap.status} roadmapTitle={roadmap.title} onGoBack={() => router.push('/dashboard')} />;
  }

  const pct = clampPct(roadmap.completion_percentage);
  const completedCount = roadmap.completed_videos;
  const isFullyDone = pct === 100;

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto', padding: '2rem 1.5rem 4rem' }}>

      {/* Back button */}
      <button
        id="back-to-dashboard-btn"
        onClick={() => router.push('/dashboard')}
        className="btn-secondary"
        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', marginBottom: '1.75rem' }}
      >
        <ArrowLeft size={15} /> Dashboard
      </button>

      {/* Hero card */}
      <div className="glass-card fade-in" style={{ overflow: 'hidden', marginBottom: '1.75rem' }}>
        {/* Thumbnail banner */}
        {roadmap.thumbnail_url && !imgError && (
          <div style={{ position: 'relative', height: '200px', overflow: 'hidden' }}>
            <Image
              src={roadmap.thumbnail_url}
              alt={roadmap.title}
              fill
              sizes="900px"
              style={{ objectFit: 'cover' }}
              priority
              onError={() => setImgError(true)}
            />
            {/* Gradient overlay */}
            <div style={{
              position: 'absolute', inset: 0,
              background: 'linear-gradient(to bottom, rgba(9,9,11,0.1) 0%, rgba(9,9,11,0.85) 100%)',
            }} />
          </div>
        )}

        <div style={{ padding: '1.5rem 1.75rem' }}>
          {/* Status + Date */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', marginBottom: '0.875rem', flexWrap: 'wrap' }}>
            <span className={`badge ${roadmap.status === 'active' ? 'badge-active' : roadmap.status === 'processing' ? 'badge-processing' : 'badge-archived'}`}>
              {roadmap.status}
            </span>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Calendar size={12} /> {formatDate(roadmap.created_at)}
            </span>
            {isFullyDone && (
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: '4px',
                padding: '2px 10px', borderRadius: '99px',
                background: 'rgba(16,185,129,0.15)', color: 'var(--emerald-400)',
                fontSize: '0.75rem', fontWeight: 700,
              }}>
                <CheckCircle2 size={12} /> Completed
              </span>
            )}
          </div>

          {/* Title */}
          <h1 style={{
            fontSize: 'clamp(1.125rem, 2.5vw, 1.5rem)', fontWeight: 700,
            color: 'var(--text-primary)', letterSpacing: '-0.02em',
            margin: '0 0 1.25rem',
          }}>
            {roadmap.title}
          </h1>

          {/* Stats row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
              <Video size={14} /> {roadmap.total_videos} videos
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
              <BarChart3 size={14} /> {completedCount} completed
            </span>
            <a
              href={roadmap.playlist_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.875rem', color: 'var(--amber-400)', textDecoration: 'none', fontWeight: 500 }}
            >
              <Play size={13} /> Open in YouTube <ExternalLink size={12} />
            </a>
          </div>

          {/* Progress */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                Overall progress
              </span>
              <span style={{
                fontSize: '0.875rem', fontWeight: 700,
                color: isFullyDone ? 'var(--emerald-400)' : 'var(--amber-400)',
              }}>
                {pct}%
              </span>
            </div>
            <div className="progress-track" style={{ height: '8px' }}>
              <div className="progress-fill" style={{ width: `${pct}%` }} />
            </div>
          </div>
        </div>
      </div>

      {/* Description */}
      {roadmap.description && (
        <div className="glass-card fade-in" style={{ padding: '1.25rem 1.5rem', marginBottom: '1.75rem' }}>
          <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.7 }}>
            {roadmap.description}
          </p>
        </div>
      )}

      {/* AI Learning Insights */}
      <div className="glass-card fade-in" style={{ padding: '1.5rem 1.75rem', marginBottom: '1.75rem', border: '1px solid rgba(245,158,11,0.08)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Brain size={18} color="var(--amber-400)" />
            <h2 style={{ fontSize: '1.0625rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              AI Learning Insights
            </h2>
          </div>
          
          <button
            onClick={() => fetchInsights(id, true)}
            disabled={isLoadingInsights}
            className="btn-secondary"
            style={{
              padding: '2px 10px',
              height: '28px',
              fontSize: '0.78rem',
              borderRadius: '6px',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <Sparkles size={11} />
            {isLoadingInsights ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>

        {isLoadingInsights ? (
          /* Loading State skeleton */
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <div className="skeleton" style={{ height: '18px', width: '100%', borderRadius: '4px' }} />
            <div className="skeleton" style={{ height: '18px', width: '90%', borderRadius: '4px' }} />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginTop: '0.5rem' }}>
              <div className="skeleton" style={{ height: '60px', borderRadius: '8px' }} />
              <div className="skeleton" style={{ height: '60px', borderRadius: '8px' }} />
            </div>
          </div>
        ) : insightsError ? (
          <div style={{ color: 'var(--rose-400)', fontSize: '0.85rem' }}>
            Failed to load AI insights: {insightsError}
          </div>
        ) : insights ? (
          /* Real Insights display */
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            
            {/* Summary */}
            <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.875rem', lineHeight: 1.55 }}>
              {insights.summary}
            </p>

            {/* Strengths & Weak Areas Side-by-Side */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem' }}>
              
              {/* Strengths */}
              <div style={{ background: 'rgba(16,185,129,0.02)', padding: '1rem 1.25rem', borderRadius: '10px', border: '1px solid rgba(52,211,153,0.08)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '0.625rem', color: 'var(--emerald-400)' }}>
                  <Check size={14} />
                  <h4 style={{ margin: 0, fontSize: '0.825rem', fontWeight: 700, letterSpacing: '0.05em' }}>
                    KEY STRENGTHS
                  </h4>
                </div>
                {insights.strengths.length > 0 ? (
                  <ul style={{ margin: 0, paddingLeft: '1.2rem', color: 'var(--text-secondary)', fontSize: '0.825rem', display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
                    {insights.strengths.map((s, idx) => (
                      <li key={idx} style={{ lineHeight: 1.4 }}>{s}</li>
                    ))}
                  </ul>
                ) : (
                  <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.825rem', fontStyle: 'italic' }}>
                    Complete videos with study notes to build strengths.
                  </p>
                )}
              </div>

              {/* Weak Areas */}
              <div style={{ background: 'rgba(239,68,68,0.02)', padding: '1rem 1.25rem', borderRadius: '10px', border: '1px solid rgba(248,113,113,0.08)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '0.625rem', color: 'var(--rose-400)' }}>
                  <AlertCircle size={14} />
                  <h4 style={{ margin: 0, fontSize: '0.825rem', fontWeight: 700, letterSpacing: '0.05em' }}>
                    AREAS FOR REVIEW
                  </h4>
                </div>
                {insights.weak_areas.length > 0 ? (
                  <ul style={{ margin: 0, paddingLeft: '1.2rem', color: 'var(--text-secondary)', fontSize: '0.825rem', display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
                    {insights.weak_areas.map((w, idx) => (
                      <li key={idx} style={{ lineHeight: 1.4 }}>{w}</li>
                    ))}
                  </ul>
                ) : (
                  <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.825rem', fontStyle: 'italic' }}>
                    All caught up!
                  </p>
                )}
              </div>

            </div>

            {/* Recommended Module & Est Time */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
              
              {/* Recommended next module */}
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '0.875rem 1.125rem', borderRadius: '10px', border: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div style={{ width: '36px', height: '36px', borderRadius: '8px', background: 'rgba(245,158,11,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <Lightbulb size={16} color="var(--amber-400)" />
                </div>
                <div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600 }}>RECOMMENDED NEXT MODULE</div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', fontWeight: 600, marginTop: '2px' }}>
                    {insights.recommended_next_module}
                  </div>
                </div>
              </div>

              {/* Est Completion time */}
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '0.875rem 1.125rem', borderRadius: '10px', border: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div style={{ width: '36px', height: '36px', borderRadius: '8px', background: 'rgba(245,158,11,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <Clock size={16} color="var(--amber-400)" />
                </div>
                <div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600 }}>EST. COMPLETION TIME</div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', fontWeight: 600, marginTop: '2px' }}>
                    {insights.estimated_completion_days === 0 ? 'Roadmap Completed!' : `${insights.estimated_completion_days} days left`}
                  </div>
                </div>
              </div>

            </div>

            {/* Study Recommendation Callout */}
            <div style={{
              background: 'linear-gradient(135deg, rgba(245,158,11,0.04) 0%, rgba(245,158,11,0.01) 100%)',
              padding: '1rem 1.25rem',
              borderRadius: '10px',
              borderLeft: '3px solid var(--amber-500)',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
            }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--amber-400)', letterSpacing: '0.02em' }}>
                STUDY ADVICE
              </div>
              <p style={{ margin: 0, fontSize: '0.825rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                {insights.study_recommendation}
              </p>
            </div>

          </div>
        ) : (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.825rem', fontStyle: 'italic' }}>
            No insights available. Complete some videos and refresh.
          </div>
        )}
      </div>

      {/* AI Module Generator invitation if empty */}
      {modules.length === 0 && (
        <div className="glass-card fade-in" style={{ padding: '2rem 1.75rem', marginBottom: '1.75rem', textAlign: 'center' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
            <div style={{
              width: '48px', height: '48px', borderRadius: '50%',
              background: 'rgba(245,158,11,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <Sparkles size={22} color="var(--amber-400)" />
            </div>
            <div>
              <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 0.25rem' }}>
                AI Learning Modules
              </h3>
              <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)', maxWidth: '450px', lineHeight: 1.5 }}>
                Automatically organize these {roadmap.total_videos} videos into structured, chronological learning modules designed for optimal studying.
              </p>
            </div>
            <button
              onClick={handleGenerateModules}
              disabled={isGeneratingModules}
              className="btn-primary"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
            >
              <Sparkles size={16} />
              {isGeneratingModules ? 'Generating Modules...' : 'Generate Learning Modules'}
            </button>
          </div>
        </div>
      )}

      {/* Video list / Modules list section */}
      <div className="fade-in" style={{ animationDelay: '0.15s' }}>
        {/* Section Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <h2 style={{ fontSize: '1.0625rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
            {activeTab === 'modules' && modules.length > 0 ? 'Learning Modules' : activeTab === 'search' ? 'Semantic Knowledge Search' : `Videos (${roadmap.videos.length})`}
          </h2>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            {modules.length > 0 && activeTab === 'modules' && (
              <button
                onClick={handleGenerateModules}
                disabled={isGeneratingModules}
                className="btn-secondary"
                style={{
                  padding: '4px 10px',
                  height: '32px',
                  fontSize: '0.8rem',
                  borderRadius: '8px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.375rem',
                }}
              >
                <Sparkles size={13} /> {isGeneratingModules ? 'Regenerating...' : 'Regenerate'}
              </button>
            )}
            
            <div style={{
              display: 'flex',
              gap: '2px',
              background: 'rgba(255,255,255,0.03)',
              padding: '3px',
              borderRadius: '8px',
              border: '1px solid var(--border-subtle)'
            }}>
              {modules.length > 0 && (
                <button
                  onClick={() => setActiveTab('modules')}
                  style={{
                    border: 'none',
                    padding: '4px 12px',
                    borderRadius: '6px',
                    fontSize: '0.78rem',
                    fontWeight: 500,
                    cursor: 'pointer',
                    background: activeTab === 'modules' ? 'rgba(245,158,11,0.12)' : 'transparent',
                    color: activeTab === 'modules' ? 'var(--amber-400)' : 'var(--text-muted)',
                    transition: 'all 0.2s',
                  }}
                >
                  Modules
                </button>
              )}
              {!isSingleVideo && (
                <button
                  onClick={() => setActiveTab('list')}
                  style={{
                    border: 'none',
                    padding: '4px 12px',
                    borderRadius: '6px',
                    fontSize: '0.78rem',
                    fontWeight: 500,
                    cursor: 'pointer',
                    background: activeTab === 'list' ? 'rgba(245,158,11,0.12)' : 'transparent',
                    color: activeTab === 'list' ? 'var(--amber-400)' : 'var(--text-muted)',
                    transition: 'all 0.2s',
                  }}
                >
                  All Videos
                </button>
              )}
              <button
                onClick={() => setActiveTab('search')}
                style={{
                  border: 'none',
                  padding: '4px 12px',
                  borderRadius: '6px',
                  fontSize: '0.78rem',
                  fontWeight: 500,
                  cursor: 'pointer',
                  background: activeTab === 'search' ? 'rgba(245,158,11,0.12)' : 'transparent',
                  color: activeTab === 'search' ? 'var(--amber-400)' : 'var(--text-muted)',
                  transition: 'all 0.2s',
                }}
              >
                Search
              </button>
            </div>
          </div>
        </div>

        {/* Content View */}
        {/* Content View */}
        {activeTab === 'modules' && modules.length > 0 ? (
          isSingleVideo ? (
            /* Single Course Video Modules View */
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {modules.map((mod) => {
                const video = mod.videos[0];
                if (!video) return null;

                const isCompleted = completedIds.has(video.id);
                const isUpdating = updatingId === video.id;
                const isGenerating = generatingNotes.has(video.id);

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
                const notesOpen = openModuleIds.has(mod.id);

                const toggleNotes = () => {
                  setOpenModuleIds((prev) => {
                    const next = new Set(prev);
                    if (next.has(mod.id)) {
                      next.delete(mod.id);
                    } else {
                      next.add(mod.id);
                    }
                    return next;
                  });
                };

                return (
                  <div
                    key={mod.id}
                    className="glass-card"
                    id={`video-item-${video.id}`}
                    style={{
                      overflow: 'hidden',
                      transition: 'all 0.2s ease',
                      border: isCompleted
                        ? '1px solid rgba(52, 211, 153, 0.15)'
                        : '1px solid var(--border-subtle)',
                      background: isCompleted
                        ? 'rgba(16, 185, 129, 0.04)'
                        : 'transparent',
                      opacity: isUpdating ? 0.7 : 1,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1.25rem', padding: '1.25rem 1.5rem' }}>
                      <div style={{
                        width: '32px', height: '32px', borderRadius: '10px', flexShrink: 0, marginTop: '2px',
                        background: isCompleted ? 'rgba(16,185,129,0.15)' : 'var(--bg-card)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '0.85rem', fontWeight: 700,
                        color: isCompleted ? 'var(--emerald-400)' : 'var(--text-muted)',
                        border: '1px solid',
                        borderColor: isCompleted ? 'rgba(16,185,129,0.2)' : 'var(--border-subtle)',
                      }}>
                        {isCompleted ? <CheckCircle2 size={16} /> : (mod.position + 1)}
                      </div>

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <h3 style={{
                          margin: '0 0 0.375rem', fontSize: '1rem', fontWeight: 600,
                          color: isCompleted ? 'var(--text-secondary)' : 'var(--text-primary)',
                          textDecoration: isCompleted ? 'line-through' : 'none',
                          lineHeight: 1.4,
                        }}>
                          {mod.name}
                        </h3>
                        {mod.description && (
                          <p style={{ margin: '0 0 0.75rem', fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                            {mod.description}
                          </p>
                        )}

                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                          {mod.module_start_time !== null && (
                            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                              <Clock size={12} /> Start: {formatSeconds(mod.module_start_time)}
                            </span>
                          )}
                          {video.duration_seconds && (
                            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                              Duration: {formatDuration(video.duration_seconds)}
                            </span>
                          )}

                          {mod.module_youtube_url && (
                            <a
                              href={mod.module_youtube_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{
                                display: 'inline-flex', alignItems: 'center', gap: '4px',
                                fontSize: '0.78rem', color: 'var(--amber-500)', textDecoration: 'none', fontWeight: 600,
                              }}
                            >
                              <Play size={12} fill="var(--amber-500)" /> Start Learning <ExternalLink size={10} />
                            </a>
                          )}

                          {video.ai_notes_status === 'generating' || isGenerating ? (
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                              <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> Generating notes…
                            </span>
                          ) : hasNotes ? (
                            <button
                              onClick={toggleNotes}
                              style={{
                                display: 'inline-flex', alignItems: 'center', gap: '3px',
                                fontSize: '0.75rem', color: 'var(--amber-400)', fontWeight: 600,
                                background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.18)',
                                borderRadius: '5px', padding: '2px 8px', cursor: 'pointer',
                              }}
                            >
                              <FileText size={11} /> {notesOpen ? 'Hide Notes' : 'View Notes'}
                              {notesOpen ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                            </button>
                          ) : (
                            <button
                              onClick={() => handleGenerateNotes(video.id)}
                              disabled={isGenerating}
                              style={{
                                display: 'inline-flex', alignItems: 'center', gap: '3px',
                                fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 500,
                                background: 'transparent', border: '1px solid var(--border-subtle)',
                                borderRadius: '5px', padding: '2px 8px', cursor: 'pointer',
                                transition: 'all 0.2s',
                              }}
                            >
                              <FileText size={11} /> Generate Notes
                            </button>
                          )}
                        </div>
                      </div>

                      <div style={{ flexShrink: 0, marginTop: '2px' }}>
                        <input
                          type="checkbox"
                          id={`check-module-${mod.id}`}
                          className="custom-checkbox"
                          checked={isCompleted}
                          onChange={async (e) => {
                            const checked = e.target.checked;
                            setCompletedIds((prev) => {
                              const next = new Set(prev);
                              if (checked) next.add(video.id);
                              else next.delete(video.id);
                              return next;
                            });
                            try {
                              await handleToggle(video.id, checked);
                            } catch {
                              setCompletedIds((prev) => {
                                const next = new Set(prev);
                                if (checked) next.delete(video.id);
                                else next.add(video.id);
                                return next;
                              });
                            }
                          }}
                          disabled={isUpdating}
                          aria-label={`Mark module "${mod.name}" as completed`}
                        />
                      </div>
                    </div>

                    {hasNotes && notesOpen && parsedNotes && (
                      <div style={{
                        borderTop: '1px solid var(--border-subtle)',
                        padding: '1.25rem 1.5rem',
                        background: 'rgba(0,0,0,0.14)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '1.125rem',
                      }}>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '0.5rem', fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.05em', color: 'var(--amber-400)' }}>
                            <FileText size={12} /> SUMMARY
                          </div>
                          <p style={{ margin: 0, fontSize: '0.82rem', lineHeight: 1.6, color: 'var(--text-secondary)' }}>
                            {parsedNotes.summary}
                          </p>
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem' }}>
                          {parsedNotes.key_concepts.length > 0 && (
                            <div style={{ background: 'rgba(99,102,241,0.04)', border: '1px solid rgba(129,140,248,0.1)', borderRadius: '10px', padding: '0.875rem 1rem' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '0.625rem', fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.05em', color: 'rgb(129,140,248)' }}>
                                <BookOpen size={12} /> KEY CONCEPTS
                              </div>
                              <ul style={{ margin: 0, paddingLeft: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                                {parsedNotes.key_concepts.map((c, i) => <li key={i} style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>{c}</li>)}
                              </ul>
                            </div>
                          )}

                          {parsedNotes.important_terms.length > 0 && (
                            <div style={{ background: 'rgba(16,185,129,0.03)', border: '1px solid rgba(52,211,153,0.1)', borderRadius: '10px', padding: '0.875rem 1rem' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '0.625rem', fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.05em', color: 'var(--emerald-400)' }}>
                                <Tag size={12} /> IMPORTANT TERMS
                              </div>
                              <ul style={{ margin: 0, paddingLeft: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                                {parsedNotes.important_terms.map((t, i) => <li key={i} style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>{t}</li>)}
                              </ul>
                            </div>
                          )}
                        </div>

                        {parsedNotes.interview_questions.length > 0 && (
                          <div style={{ background: 'rgba(245,158,11,0.03)', border: '1px solid rgba(245,158,11,0.1)', borderRadius: '10px', padding: '0.875rem 1rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '0.625rem', fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.05em', color: 'var(--amber-400)' }}>
                              <MessageSquare size={12} /> INTERVIEW QUESTIONS
                            </div>
                            <ol style={{ margin: 0, paddingLeft: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
                              {parsedNotes.interview_questions.map((q, i) => <li key={i} style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{q}</li>)}
                            </ol>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            /* Modules Collapsible Cards View */
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {modules.map((mod) => {
                const isOpen = openModuleIds.has(mod.id);
                const { completed, total, pct } = getModuleProgress(mod.videos);
                return (
                  <div
                    key={mod.id}
                    className="glass-card"
                    style={{
                      overflow: 'hidden',
                      transition: 'border-color 0.2s',
                      border: isOpen ? '1px solid rgba(245,158,11,0.2)' : '1px solid var(--border-subtle)',
                    }}
                  >
                    {/* Module Header */}
                    <div
                      onClick={() => toggleModule(mod.id)}
                      style={{
                        padding: '1.125rem 1.375rem',
                        cursor: 'pointer',
                        background: 'rgba(255,255,255,0.01)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: '1rem',
                        userSelect: 'none',
                      }}
                    >
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 0.25rem' }}>
                          {mod.name}
                        </h3>
                        {mod.description && (
                          <p style={{ margin: 0, fontSize: '0.825rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                            {mod.description}
                          </p>
                        )}
                      </div>
                      
                      <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', flexShrink: 0 }}>
                        <div style={{ textAlign: 'right' }}>
                          <span style={{ fontSize: '0.78rem', fontWeight: 500, color: 'var(--text-secondary)' }}>
                            {completed}/{total} videos
                          </span>
                          {total > 0 && (
                            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: pct === 100 ? 'var(--emerald-400)' : 'var(--amber-400)', marginTop: '2px' }}>
                              {pct}% done
                            </div>
                          )}
                        </div>
                        
                        <div style={{ color: 'var(--text-muted)' }}>
                          {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                        </div>
                      </div>
                    </div>

                    {/* Module Body */}
                    {isOpen && (
                      <div style={{
                        padding: '0 1.375rem 1.375rem',
                        borderTop: '1px solid var(--border-subtle)',
                        background: 'rgba(0,0,0,0.12)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.5rem',
                        paddingTop: '1.125rem',
                      }}>
                        {mod.videos.map((video) => (
                          <VideoItem
                            key={video.id}
                            video={video}
                            isCompleted={completedIds.has(video.id)}
                            onToggle={handleToggle}
                            isUpdating={updatingId === video.id}
                            onGenerateNotes={handleGenerateNotes}
                            isGeneratingNotes={generatingNotes.has(video.id)}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )
        ) : activeTab === 'search' ? (
          /* Semantic Search Section */
          <div className="glass-card fade-in" style={{ padding: '1.75rem 2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                Semantic Roadmap Search
              </h3>
              <p style={{ fontSize: '0.825rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.4 }}>
                Find concepts, topics, and interview questions across this roadmap. Enter a query in natural language like <i>"Where was recursion explained?"</i> or <i>"constructors in Python"</i>.
              </p>
            </div>

            <form onSubmit={handleSearch} style={{ display: 'flex', gap: '0.75rem' }}>
              <input
                id="search-query-input"
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search concepts, libraries, topics, or terms..."
                className="input-field"
                style={{ flex: 1, height: '42px' }}
                disabled={isSearching}
              />
              <button
                id="search-query-button"
                type="submit"
                className="btn-primary"
                style={{ height: '42px', padding: '0 1.5rem', display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
                disabled={isSearching || !searchQuery.trim()}
              >
                {isSearching ? 'Searching...' : 'Search'}
              </button>
            </form>

            {searchError && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.625rem',
                padding: '0.75rem 1rem',
                background: 'rgba(239, 68, 68, 0.08)',
                border: '1px solid rgba(239, 68, 68, 0.2)',
                borderRadius: '8px',
                color: 'var(--red-400)',
                fontSize: '0.825rem'
              }}>
                <AlertCircle size={16} />
                <span>{searchError}</span>
              </div>
            )}

            {isSearching ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '3rem 0', gap: '1rem' }}>
                <div style={{ border: '2px solid rgba(255,255,255,0.05)', borderTop: '2px solid var(--amber-400)', borderRadius: '50%', width: '28px', height: '28px', animation: 'spin 0.8s linear infinite' }} />
                <span style={{ fontSize: '0.825rem', color: 'var(--text-muted)' }}>Searching roadmap knowledge...</span>
              </div>
            ) : hasSearched ? (
              searchResults.length === 0 ? (
                /* Empty state */
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '3.5rem 0', gap: '0.75rem', textAlign: 'center' }}>
                  <AlertCircle size={32} style={{ color: 'var(--text-muted)' }} />
                  <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-secondary)' }}>No matches found</div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0, maxWidth: '280px' }}>
                    Try searching with different terms or check if notes have been generated for videos.
                  </p>
                </div>
              ) : (
                /* Results List */
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <div style={{ fontSize: '0.78rem', fontWeight: 500, color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.5rem' }}>
                    Found {searchResults.length} relevant match{searchResults.length > 1 ? 'es' : ''}
                  </div>
                  {searchResults.map((result) => (
                    <div
                      key={result.video_id}
                      className="glass-card"
                      style={{
                        padding: '1.25rem 1.5rem',
                        transition: 'border-color 0.2s',
                        border: '1px solid var(--border-subtle)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.75rem',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem', flexWrap: 'wrap' }}>
                            {result.source_type === 'transcript' ? (
                              <span style={{ fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--sky-400)', background: 'rgba(56,189,248,0.08)', padding: '2px 6px', borderRadius: '4px' }}>
                                Transcript Match
                              </span>
                            ) : result.source_type === 'notes' ? (
                              <span style={{ fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--amber-400)', background: 'rgba(245,158,11,0.08)', padding: '2px 6px', borderRadius: '4px' }}>
                                Notes Match
                              </span>
                            ) : (
                              <span style={{ fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--teal-400)', background: 'rgba(20,184,166,0.08)', padding: '2px 6px', borderRadius: '4px' }}>
                                Metadata Match
                              </span>
                            )}
                            {result.module_name && (
                              <span style={{ fontSize: '0.7rem', fontWeight: 500, color: 'var(--text-muted)', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                                • Module: {result.module_name}
                              </span>
                            )}
                          </div>
                          <h4 style={{ fontSize: '0.925rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                            {result.video_title}
                          </h4>
                        </div>
                        <div style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.25rem',
                          background: 'rgba(16,185,129,0.08)',
                          color: 'var(--emerald-400)',
                          padding: '3px 8px',
                          borderRadius: '6px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          flexShrink: 0
                        }}>
                          <Brain size={12} />
                          Match: {Math.round(result.similarity_score * 100)}%
                        </div>
                      </div>

                      {result.matched_content_preview && (
                        <div style={{
                          fontSize: '0.825rem',
                          color: 'var(--text-secondary)',
                          lineHeight: 1.5,
                          background: 'rgba(0,0,0,0.15)',
                          padding: '0.75rem 1rem',
                          borderRadius: '8px',
                          borderLeft: `3px solid ${
                            result.source_type === 'transcript'
                              ? 'var(--sky-400)'
                              : result.source_type === 'notes'
                              ? 'var(--amber-400)'
                              : 'var(--teal-400)'
                          }`,
                        }}>
                          {highlightText(result.matched_content_preview, searchQuery)}
                        </div>
                      )}

                      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '0.25rem' }}>
                        {isSingleVideo && result.start_time !== null && result.start_time !== undefined && (
                          <a
                            href={`https://www.youtube.com/watch?v=${roadmap?.playlist_id}&t=${Math.floor(result.start_time)}s`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="btn-primary"
                            style={{
                              padding: '4px 10px',
                              fontSize: '0.78rem',
                              borderRadius: '6px',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.375rem',
                              height: '28px',
                              textDecoration: 'none',
                              color: 'var(--bg-main)',
                            }}
                          >
                            <ExternalLink size={12} /> Watch at {formatSeconds(result.start_time)}
                          </a>
                        )}
                        <button
                          onClick={() => {
                            setActiveTab(isSingleVideo ? 'modules' : 'list');
                            setTimeout(() => {
                              const el = document.getElementById(`video-item-${result.video_id}`);
                              if (el) {
                                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                const prevBorderColor = el.style.borderColor;
                                const prevBoxShadow = el.style.boxShadow;
                                el.style.borderColor = 'var(--amber-400)';
                                el.style.boxShadow = '0 0 12px rgba(245, 158, 11, 0.2)';
                                setTimeout(() => {
                                  el.style.borderColor = prevBorderColor;
                                  el.style.boxShadow = prevBoxShadow;
                                }, 3000);
                              }
                            }, 100);
                          }}
                          className="btn-secondary"
                          style={{
                            padding: '4px 10px',
                            fontSize: '0.78rem',
                            borderRadius: '6px',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.375rem',
                            height: '28px',
                          }}
                        >
                          <Play size={12} /> {isSingleVideo ? 'Go to Module' : 'Go to Video'}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )
            ) : (
              /* Initial state before search */
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '2.5rem 0', gap: '0.5rem', color: 'var(--text-muted)' }}>
                <Brain size={24} style={{ opacity: 0.5, marginBottom: '0.5rem' }} />
                <span style={{ fontSize: '0.8rem' }}>Enter a query above to search inside this roadmap.</span>
              </div>
            )}
          </div>
        ) : (
          /* Flat Videos List View */
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {roadmap.videos.map((video) => (
              <VideoItem
                key={video.id}
                video={video}
                isCompleted={completedIds.has(video.id)}
                onToggle={handleToggle}
                isUpdating={updatingId === video.id}
                onGenerateNotes={handleGenerateNotes}
                isGeneratingNotes={generatingNotes.has(video.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
