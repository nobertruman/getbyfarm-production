"use client";

import { API_BASE_URL } from "./config";
import { clearTokens, getAccessToken, refreshAccessToken } from "./auth";

export class ApiError extends Error {
  status;
  fields;
  constructor(message, status, fields = {}) {
    super(message);
    this.status = status;
    this.fields = fields;
  }
}

/** Turns DRF error bodies ({detail} or {field: [msgs]}) into one readable sentence. */
function readableError(body, fallback) {
  if (body && typeof body === "object") {
    const b = body;
    if (typeof b.detail === "string") return { message: b.detail, fields: {} };
    const fields = {};
    const parts = [];
    for (const [k, v] of Object.entries(b)) {
      const msgs = Array.isArray(v) ? v.map(String) : [String(v)];
      fields[k] = msgs;
      parts.push(k === "non_field_errors" ? msgs.join(" ") : `${k.replace(/_/g, " ")}: ${msgs.join(" ")}`);
    }
    if (parts.length) return { message: parts.join(" "), fields };
  }
  return { message: fallback, fields: {} };
}

export async function apiFetch(path, options = {}, retried = false) {
  const headers = new Headers(options.headers);
  if (options.body !== undefined) headers.set("Content-Type", "application/json");
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let res;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  } catch {
    throw new ApiError("Can't reach GetbyFarm right now. Check your connection and try again.", 0);
  }

  if (res.status === 401 && !retried && token) {
    if (await refreshAccessToken()) return apiFetch(path, options, true);
    clearTokens();
    if (typeof window !== "undefined") {
      // Intentional hard navigation: a full page load clears all in-memory state once the session has ended.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign("/login?expired=1");
    }
    throw new ApiError("Your session expired. Please log in again.", 401);
  }
  if (res.status === 429) throw new ApiError("You're doing that too often. Please wait a moment.", 429);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const { message, fields } = readableError(
      body,
      res.status >= 500 ? "Something went wrong on our side. Please try again." : res.statusText,
    );
    throw new ApiError(message, res.status, fields);
  }
  if (res.status === 204) return undefined;
  return res.json();
}
