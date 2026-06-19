// ─────────────────────────────────────────────────────────────────
// SkillMap AI — Shared TypeScript Types
// Mirrors the FastAPI Pydantic schemas exactly.
// ─────────────────────────────────────────────────────────────────

// ── Auth ──────────────────────────────────────────────────────────

export interface UserResponse {
  id: string;
  email: string;
  username: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserWithToken {
  user: UserResponse;
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  username: string;
  password: string;
}

// ── Roadmaps ──────────────────────────────────────────────────────

export type RoadmapStatus = 'processing' | 'active' | 'archived';
export type AINotesStatus = 'pending' | 'generating' | 'done' | 'failed';

export interface RoadmapSummary {
  id: string;
  title: string;
  thumbnail_url: string | null;
  total_videos: number;
  completed_videos: number;
  status: RoadmapStatus;
  completion_percentage: number;
  created_at: string;
}

export interface VideoResponse {
  id: string;
  youtube_id: string;
  title: string;
  thumbnail_url: string | null;
  duration_seconds: number | null;
  position: number;
  ai_notes: string | null;
  ai_notes_status: AINotesStatus;
  is_completed: boolean;
}

export interface RoadmapDetailResponse {
  id: string;
  title: string;
  description: string | null;
  playlist_url: string;
  playlist_id: string;
  thumbnail_url: string | null;
  total_videos: number;
  completed_videos: number;
  status: RoadmapStatus;
  completion_percentage: number;
  created_at: string;
  updated_at: string;
  videos: VideoResponse[];
}

export interface RoadmapImportResponse {
  roadmap_id: string;
  title: string;
  total_videos: number;
  status: RoadmapStatus;
  message: string;
}

export interface PlaylistImportRequest {
  playlist_url: string;
}

// ── Progress ──────────────────────────────────────────────────────

export interface ProgressUpdateRequest {
  is_completed: boolean;
  watch_time_seconds?: number;
  user_notes?: string | null;
}

export interface ProgressResponse {
  id: string;
  video_id: string;
  roadmap_id: string;
  is_completed: boolean;
  watch_time_seconds: number;
  user_notes: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProgressStatsResponse {
  roadmap_id: string;
  title: string;
  total_videos: number;
  completed_videos: number;
  remaining_videos: number;
  completion_percentage: number;
}

// ── Modules ───────────────────────────────────────────────────────

export interface ModuleResponse {
  id: string;
  name: string;
  description: string | null;
  position: number;
  videos: VideoResponse[];
}

// ── Insights ──────────────────────────────────────────────────────

export interface RoadmapInsightsResponse {
  summary: string;
  strengths: string[];
  weak_areas: string[];
  recommended_next_module: string;
  estimated_completion_days: number;
  study_recommendation: string;
}

// ── API Error ─────────────────────────────────────────────────────

export interface APIError {
  detail: string;
}

// ── Video Notes ───────────────────────────────────────────────────

export interface VideoNotesResponse {
  video_id: string;
  ai_notes_status: AINotesStatus;
  summary: string;
  key_concepts: string[];
  important_terms: string[];
  interview_questions: string[];
}

// ── Search ────────────────────────────────────────────────────────

export interface SearchResult {
  video_id: string;
  video_title: string;
  module_name: string | null;
  similarity_score: number;
  matched_content_preview: string;
}

export interface SearchResponse {
  results: SearchResult[];
}
