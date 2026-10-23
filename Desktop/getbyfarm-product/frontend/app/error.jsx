"use client";

import { Logo } from "@/components/Logo";
import { TriBar } from "@/components/Brand";

export default function GlobalError({ reset }) {
  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <TriBar className="h-1.5" />
      <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
        <Logo variant="full" height={72} />
        <h1 className="mt-10 font-display text-display-md font-medium">Something went wrong.</h1>
        <p className="mt-2 text-ink-soft">It's on our side. Please try again.</p>
        <button onClick={reset} className="mt-6 rounded bg-ember-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-ember-700">Try again</button>
      </div>
    </div>
  );
}
