import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sentinel — AI GRC Auditor",
  description: "Autonomous AI Governance, Risk and Compliance Auditor",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-surface min-h-screen font-sans antialiased">
        <nav className="bg-brand-primary text-white px-6 py-3 flex items-center justify-between shadow-md">
          <a href="/" className="flex items-center gap-2 font-bold text-lg tracking-tight">
            <span className="text-2xl">🛡</span>
            <span>SENTINEL</span>
            <span className="text-xs font-normal text-blue-300 ml-1">AI GRC Auditor</span>
          </a>
          <div className="flex items-center gap-6 text-sm">
            <a href="/history" className="text-blue-200 hover:text-white transition-colors">Audit History</a>
            <a
              href="https://github.com/your-org/sentinel"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-200 hover:text-white transition-colors"
            >
              GitHub
            </a>
          </div>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  );
}
