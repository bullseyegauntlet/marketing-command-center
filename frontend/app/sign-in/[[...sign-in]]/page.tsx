"use client";

import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#080808]">
      {/* Minimal branding */}
      <div className="flex flex-col items-center gap-8">
        <div className="text-center">
          <p className="text-[10px] font-semibold text-[#C09E5A] tracking-widest uppercase mb-2">
            Gauntlet AI
          </p>
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: "var(--font-space-grotesk), sans-serif", letterSpacing: "-0.02em" }}>
            Marketing Command Center
          </h1>
        </div>
        <SignIn />
      </div>
    </div>
  );
}
