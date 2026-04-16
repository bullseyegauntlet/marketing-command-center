"use client";

import { SignIn } from "@clerk/nextjs";
import { dark } from "@clerk/themes";

export default function SignInPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#080808]">
      <div className="flex flex-col items-center gap-8">
        <div className="text-center">
          <p className="text-[10px] font-semibold text-[#C09E5A] tracking-widest uppercase mb-2">
            Gauntlet AI
          </p>
          <h1
            className="text-2xl font-bold text-white"
            style={{ fontFamily: "var(--font-space-grotesk), sans-serif", letterSpacing: "-0.02em" }}
          >
            Marketing Command Center
          </h1>
        </div>

        <SignIn
          appearance={{
            baseTheme: dark,
            layout: {
              socialButtonsVariant: "blockButton",
              socialButtonsPlacement: "top",
            },
            variables: {
              colorBackground: "#121212",
              colorInputBackground: "#1a1a1a",
              colorInputText: "#ffffff",
              colorText: "#ffffff",
              colorTextSecondary: "rgba(255,255,255,0.55)",
              colorTextOnPrimaryBackground: "#080808",
              colorPrimary: "#C09E5A",
              colorNeutral: "#ffffff",
              colorDanger: "#e84646",
              borderRadius: "4px",
              fontFamily: "var(--font-geist-sans), system-ui, sans-serif",
            },
            elements: {
              card: "bg-[#121212] border border-[#2B2B2B] shadow-2xl shadow-black/60",
              headerTitle: "!text-white font-bold",
              headerSubtitle: "!text-[rgba(255,255,255,0.5)]",
              bodyText: "!text-white",
              formButtonPrimary: "bg-[#C09E5A] hover:bg-[#B8914F] !text-[#080808] font-semibold",
              formFieldInput: "bg-[#1a1a1a] border-[#2B2B2B] !text-white focus:border-[#C09E5A]",
              formFieldLabel: "!text-[rgba(255,255,255,0.6)] text-xs",
              formFieldInputShowPasswordButton: "!text-[rgba(255,255,255,0.5)]",
              dividerLine: "bg-[#2B2B2B]",
              dividerText: "!text-[rgba(255,255,255,0.35)]",
              footerActionText: "!text-[rgba(255,255,255,0.5)]",
              footerActionLink: "!text-[#C09E5A] hover:!text-[#D4B575]",
              identityPreviewText: "!text-[rgba(255,255,255,0.7)]",
              identityPreviewEditButton: "!text-[#C09E5A]",
              alternativeMethodsBlockButton: "!text-white border-[#2B2B2B] hover:bg-[rgba(255,255,255,0.04)]",
              socialButtonsBlockButton: "border-[#2B2B2B] !text-white hover:bg-[rgba(255,255,255,0.04)]",
              socialButtonsBlockButtonText: "!text-white",
              // Hide email/password fields — Google OAuth only
              dividerRow: "hidden",
              formFieldRow__identifier: "hidden",
              formFieldRow__password: "hidden",
              formButtonPrimary__signIn: "hidden",
              footerAction: "hidden",
            },
          }}
        />
      </div>
    </div>
  );
}
