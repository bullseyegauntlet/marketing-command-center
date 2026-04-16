"use client";

import { usePathname } from "next/navigation";
import { NavBar } from "@/components/nav-bar";
import { StatsBar } from "@/components/stats-bar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isAuthPage = pathname.startsWith("/sign-in") || pathname.startsWith("/sign-up");

  if (isAuthPage) {
    return <main className="flex-1">{children}</main>;
  }

  return (
    <>
      <NavBar />
      <StatsBar />
      <main className="flex-1 container mx-auto px-6 py-10 max-w-5xl">
        {children}
      </main>
    </>
  );
}
