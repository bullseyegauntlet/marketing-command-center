"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useClerk, useUser } from "@clerk/nextjs";
import { cn } from "@/lib/utils";

const navLinks = [
  { href: "/", label: "Explore" },
  { href: "/docs", label: "Docs" },
];

function UserMenu() {
  const { signOut } = useClerk();
  const { user } = useUser();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, []);

  if (!user) return null;

  return (
    <div ref={ref} className="relative ml-3">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs font-medium text-[rgba(255,255,255,0.4)] hover:text-[rgba(255,255,255,0.7)] hover:bg-[rgba(255,255,255,0.04)] transition-all border border-[#2B2B2B]"
      >
        <img
          src={user.imageUrl}
          alt={user.firstName ?? "User"}
          className="w-4 h-4 rounded-full opacity-70"
        />
        <span>{user.firstName ?? "Account"}</span>
        <svg
          className={cn("w-3 h-3 transition-transform duration-150", open && "rotate-180")}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>

      {open && (
        <div
          className="absolute right-0 mt-1 w-44 bg-[#1a1a1a] border border-[#2B2B2B] shadow-xl shadow-black/40 z-50 py-1"
          style={{ borderRadius: "4px" }}
        >
          <div className="px-3 py-2 border-b border-[#2B2B2B]">
            <p className="text-xs text-[rgba(255,255,255,0.5)] truncate">{user.primaryEmailAddress?.emailAddress}</p>
          </div>
          <button
            onClick={() => {
              setOpen(false);
              signOut({ redirectUrl: "/sign-in" });
            }}
            className="w-full text-left px-3 py-2 text-sm text-[rgba(255,255,255,0.6)] hover:text-white hover:bg-[rgba(255,255,255,0.04)] transition-colors flex items-center gap-2"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

export function NavBar() {
  const pathname = usePathname();

  return (
    <header className="border-b border-[#1e1e1e] bg-[rgba(8,8,8,0.9)] backdrop-blur-md sticky top-0 z-50">
      <div className="container mx-auto px-6 max-w-5xl">
        <div className="flex items-center justify-between h-14">
          <Link href="/" className="flex items-center gap-3">
            <span className="text-[#C09E5A] font-bold text-lg tracking-tight" style={{ fontFamily: "var(--font-space-grotesk), sans-serif" }}>
              MCC
            </span>
            <span className="text-[#2B2B2B]">|</span>
            <span className="text-[10px] text-[rgba(255,255,255,0.3)] tracking-widest uppercase font-medium">
              Gauntlet AI
            </span>
          </Link>

          <div className="flex items-center gap-0.5">
            <nav className="flex items-center gap-0.5">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={cn(
                    "px-4 py-1.5 text-sm font-medium transition-all duration-150 rounded-sm",
                    pathname === link.href
                      ? "text-[#C09E5A] bg-[rgba(192,158,90,0.08)]"
                      : "text-[rgba(255,255,255,0.4)] hover:text-[rgba(255,255,255,0.8)] hover:bg-[rgba(255,255,255,0.04)]"
                  )}
                >
                  {link.label}
                </Link>
              ))}
            </nav>
            <UserMenu />
          </div>
        </div>
      </div>
    </header>
  );
}
