import type { Metadata } from "next";
import { Geist_Mono } from "next/font/google";
import "./globals.css";

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "lexdiff - 法令改正の差分ビューア",
    template: "%s | lexdiff",
  },
  description:
    "法律の改正履歴をGitHub風の差分表示で可視化。いつ・どの条文が・誰によって・どう変わったかを一目で追えるオープンソースプロジェクト。",
  metadataBase: new URL("https://lexdiff.com"),
  openGraph: {
    title: "lexdiff - 法令改正の差分ビューア",
    description:
      "法律の改正履歴をGitHub風の差分表示で可視化。いつ・どの条文が・誰によって・どう変わったかを一目で追えます。",
    url: "https://lexdiff.com",
    siteName: "lexdiff",
    locale: "ja_JP",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "lexdiff - 法令改正の差分ビューア",
    description:
      "法律の改正履歴をGitHub風の差分表示で可視化。",
  },
  alternates: {
    canonical: "https://lexdiff.com",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin=""
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&display=swap"
          rel="stylesheet"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20,300,0,0&icon_names=add,arrow_forward,calendar_month,change_history,code,commit,description,difference,family_restroom,folder,gavel,help,history,info,lock,open_in_new,schedule,smart_toy,speed,tag,work&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className={`${geistMono.variable} antialiased`}>
        <header className="border-b border-[var(--border)] px-4 py-3">
          <div className="max-w-5xl mx-auto flex items-center gap-3">
            <a href="/" className="text-[17px] font-bold font-mono">
              <span className="text-[var(--diff-add-text)]">lex</span><span className="text-[var(--diff-del-text)]">diff</span>
            </a>
            <span className="text-[13px] opacity-50 hidden md:inline">
              法令改正の差分ビューア
            </span>
            <nav className="ml-auto flex items-center gap-1">
              <a
                href="/about"
                className="px-3 py-1.5 text-[13px] opacity-60 hover:opacity-100 transition-opacity rounded-md hover:bg-[var(--muted)]"
              >
                About
              </a>
              <a
                href="https://github.com/wharfe/lex-diff"
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-1.5 text-[13px] opacity-60 hover:opacity-100 transition-opacity rounded-md hover:bg-[var(--muted)]"
              >
                GitHub
              </a>
            </nav>
          </div>
        </header>
        <main className="max-w-5xl mx-auto px-4 py-6 md:px-6 md:py-8">
          {children}
        </main>
        <footer className="border-t border-[var(--border)] px-4 py-5 mt-8 md:px-6">
          <div className="max-w-5xl mx-auto flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] opacity-40">
            <span>
              出典：
              <a
                href="https://laws.e-gov.go.jp/"
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                e-Gov法令検索
              </a>
            </span>
            <span>AI要約：Claude（Anthropic社）</span>
            <a href="/about" className="underline">
              AI利用方針・注意事項
            </a>
          </div>
        </footer>
      </body>
    </html>
  );
}
