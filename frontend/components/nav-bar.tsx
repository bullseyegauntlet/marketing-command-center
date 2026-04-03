"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useClerk, useUser } from "@clerk/nextjs";
import { cn } from "@/lib/utils";

const navLinks = [
  { href: "/", label: "Query" },
  { href: "/history", label: "History" },
];

export function NavBar() {
  const pathname = usePathname();
  const { signOut } = useClerk();
  const { user } = useUser();

  return (
    <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
      <div className="container mx-auto px-4 max-w-7xl">
        <div className="flex items-center justify-between h-14">
          {/* Logo */}
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded bg-primary flex items-center justify-center">
              <span className="text-primary-foreground text-xs font-bold font-mono">MCC</span>
            </div>
            <span className="text-sm font-semibold tracking-wide text-foreground">
              Marketing Command Center
            </span>
            <span className="text-xs text-muted-foreground font-mono hidden sm:block">
              gauntletai.com
            </span>
          </div>

          {/* Nav */}
          <div className="flex items-center gap-2">
            <nav className="flex items-center gap-1">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={cn(
                    "px-3 py-1.5 rounded text-sm font-medium transition-colors",
                    pathname === link.href
                      ? "bg-primary/10 text-primary border border-primary/20"
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
                className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors border border-border"
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
