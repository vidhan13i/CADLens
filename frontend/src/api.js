// P17 fix: single source of truth for API base URL.
// Set VITE_API_URL in a .env file to override (e.g. for staging/production).
export const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
