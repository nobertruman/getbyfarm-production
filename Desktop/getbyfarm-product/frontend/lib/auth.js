"use client";

// JWT session for the Django API (SimpleJWT with refresh rotation + server-side blacklist).
// Tokens live in localStorage for this release. Trade-off: any XSS could read them. Mitigations in place:
// short-lived access token (30 min), rotating+blacklisted refresh token, strict CSP at the proxy, no
// third-party scripts. A later hardening step is moving the refresh token into an httpOnly cookie.
import { API_BASE_URL } from "./config";

const ACCESS = "getbyfarm.access";
const REFRESH = "getbyfarm.refresh";
const isBrowser = () => typeof window !== "undefined";

export const getAccessToken = () => (isBrowser() ? window.localStorage.getItem(ACCESS) : null);
export const getRefreshToken = () => (isBrowser() ? window.localStorage.getItem(REFRESH) : null);
export const isLoggedIn = () => !!getAccessToken();

function store(access, refresh) {
  window.localStorage.setItem(ACCESS, access);
  if (refresh) window.localStorage.setItem(REFRESH, refresh);
}
export function clearTokens() {
  if (!isBrowser()) return;
  window.localStorage.removeItem(ACCESS);
  window.localStorage.removeItem(REFRESH);
}

export async function login(email, password) {
  const res = await fetch(`${API_BASE_URL}/api/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
  });
  if (res.status === 429) throw new Error("Too many attempts. Please wait a minute and try again.");
  if (!res.ok) throw new Error("Incorrect email or password.");
  const data = await res.json();
  store(data.access, data.refresh);
}

export async function logout() {
  const refresh = getRefreshToken();
  clearTokens();
  if (refresh) {
    // Best effort: revoke server-side so a copied token can't be reused.
    await fetch(`${API_BASE_URL}/api/auth/logout/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    }).catch(() => undefined);
  }
}

let refreshing = null;

/** Single-flight refresh: parallel 401s share one refresh call (rotation would otherwise invalidate the second). */
export function refreshAccessToken() {
  if (refreshing) return refreshing;
  refreshing = (async () => {
    const refresh = getRefreshToken();
    if (!refresh) return null;
    const res = await fetch(`${API_BASE_URL}/api/auth/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    }).catch(() => null);
    if (!res || !res.ok) {
      clearTokens();
      return null;
    }
    const data = await res.json();
    store(data.access, data.refresh); // rotation returns a NEW refresh token: keep it
    return data.access;
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}
