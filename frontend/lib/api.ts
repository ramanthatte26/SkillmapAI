// ─────────────────────────────────────────────────────────────────
// SkillMap AI — Centralized API Client
// Typed fetch wrapper that auto-attaches the Bearer token.
// ─────────────────────────────────────────────────────────────────

import { getToken, clearSession } from '@/lib/auth';
import { API_BASE_URL } from './config';

const BASE_URL = API_BASE_URL;


// ── Core fetch wrapper ────────────────────────────────────────────

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  // Auto-logout on 401 Unauthorized or 403 Forbidden
  if (res.status === 401 || res.status === 403) {
    clearSession();
    if (typeof window !== 'undefined') {
      window.location.href = '/login?logged_out=true';
    }
    throw new Error(res.status === 401 ? 'Unauthorized' : 'Forbidden');
  }


  // Parse error body
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      message = err.detail ?? err.message ?? message;
    } catch {
      // ignore parse error
    }
    throw new Error(message);
  }

  // Handle 204 No Content
  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

// ── HTTP verb helpers ─────────────────────────────────────────────

export const api = {
  get<T>(path: string): Promise<T> {
    return request<T>(path, { method: 'GET' });
  },

  post<T>(path: string, body?: unknown): Promise<T> {
    return request<T>(path, {
      method: 'POST',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  },

  put<T>(path: string, body?: unknown): Promise<T> {
    return request<T>(path, {
      method: 'PUT',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  },

  patch<T>(path: string, body?: unknown): Promise<T> {
    return request<T>(path, {
      method: 'PATCH',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  },

  delete<T>(path: string): Promise<T> {
    return request<T>(path, { method: 'DELETE' });
  },
};

// ── Domain-specific API calls ─────────────────────────────────────

import type {
  LoginRequest,
  RegisterRequest,
  UserWithToken,
  RoadmapSummary,
  RoadmapDetailResponse,
  RoadmapImportResponse,
  PlaylistImportRequest,
  ProgressUpdateRequest,
  ProgressResponse,
  ProgressStatsResponse,
  UserResponse,
  ModuleResponse,
  RoadmapInsightsResponse,
  VideoNotesResponse,
  SearchResult,
} from '@/types';

// Auth
export const authApi = {
  login: (data: LoginRequest) =>
    api.post<UserWithToken>('/auth/login', data),
  register: (data: RegisterRequest) =>
    api.post<UserWithToken>('/auth/register', data),
  me: () => api.get<UserResponse>('/auth/me'),
};

// Roadmaps
export const roadmapsApi = {
  list: (skip = 0, limit = 20) =>
    api.get<RoadmapSummary[]>(`/roadmaps?skip=${skip}&limit=${limit}`),
  get: (id: string) =>
    api.get<RoadmapDetailResponse>(`/roadmaps/${id}`),
  import: (data: PlaylistImportRequest) =>
    api.post<RoadmapImportResponse>('/roadmaps/import', data),
  generateModules: (id: string) =>
    api.post<{ modules_created: number }>(`/roadmaps/${id}/generate-modules`),
  getModules: (id: string) =>
    api.get<ModuleResponse[]>(`/roadmaps/${id}/modules`),
  getInsights: (id: string, forceRefresh = false) =>
    api.get<RoadmapInsightsResponse>(`/roadmaps/${id}/insights?force_refresh=${forceRefresh}`),
  delete: (id: string) =>
    api.delete<void>(`/roadmaps/${id}`),
};

// Progress
export const progressApi = {
  updateVideo: (videoId: string, data: ProgressUpdateRequest) =>
    api.put<ProgressResponse>(`/progress/video/${videoId}`, data),
  getRoadmapStats: (roadmapId: string) =>
    api.get<ProgressStatsResponse>(`/progress/roadmap/${roadmapId}`),
};

// Videos (AI Notes)
export const videosApi = {
  generateNotes: (videoId: string) =>
    api.post<VideoNotesResponse>(`/videos/${videoId}/generate-notes`),
  getNotes: (videoId: string) =>
    api.get<VideoNotesResponse>(`/videos/${videoId}/notes`),
};

// Search
export const searchApi = {
  search: (data: { roadmap_id: string; query: string }) =>
    api.post<{ results: SearchResult[] }>('/search', data),
};

// Course Video
export const courseVideoApi = {
  import: (data: { video_url: string }) =>
    api.post<RoadmapImportResponse>('/course-video/import', data),
};
