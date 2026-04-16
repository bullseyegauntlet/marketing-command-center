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
    <header className="border-b border-border bg-[rgba(8,8,8,0.85)] backdrop-blur-md sticky top-0 z-50">
      <div className="container mx-auto px-6 max-w-5xl">
        <div className="flex items-center justify-between h-14">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-3 group">
            <div className="flex items-center gap-2">
              <span className="text-[#C09E5A] font-bold text-lg tracking-tight" style={{ fontFamily: "var(--font-space-grotesk), sans-serif" }}>
                MCC
              </span>
              <span className="text-[#2B2B2B]">|</span>
              <span className="text-xs text-[rgba(255,255,255,0.4)] tracking-widest uppercase font-medium">
                Gauntlet AI
              </span>
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
                    "px-4 py-1.5 text-sm font-medium transition-all duration-150 rounded-sm",
                    pathname === link.href
                      ? "text-[#C09E5A] bg-[rgba(192,158,90,0.08)]"
                      : "text-[rgba(255,255,255,0.5)] hover:text-[rgba(255,255,255,0.9)] hover:bg-[rgba(255,255,255,0.04)]"
                  )}
                >
                  {link.label}
                </Link>
              ))}
            </nav>

            {user && (
              <button
                onClick={() => signOut({ redirectUrl: "/sign-in" })}
                className="ml-3 flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs font-medium text-[rgba(255,255,255,0.4)] hover:text-[rgba(255,255,255,0.7)] hover:bg-[rgba(255,255,255,0.04)] transition-all border border-[#2B2B2B]"
              >
                <img
                  src={user.imageUrl}
                  alt={user.firstName ?? "User"}
                  className="w-4 h-4 rounded-full opacity-70"
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
