"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getMe } from "@/lib/api";
import { clearTokens, isLoggedIn } from "@/lib/auth";
import { AppNav } from "./AppNav";

const UserContext = createContext(null);
export const useUser = () => {
  const u = useContext(UserContext);
  if (!u) throw new Error("useUser must be used inside <RoleLayout>");
  return u;
};

export const HOME = { buyer: "/buyer", supplier: "/supplier", admin: "/admin" };

/** Guards a whole section: must be logged in AND hold the right role, otherwise redirect. */
export function RoleLayout({ role, children }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState(null);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }
    getMe()
      .then((me) => (me.role === role ? setUser(me) : router.replace(HOME[me.role])))
      .catch(() => {
        clearTokens();
        router.replace("/login");
      });
  }, [role, router, pathname]);

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper text-sm text-ink-faint">Loading…</div>
    );
  }
  return (
    <UserContext.Provider value={user}>
      <div className="min-h-screen bg-paper">
        <AppNav user={user} />
        <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">{children}</main>
      </div>
    </UserContext.Provider>
  );
}
