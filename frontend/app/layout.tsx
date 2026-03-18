import type { Metadata } from "next";
import { Geist_Mono } from "next/font/google";
import "./globals.css";

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "lex-diff - 法令改正の差分ビューア",
  description:
    "法律の改正履歴を差分表示で可視化するオープンソースプロジェクト。e-Gov法令APIを利用。",
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
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20,300,0,0&icon_names=add,arrow_forward,calendar_month,change_history,commit,description,difference,family_restroom,folder,gavel,history,lock,open_in_new,schedule,smart_toy,speed,tag,work&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className={`${geistMono.variable} antialiased`}>
        <header className="border-b border-[var(--border)] px-4 py-3">
          <div className="max-w-5xl mx-auto flex items-center gap-3">
            <a href="/" className="text-[17px] font-bold font-mono">
              lex-diff
            </a>
            <span className="text-[13px] opacity-50">
              法令改正の差分ビューア
            </span>
          </div>
        </header>
        <main className="max-w-5xl mx-auto px-4 py-6 md:px-6 md:py-8">
          {children}
        </main>
        <footer className="border-t border-[var(--border)] px-4 py-6 mt-8 md:px-6">
          <div className="max-w-5xl mx-auto">
            <div className="text-[13px] leading-[22px] opacity-50 space-y-2">
              <p>
                出典：
                <a
                  href="https://laws.e-gov.go.jp/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline"
                >
                  e-Gov法令検索
                </a>
                （デジタル庁）。法令データは著作権法第13条により著作権の対象外です。
              </p>
              <p>
                改正の概要・条文の注釈はClaude
                AI（Anthropic社）により自動生成されています。
                誤りや省略が含まれる可能性があります。正確な内容は必ず原文をご確認ください。
              </p>
              <p>
                要約生成のプロンプトを含むすべてのソースコードはGitHubで公開しています。
              </p>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
