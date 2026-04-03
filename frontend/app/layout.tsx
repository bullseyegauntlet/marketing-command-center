import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";
import { StatsBar } from "@/components/stats-bar";
import { NavBar } from "@/components/nav-bar";
import { ClerkProvider } from "@clerk/nextjs";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "MCC — Marketing Command Center",
  description: "Gauntlet AI marketing intelligence dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body className={`${geistSans.variable} antialiased min-h-screen bg-background`}>
          <div className="flex flex-col min-h-screen">
            <NavBar />
            <StatsBar />
            <main className="flex-1 container mx-auto px-6 py-8 max-w-4xl">
              {children}
            </main>
          </div>
        </body>
      </html>
    </ClerkProvider>
  );
}
