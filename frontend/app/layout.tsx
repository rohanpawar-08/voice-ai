import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Voice & Support Copilot - Real-Time Dashboard",
  description: "Phase 1: Real-Time Multimodal Voice & Support Copilot WebSocket Dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen bg-[#090d16] text-slate-100 selection:bg-cyan-500/30">
        {children}
      </body>
    </html>
  );
}
