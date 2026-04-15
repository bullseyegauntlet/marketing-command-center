"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useClerk, useUser } from "@clerk/nextjs";
import { cn } from "@/lib/utils";

const navLinks = [
  { href: "/", label: "Search" },
  { href: "/history", label: "History" },
  { href: "/docs", label: "Docs" },
];

export function NavBar() {
  const pathname = usePathname();
  const { signOut } = useClerk();
  const { user } = useUser();

  return (
    <header className="border-b border-border bg-white sticky top-0 z-50 shadow-sm">
      <div className="container mx-auto px-6 max-w-4xl">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#1a73e8] to-[#0d47a1] flex items-center justify-center shadow-md shadow-blue-200">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <circle cx="11" cy="11" r="7" stroke="white" strokeWidth="2.2"/>
                <path d="m21 21-4.35-4.35" stroke="white" strokeWidth="2.2" strokeLinecap="round"/>
              </svg>
            </div>
            <div>
              <span className="text-base font-bold text-foreground tracking-tight leading-none block">Marketing Command Center</span>
              <span className="text-[11px] text-muted-foreground leading-none">Gauntlet AI</span>
            </div>
          </div>

          {/* Nav */}
          <div className="flex items-center gap-2">
            <nav className="flex items-center gap-1">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={cn(
                    "px-4 py-2 rounded-full text-sm font-medium transition-colors",
                    pathname === link.href
                      ? "bg-accent text-primary"
                      : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                  )}
                >
                  {link.label}
                </Link>
              ))}
            </nav>
            {user && (
              <button
                onClick={() => signOut({ redirectUrl: "/sign-in" })}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors border border-border"
              >
                <img
                  src={user.imageUrl}
                  alt={user.firstName ?? "User"}
                  className="w-4 h-4 rounded-full"
                />
                Sign out
              </button>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
