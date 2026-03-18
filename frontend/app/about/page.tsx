import type { Metadata } from "next";
import { Icon } from "@/components/icon";

export const metadata: Metadata = {
  title: "lexdiffについて",
  description:
    "lexdiffの仕組み、コンセプト、AI利用方針について。法令の改正履歴をGitHub風のdiffで可視化するオープンソースプロジェクト。",
};

export default function AboutPage() {
  return (
    <div className="space-y-10">
      {/* Concept */}
      <section>
        <h2 className="text-[20px] font-bold">lexdiffとは</h2>
        <div className="mt-3 space-y-3 text-[15px] leading-[26px] opacity-80">
          <p>
            lexdiffは、日本の法律の改正履歴を
            <strong>GitHub風の差分表示</strong>
            で可視化するオープンソースプロジェクトです。
          </p>
          <p>
            法律が「いつ・どこが・なぜ変わったか」を誰でも直感的に追えるようにすることを目指しています。
            e-Gov法令APIから条文データを取得し、改正前後の構造的な差分を計算して表示します。
          </p>
        </div>
      </section>

      {/* GitHub metaphor */}
      <section>
        <h2 className="text-[20px] font-bold">
          なぜGitHub風なのか
        </h2>
        <div className="mt-3 space-y-3 text-[15px] leading-[26px] opacity-80">
          <p>
            ソフトウェア開発では、コードの変更履歴を差分（diff）で確認することが日常的に行われています。
            「何が追加され、何が削除されたか」が一目でわかるこの仕組みは、実は法律の改正にもそのまま当てはまります。
          </p>
          <p>
            lexdiffでは、この考え方を法令に適用しています：
          </p>
        </div>
        <div className="mt-4 border border-[var(--border)] rounded-lg overflow-hidden text-[14px]">
          {[
            {
              git: "リポジトリ",
              law: "一つの法律",
              example: "民法、道路交通法",
            },
            {
              git: "コミット",
              law: "一つの改正法律",
              example: "令和4年法律第102号",
            },
            {
              git: "コミットメッセージ",
              law: "改正理由・趣旨",
              example: "共同親権制度の導入",
            },
            {
              git: "Author",
              law: "提出者・所管大臣",
              example: "小泉龍司（法務大臣）",
            },
            {
              git: "diff（差分）",
              law: "条文の新旧対照",
              example: "+/- で変更箇所を表示",
            },
            {
              git: "コミット履歴",
              law: "改正履歴タイムライン",
              example: "法律の変遷を時系列で一覧",
            },
          ].map(({ git, law, example }, i) => (
            <div
              key={git}
              className={`flex items-center px-4 py-3 ${
                i > 0 ? "border-t border-[var(--border)]" : ""
              }`}
            >
              <span className="w-1/3 font-mono opacity-60">{git}</span>
              <span className="w-1/3 font-medium">{law}</span>
              <span className="w-1/3 text-[13px] opacity-50">{example}</span>
            </div>
          ))}
        </div>

        {/* Key insight: amendment = law */}
        <div className="mt-5 rounded-lg border border-[var(--diff-hunk-text)]/20 bg-[var(--diff-hunk-bg)] p-4 text-[14px] leading-[24px]">
          <p className="font-bold text-[var(--diff-hunk-text)] mb-2">
            改正履歴に「法律」が並ぶのはなぜ？
          </p>
          <p>
            日本の法律を改正するには、<strong>改正するための新しい法律</strong>（改正法）が必要です。
            たとえば民法を変えたいときは、「民法等の一部を改正する法律」という別の法律案を国会に提出し、審議・可決する必要があります。
          </p>
          <p className="mt-2">
            つまり、lexdiffの改正履歴に並んでいる一つ一つの項目は、それ自体が<strong>独立した法律</strong>です。
            GitHubでいえば、コミットメッセージどころか<strong>コミットそのものが一つの法律文書</strong>になっている — それが日本の法改正の仕組みです。
          </p>
        </div>
      </section>

      {/* How it works */}
      <section>
        <h2 className="text-[20px] font-bold">仕組み</h2>
        <div className="mt-3 space-y-4 text-[15px] leading-[26px] opacity-80">
          <p>
            <span className="font-bold opacity-100">
              1. 法令データの取得
            </span>
            <br />
            e-Gov法令API（Version
            2）から、任意の時点における法令の条文を取得します。
            このAPIはデジタル庁が提供しており、認証不要で利用できます。
          </p>
          <p>
            <span className="font-bold opacity-100">
              2. 構造的な差分の計算
            </span>
            <br />
            改正前後の条文をXML構造（条・項・号）のレベルで比較し、
            追加・変更・削除された条文を特定します。
          </p>
          <p>
            <span className="font-bold opacity-100">
              3. AIによる注釈の生成
            </span>
            <br />
            Claude（Anthropic社）を使用して、改正の概要と各条文の変更内容をわかりやすく要約します。
            要約プロンプトはすべてオープンソースで公開しています。
          </p>
        </div>
      </section>

      {/* AI Disclaimer */}
      <section>
        <h2 className="text-[20px] font-bold">AI利用に関する注意事項</h2>
        <div className="mt-3 space-y-3 rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-4 text-[14px] leading-[24px]">
          <p>
            <span className="font-bold text-yellow-500">
              改正の概要・条文の注釈はAIが生成しています。
            </span>
            すべての要約はClaude
            AI（Anthropic社）によって事前に生成されたものです。
            原文の意図を正確に反映することを目指していますが、誤りや省略が含まれる可能性があります。
          </p>
          <p>
            <span className="font-bold text-yellow-500">
              条文の差分（diff）はプログラムによる機械的な比較です。
            </span>
            diff自体にはAIは関与しておらず、e-Gov
            APIから取得した法令データを構造的に比較した結果です。
          </p>
          <p>
            <span className="font-bold text-yellow-500">
              提出者・大臣名は法案提出当時の役職です。
            </span>
            改正履歴に表示される大臣名や役職は、その法案が国会に提出された時点のものです。
            現在の役職とは異なる場合があります。情報はNDL国会会議録から自動抽出しています。
          </p>
          <p>
            <span className="font-bold text-yellow-500">
              正確な内容は必ず原文でご確認ください。
            </span>
            各ページにはe-Gov法令検索への原文リンクを掲載しています。
            重要な判断の根拠にする場合は、必ず原文をご参照ください。
          </p>
        </div>
      </section>

      {/* Data Source */}
      <section>
        <h2 className="text-[20px] font-bold">データソース</h2>
        <div className="mt-3 rounded-lg border border-[var(--border)] p-4">
          <div className="flex items-center justify-between">
            <a
              href="https://laws.e-gov.go.jp/apitop/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[15px] font-bold text-[var(--diff-hunk-text)] hover:underline"
            >
              e-Gov法令API（Version 2）
              <Icon name="open_in_new" size={14} className="ml-1" />
            </a>
            <span className="rounded-full bg-green-500/10 px-2 py-0.5 text-[12px] font-medium text-green-600">
              稼働中
            </span>
          </div>
          <p className="mt-1 text-[13px] opacity-60">
            デジタル庁 —
            法令の条文データを構造化されたJSON形式で提供。時点指定による過去の条文取得に対応。
          </p>
        </div>
        <p className="mt-3 text-[14px] leading-[24px] opacity-70">
          法令データは著作権法第13条により著作権の対象外です。
          AI生成コンテンツは「Claude AI（Anthropic社）による要約」として明示しています。
        </p>
      </section>

      {/* FAQ */}
      <section>
        <h2 className="text-[20px] font-bold">よくある質問</h2>
        <div className="mt-3 space-y-5">
          {[
            {
              q: "AI要約は正確ですか？",
              a: "AIによる要約のため、誤りや省略が含まれる可能性があります。重要な判断の根拠にする場合は、必ずe-Gov法令検索の原文をご確認ください。各ページには原文へのリンクがあります。",
            },
            {
              q: "差分（diff）はどのように計算していますか？",
              a: "e-Gov法令APIから改正前後の法令データを取得し、条・項・号のレベルで構造的に比較しています。テキストの単純な文字比較ではなく、法令XMLの構造を理解した差分計算を行っています。",
            },
            {
              q: "すべての法律に対応していますか？",
              a: "e-Gov法令APIで公開されているすべての法律が対象です。現在はデモとして主要な法律を掲載していますが、今後対象を拡大していく予定です。",
            },
            {
              q: "OpenGIKAIとの関係は？",
              a: "lexdiffは独立したプロジェクトですが、同じ開発者による姉妹プロジェクトです。OpenGIKAIは国会審議・首相記者会見・政府審議会などの公的な議論の内容を、lexdiffは法律の条文変更をそれぞれ可視化しています。将来的には相互リンクによる連携を予定しています。",
            },
            {
              q: "ソースコードはどこで見られますか？",
              a: "GitHubで全ソースコードを公開しています。データ取得・差分計算スクリプト、AI要約プロンプト、フロントエンドのすべてが含まれます。",
            },
          ].map(({ q, a }) => (
            <div key={q}>
              <div className="text-[15px] font-bold">{q}</div>
              <p className="mt-1 text-[14px] leading-[24px] opacity-70">
                {a}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* OSS & Transparency */}
      <section>
        <h2 className="text-[20px] font-bold">オープンソース・透明性</h2>
        <div className="mt-3 space-y-3 text-[15px] leading-[26px] opacity-80">
          <p>
            lexdiffは公共財として運営されています。以下をすべてGitHubで公開しています：
          </p>
          <ul className="list-inside list-disc space-y-1 pl-2">
            <li>e-Gov APIからのデータ取得ロジック</li>
            <li>条文の構造的差分計算アルゴリズム</li>
            <li>AI要約生成のプロンプト全文</li>
            <li>フロントエンドのソースコード</li>
          </ul>
          <p className="mt-2">
            <a
              href="https://github.com/wharfe/lex-diff"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--diff-hunk-text)] hover:underline"
            >
              GitHub: wharfe/lex-diff
              <Icon name="open_in_new" size={14} className="ml-1" />
            </a>
          </p>
        </div>
      </section>

      {/* Related Projects */}
      <section>
        <h2 className="text-[20px] font-bold">関連プロジェクト</h2>
        <div className="mt-3">
          <a
            href="https://open-gikai.vercel.app"
            target="_blank"
            rel="noopener noreferrer"
            className="block rounded-lg border border-[var(--border)] p-4 hover:bg-[var(--muted)] transition-colors"
          >
            <div className="text-[15px] font-bold">
              OpenGIKAI
              <Icon
                name="open_in_new"
                size={14}
                className="ml-1 opacity-50"
              />
            </div>
            <p className="mt-1 text-[14px] leading-[22px] opacity-60">
              国会審議・首相記者会見・政府審議会などの公的な議論をスレッド形式で再構築するオープンソースの公共メディア。
              lexdiffが「法律の条文がどう変わったか」を見せるのに対し、
              OpenGIKAIは「その法律がどう議論されたか」を見せます。
            </p>
          </a>
        </div>
      </section>

      {/* License */}
      <section className="pb-10">
        <h2 className="text-[20px] font-bold">ライセンス</h2>
        <p className="mt-3 text-[15px] leading-[26px] opacity-80">
          ソースコードはMITライセンスで公開しています。
          法令データは著作権法第13条により著作権の対象外です。
          AI生成要約は「Claude AIによる要約」として明示しています。
        </p>
      </section>
    </div>
  );
}
