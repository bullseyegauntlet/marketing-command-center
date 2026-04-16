import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sign in — MCC",
};

// This layout intentionally renders children without the root NavBar/StatsBar.
// Next.js App Router applies layouts from outermost to innermost — this nested
// layout file doesn't override the root layout, but we handle that by making
// the root layout conditionally render chrome via a client wrapper.
export default function SignInLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
