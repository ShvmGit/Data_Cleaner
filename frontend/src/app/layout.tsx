import type { Metadata } from "next";
import { Toaster } from "sonner";
import "./globals.css";

export const metadata: Metadata = {
  title: "DataCleaner AI — Intelligent Data Cleaning & EDA",
  description: "AI-powered automated data cleaning and exploratory data analysis for CSV, TXT, and Excel files. Clean your data in seconds.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen animated-gradient antialiased">
        {/* Header */}
        <header className="fixed top-0 left-0 right-0 z-50 border-b border-[var(--border-subtle)]" style={{ background: "rgba(10,14,26,0.8)", backdropFilter: "blur(20px)" }}>
          <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl flex items-center justify-center text-lg" style={{ background: "var(--gradient-primary)" }}>
                ✨
              </div>
              <div>
                <h1 className="text-lg font-bold gradient-text">DataCleaner AI</h1>
              </div>
            </div>
            <div className="flex items-center gap-4 text-sm text-[var(--text-muted)]">
              <span className="badge badge-emerald">
                <span className="pulse-dot mr-2" />
                Online
              </span>
              <span>v1.0</span>
            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="pt-20 pb-10 px-6 max-w-7xl mx-auto">
          {children}
        </main>

        <Toaster
          theme="dark"
          position="bottom-right"
          toastOptions={{
            style: {
              background: "var(--bg-card)",
              border: "1px solid var(--border-subtle)",
              color: "var(--text-primary)",
            },
          }}
        />
      </body>
    </html>
  );
}
