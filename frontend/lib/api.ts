import 'server-only';

// Server-only: holds the FastAPI base URL and API key. Never import from client
// components.
export const FASTAPI_URL = process.env.FASTAPI_URL || 'http://localhost:8000';

// Required: no default. The key must match the backend's API_KEY and is read
// from the environment so no real credential ever lives in the repo.
function getApiKey(): string {
  const key = process.env.API_KEY;
  if (!key) {
    throw new Error('API_KEY is not set. Set it to match the FastAPI backend.');
  }
  return key;
}

export function apiHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return { 'X-API-Key': getApiKey(), ...extra };
}
