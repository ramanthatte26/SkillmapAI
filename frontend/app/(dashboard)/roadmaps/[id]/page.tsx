'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Image from 'next/image';
import { roadmapsApi, progressApi, videosApi, searchApi } from '@/lib/api';
import VideoItem from '@/components/roadmap/VideoItem';
import { clampPct, formatDate } from '@/lib/utils';
import type { RoadmapDetailResponse, ModuleResponse, RoadmapInsightsResponse, VideoNotesResponse, SearchResult } from '@/types';
import {
  ArrowLeft, ExternalLink, Play, CheckCircle2,
  Video, BarChart3, Calendar, Sparkles, ChevronDown, ChevronUp,
  Brain, Lightbulb, Clock, Check, AlertCircle,
} from 'lucide-react';

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
  const fetchInsights = useCallback((roadmapId: string) => {
    setIsLoadingInsights(true);
    setInsightsError('');
    roadmapsApi.getInsights(roadmapId)
      .then((data) => {
        setInsights(data);
      })
      .catch((err) => {
        console.error('Failed to load insights:', err);
        setInsightsError(err instanceof Error ? err.message : 'Failed to load insights');
      })
      .finally(() => setIsLoadingInsights(false));
  }, []);

  // Fetch roadmap detail and modules
  useEffect(() => {
    if (!id) return;
    Promise.resolve().then(() => {
      setIsLoading(true);
    });

    const roadmapPromise = roadmapsApi.get(id)
      .then((data) => {
        setRoadmap(data);
        const completed = new Set(
          data.videos.filter((v) => v.is_completed).map((v) => v.id)
        );
        setCompletedIds(completed);
      });

    const modulesPromise = roadmapsApi.getModules(id)
      .then((data) => {
        setModules(data);
        setOpenModuleIds(new Set(data.map((m) => m.id)));
      })
      .catch((err) => {
        console.error('Failed to load modules:', err);
      });

    // Fetch insights independently so it does not block the UI
    fetchInsights(id);

    Promise.all([roadmapPromise, modulesPromise])
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load roadmap'))
      .finally(() => setIsLoading(false));
  }, [id, fetchInsights]);

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
            onClick={() => fetchInsights(id)}
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
                            <span style={{ fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--amber-400)', background: 'rgba(245,158,11,0.08)', padding: '2px 6px', borderRadius: '4px' }}>
                              Video Match
                            </span>
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
                          borderLeft: '3px solid var(--amber-400)',
                        }}>
                          {result.matched_content_preview}
                        </div>
                      )}

                      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.25rem' }}>
                        <button
                          onClick={() => {
                            setActiveTab('list');
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
                          <Play size={12} /> Go to Video
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
