"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { logout } from "@/lib/auth";
import { Logo } from "./Logo";
import { TriBar } from "./Brand";

const LINKS = {
  buyer: [
    { href: "/buyer", label: "Dashboard" },
    { href: "/buyer/compare", label: "Compare & buy" },
    { href: "/buyer/cart", label: "Cart" },
    { href: "/buyer/orders", label: "Orders" },
  ],
  supplier: [{ href: "/supplier", label: "Dashboard" }],
  admin: [{ href: "/admin", label: "Overview" }],
};

export function AppNav({ user }) {
  const pathname = usePathname();
  const router = useRouter();
  const initials = user.full_name
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  async function handleLogout() {
    await logout();
    router.replace("/login");
  }

  return (
    <header className="bg-paper-raised">
      <TriBar className="h-1" />
      <div className="border-b border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <Link href="/" aria-label="GetbyFarm home">
              <Logo height={34} />
            </Link>
            <nav className="flex items-center gap-1" aria-label="Main">
              {LINKS[user.role].map((l) => (
                <Link
                  key={l.href}
                  href={l.href}
                  className={`rounded px-3 py-1.5 text-sm transition-colors ${
                    pathname === l.href ? "bg-leaf-600 text-white" : "text-ink-soft hover:bg-leaf-50 hover:text-leaf-800"
                  }`}
                >
                  {l.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden text-ink-faint sm:inline">
              {user.supplier?.business_name ?? user.organization?.name ?? "GetbyFarm team"}
            </span>
            <span
              title={user.email}
              className="flex h-8 w-8 items-center justify-center rounded-full bg-ember-600 font-display text-sm font-medium text-white"
            >
              {initials}
            </span>
            <button onClick={handleLogout} className="rounded border border-line px-3 py-1.5 text-ink-soft hover:bg-paper-dim">
              Log out
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
