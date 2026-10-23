"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { getMe } from "@/lib/api";
import { login } from "@/lib/auth";
import { HOME } from "@/components/Session";
import { AuthShell } from "@/components/AuthShell";
import { ErrorNote } from "@/components/ui";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      const me = await getMe();
      const next = params.get("next");
      // Only follow same-site, section-matching redirects (prevents open-redirect abuse).
      const safe = next && next.startsWith(HOME[me.role]) ? next : HOME[me.role];
      router.replace(safe);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not log in.");
      setBusy(false);
    }
  }

  const input = "mt-1 w-full rounded border border-line bg-paper-raised px-3 py-2.5 focus:border-leaf-600";
  return (
    <form onSubmit={submit} className="mt-6 space-y-4">
      {params.get("expired") && (
        <p className="rounded bg-ember-50 px-3 py-2 text-sm text-ember-700">Your session expired. Please log in again.</p>
      )}
      {params.get("registered") && (
        <p className="rounded bg-leaf-50 px-3 py-2 text-sm text-leaf-800">Account created. Log in to continue.</p>
      )}
      <div>
        <label htmlFor="email" className="text-sm text-ink-soft">Email</label>
        <input id="email" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className={input} />
      </div>
      <div>
        <label htmlFor="password" className="text-sm text-ink-soft">Password</label>
        <input id="password" type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} className={input} />
      </div>
      {error && <ErrorNote>{error}</ErrorNote>}
      <button disabled={busy} className="w-full rounded bg-ember-600 py-2.5 font-medium text-white hover:bg-ember-700 disabled:opacity-60">
        {busy ? "Logging in…" : "Log in"}
      </button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <AuthShell
      title="Welcome back"
      footer={<>New to GetbyFarm? <Link href="/register" className="font-medium text-leaf-700 underline">Create an account</Link></>}
    >
      <Suspense fallback={null}>
        <LoginForm />
      </Suspense>
    </AuthShell>
  );
}
