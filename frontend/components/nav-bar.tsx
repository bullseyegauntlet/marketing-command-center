"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useClerk, useUser } from "@clerk/nextjs";
import { cn } from "@/lib/utils";

const navLinks = [
  { href: "/", label: "Explore" },
  { href: "/docs", label: "Docs" },
];

export function NavBar() {
  const pathname = usePathname();
  const { signOut } = useClerk();
  const { user } = useUser();

  return (
    <header className="border-b border-border bg-white/80 backdrop-blur-md sticky top-0 z-50">
      <div className="container mx-auto px-6 max-w-5xl">
        <div className="flex items-center justify-between h-14">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-[#5b6cf8] to-[#8b5cf6] flex items-center justify-center shadow-sm shadow-indigo-200 group-hover:shadow-indigo-300 transition-shadow">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <circle cx="11" cy="11" r="7" stroke="white" strokeWidth="2.5"/>
                <path d="m21 21-4.35-4.35" stroke="white" strokeWidth="2.5" strokeLinecap="round"/>
              </svg>
            </div>
            <div>
              <span className="text-sm font-bold text-foreground tracking-tight leading-none block">
                Marketing Command Center
              </span>
              <span className="text-[10px] text-muted-foreground leading-none">Gauntlet AI</span>
            </div>
          </Link>

          {/* Nav */}
          <div className="flex items-center gap-1">
            <nav className="flex items-center gap-0.5">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={cn(
                    "px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all duration-150",
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
                className="ml-2 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all border border-border"
              >
                <img
                  src={user.imageUrl}
                  alt={user.firstName ?? "User"}
                  className="w-4 h-4 rounded-full"
                />
                <span>{user.firstName ?? "Sign out"}</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
