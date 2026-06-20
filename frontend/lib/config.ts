// Centralized API Configuration
// Read from NEXT_PUBLIC_API_URL, fallback to NEXT_PUBLIC_API_BASE_URL, fallback to localhost.
// Also, ensure we handle the /api/v1 prefix gracefully.

const rawUrl = process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

// Remove trailing slash if present
const cleanUrl = rawUrl.endsWith('/') ? rawUrl.slice(0, -1) : rawUrl;

// Ensure /api/v1 suffix is present
export const API_BASE_URL = cleanUrl.endsWith('/api/v1') 
  ? cleanUrl 
  : `${cleanUrl}/api/v1`;

export const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME || 'SkillMap AI';
