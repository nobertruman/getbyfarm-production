"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { register } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { AuthShell } from "@/components/AuthShell";
import { ErrorNote } from "@/components/ui";

function RegisterForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [type, setType] = useState(params.get("type") === "supplier" ? "supplier" : "buyer");
  const [f, setF] = useState({ full_name: "", email: "", phone: "", password: "", business_name: "", branch_name: "", operating_location: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const body = { account_type: type, ...f };
      Object.keys(body).forEach((k) => body[k] === "" && delete body[k]);
      await register(body);
      router.replace("/login?registered=1");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create your account.");
      setBusy(false);
    }
  }

  const input = "mt-1 w-full rounded border border-line bg-paper-raised px-3 py-2.5 focus:border-leaf-600";
  return (
    <form onSubmit={submit} className="mt-6 space-y-4">
      <div className="grid grid-cols-2 gap-1 rounded border border-line bg-paper-raised p-1" role="tablist">
        {["buyer", "supplier"].map((t) => (
          <button
            type="button"
            key={t}
            role="tab"
            aria-selected={type === t}
            onClick={() => setType(t)}
            className={`rounded py-2 text-sm font-medium ${type === t ? "bg-leaf-600 text-white" : "text-ink-soft hover:bg-leaf-50"}`}
          >
            {t === "buyer" ? "I buy for a business" : "I supply products"}
          </button>
        ))}
      </div>
      <div>
        <label className="text-sm text-ink-soft" htmlFor="business">{type === "buyer" ? "Business name" : "Supplier / company name"}</label>
        <input id="business" required value={f.business_name} onChange={set("business_name")} className={input} />
      </div>
      {type === "buyer" && (
        <div>
          <label className="text-sm text-ink-soft" htmlFor="branch">First branch (optional)</label>
          <input id="branch" placeholder="e.g. Nairobi CBD" value={f.branch_name} onChange={set("branch_name")} className={input} />
        </div>
      )}
      <div>
        <label className="text-sm text-ink-soft" htmlFor="loc">{type === "buyer" ? "Delivery address" : "Where you operate"}</label>
        <input id="loc" required value={f.operating_location} onChange={set("operating_location")} className={input} />
      </div>
      <div>
        <label className="text-sm text-ink-soft" htmlFor="name">Your full name</label>
        <input id="name" required autoComplete="name" value={f.full_name} onChange={set("full_name")} className={input} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="text-sm text-ink-soft" htmlFor="email">Email</label>
          <input id="email" type="email" required autoComplete="email" value={f.email} onChange={set("email")} className={input} />
        </div>
        <div>
          <label className="text-sm text-ink-soft" htmlFor="phone">Phone (optional)</label>
          <input id="phone" type="tel" autoComplete="tel" placeholder="0712 345 678" value={f.phone} onChange={set("phone")} className={input} />
        </div>
      </div>
      <div>
        <label className="text-sm text-ink-soft" htmlFor="pw">Password</label>
        <input id="pw" type="password" required minLength={10} autoComplete="new-password" value={f.password} onChange={set("password")} className={input} />
        <p className="mt-1 text-xs text-ink-faint">At least 10 characters; avoid common passwords.</p>
      </div>
      {type === "supplier" && (
        <p className="rounded bg-ember-50 px-3 py-2 text-sm text-ember-700">
          New suppliers are reviewed by the GetbyFarm team before they appear to buyers. You can add your products while you wait.
        </p>
      )}
      {error && <ErrorNote>{error}</ErrorNote>}
      <button disabled={busy} className="w-full rounded bg-ember-600 py-2.5 font-medium text-white hover:bg-ember-700 disabled:opacity-60">
        {busy ? "Creating account…" : "Create account"}
      </button>
    </form>
  );
}

export default function RegisterPage() {
  return (
    <AuthShell
      title="Create your account"
      footer={<>Already registered? <Link href="/login" className="font-medium text-leaf-700 underline">Log in</Link></>}
    >
      <Suspense fallback={null}>
        <RegisterForm />
      </Suspense>
    </AuthShell>
  );
}
