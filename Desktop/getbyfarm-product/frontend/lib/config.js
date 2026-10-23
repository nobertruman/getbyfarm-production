// Empty string = same-origin (recommended: the reverse proxy serves the site and /api on one domain,
// so there is no CORS and the URL isn't baked into the build). Set NEXT_PUBLIC_API_URL only if the API
// lives on a different domain. `??` (not `||`) so an intentionally empty value is respected.
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
