import Link from "next/link";
import { Logo } from "@/components/Logo";
import { TriBar } from "@/components/Brand";
import { BRAND } from "@/lib/brand";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <TriBar className="h-1.5" />
      <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
        <Logo variant="full" height={72} />
        <p className="num mt-10 text-6xl font-medium text-ember-500">404</p>
        <h1 className="mt-2 font-display text-display-md font-medium">We couldn't find that page.</h1>
        <p className="mt-2 font-script text-2xl text-ember-700">{BRAND.tagline}, though, is always in season.</p>
        <Link href="/" className="mt-8 rounded bg-ember-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-ember-700">Back to GetbyFarm</Link>
      </div>
    </div>
  );
}
