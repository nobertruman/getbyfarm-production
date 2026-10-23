"use client";
import { useCallback, useEffect, useState } from "react";

/**
 * Loads data on mount and whenever `deps` change; exposes { data, error, loading, reload, setData }.
 * `loading` is derived (a request is loading until the latest one has settled), and stale responses
 * from earlier deps values or an unmounted component are ignored.
 */
export function useAsync(fn, deps = []) {
  const [tick, setTick] = useState(0);
  const [settled, setSettled] = useState({ key: null, data: null, error: null });
  const key = `${JSON.stringify(deps)}#${tick}`;
  const reload = useCallback(() => setTick((t) => t + 1), []);
  const setData = useCallback((data) => setSettled((s) => ({ ...s, data })), []);

  useEffect(() => {
    let cancelled = false;
    fn()
      .then((data) => {
        if (!cancelled) setSettled({ key, data, error: null });
      })
      .catch((e) => {
        if (!cancelled)
          setSettled((s) => ({ key, data: s.data, error: e instanceof Error ? e.message : "Something went wrong." }));
      });
    return () => {
      cancelled = true;
    };
    // `fn` is intentionally not a dependency: callers pass inline closures; `deps` says when to refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return { data: settled.data, error: settled.error, loading: settled.key !== key, reload, setData };
}
