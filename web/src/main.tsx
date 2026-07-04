import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  CheckCircle2,
  Copy,
  Download,
  ExternalLink,
  Link2,
  Loader2,
  RotateCcw,
  Smartphone,
  Sparkles,
} from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import "./styles.css";

type DownloadLink = {
  url: string;
  filename: string;
  expires_at: string;
  expires_in_seconds: number;
};

type ConvertResponse = {
  deck: string;
  card_count: number;
  tsv: string;
  tsv_filename: string;
  apkg_filename: string;
  downloads: {
    tsv: DownloadLink | null;
    apkg: DownloadLink | null;
  };
  warnings: string[];
};

type CapabilitiesResponse = {
  apkg_download_links_enabled: boolean;
  link_ttl_seconds: number | null;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function App() {
  const [source, setSource] = useState("");
  const [result, setResult] = useState<ConvertResponse | null>(null);
  const [error, setError] = useState("");
  const [isConverting, setIsConverting] = useState(false);
  const [createDownloadLink, setCreateDownloadLink] = useState(true);
  const [capabilities, setCapabilities] = useState<CapabilitiesResponse | null>(null);
  const [apkgUrlCopied, setApkgUrlCopied] = useState(false);
  const [tsvCopied, setTsvCopied] = useState(false);
  const outputRef = useRef<HTMLElement>(null);

  const canConvert = source.trim().length > 0 && !isConverting;
  const canCreateApkgLink = capabilities?.apkg_download_links_enabled === true;
  const previewLines = useMemo(() => result?.tsv.split("\n").slice(0, 16).join("\n") ?? "", [result]);

  useEffect(() => {
    let cancelled = false;

    async function loadCapabilities() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/capabilities`);
        if (!response.ok) {
          throw new Error("capabilities request failed");
        }
        const data = await response.json();
        if (cancelled) return;
        setCapabilities(data);
        if (!data.apkg_download_links_enabled) {
          setCreateDownloadLink(false);
        }
      } catch {
        if (cancelled) return;
        setCapabilities({ apkg_download_links_enabled: false, link_ttl_seconds: null });
        setCreateDownloadLink(false);
      }
    }

    loadCapabilities();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!result || !outputRef.current) return;
    if (!window.matchMedia("(max-width: 900px)").matches) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    outputRef.current.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
  }, [result]);

  async function convert() {
    if (!canConvert) return;
    setIsConverting(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/convert`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          source,
          create_download_link: createDownloadLink,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail ?? "変換に失敗しました。");
      }
      setResult(data);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "変換に失敗しました。");
    } finally {
      setIsConverting(false);
    }
  }

  function downloadLocal() {
    if (!result) return;
    const blob = new Blob([result.tsv], { type: "text/tab-separated-values;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = result.tsv_filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function copyTsv() {
    if (!result) return;
    await navigator.clipboard.writeText(result.tsv);
    setTsvCopied(true);
    window.setTimeout(() => setTsvCopied(false), 2000);
  }

  async function copyApkgUrl() {
    const url = result?.downloads.apkg?.url;
    if (!url) return;
    await navigator.clipboard.writeText(url);
    setApkgUrlCopied(true);
    window.setTimeout(() => setApkgUrlCopied(false), 2000);
  }

  function reset() {
    setSource("");
    setResult(null);
    setError("");
  }

  return (
    <main className="app-shell">
      <div className="workspace">
        <header className="hero">
          <p className="brand">
            <span className="brand-badge" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="23" height="23" role="img">
                {/* 重ねた暗記カードと、正誤問題の「○」印 */}
                <rect
                  x="6.5"
                  y="4.5"
                  width="12"
                  height="15.5"
                  rx="2.4"
                  transform="rotate(9 12 12)"
                  fill="#ffffff"
                  opacity="0.5"
                />
                <rect
                  x="5.5"
                  y="4"
                  width="12"
                  height="15.5"
                  rx="2.4"
                  transform="rotate(-8 12 12)"
                  fill="#ffffff"
                />
                <circle
                  cx="11.5"
                  cy="11.75"
                  r="3.3"
                  transform="rotate(-8 12 12)"
                  fill="none"
                  stroke="#ec7b2e"
                  strokeWidth="1.8"
                />
              </svg>
            </span>
            Anki Quiz Converter
          </p>
          <h1>
            演習問題を、<mark>Ankiのカード</mark>に。
          </h1>
          <p className="lead">薬理学の演習問題解答を貼り付けるだけで、Ankiにインポートできるデッキを作ります。</p>
          <ol className="steps">
            <li>
              <span className="step-num" aria-hidden="true">1</span>
              解答テキストを貼り付ける
            </li>
            <li>
              <span className="step-num" aria-hidden="true">2</span>
              変換ボタンを押す
            </li>
            <li>
              <span className="step-num" aria-hidden="true">3</span>
              QRコードでスマホのAnkiへ
            </li>
          </ol>
        </header>

        <div className="grid">
          <section className="panel input-panel" aria-labelledby="input-title">
            <div className="panel-head">
              <div>
                <h2 id="input-title">問題テキスト</h2>
                <p>コピーした演習問題解答をそのまま貼り付けます。</p>
              </div>
              <label className="toggle">
                <input
                  checked={createDownloadLink}
                  disabled={!canCreateApkgLink}
                  onChange={(event) => setCreateDownloadLink(event.target.checked)}
                  type="checkbox"
                />
                <span>{canCreateApkgLink ? "APKGリンク作成" : "リンク作成不可"}</span>
              </label>
            </div>

            <textarea
              aria-label="変換元テキスト"
              className="source-textarea"
              onChange={(event) => setSource(event.target.value)}
              placeholder="薬理学Ⅲ(アレルギー疾患治療薬)演習問題解答..."
              value={source}
            />

            {error ? (
              <div className="error-box" role="alert">
                {error}
              </div>
            ) : null}

            <div className="actions">
              <button className="primary-button" disabled={!canConvert} onClick={convert} type="button">
                {isConverting ? (
                  <Loader2 className="spin" size={18} aria-hidden="true" />
                ) : (
                  <Sparkles size={18} aria-hidden="true" />
                )}
                <span>{isConverting ? "変換中…" : "Ankiカードに変換"}</span>
              </button>
              <button
                className="icon-button"
                disabled={!source && !result}
                onClick={reset}
                title="最初からやり直す"
                type="button"
              >
                <RotateCcw size={18} aria-hidden="true" />
              </button>
            </div>
          </section>

          <section className="panel output-panel" aria-labelledby="output-title" ref={outputRef}>
            <div className="panel-head">
              <div>
                <h2 id="output-title">できあがったデッキ</h2>
                <p>TSVは即時ダウンロード、APKGはリンク作成ONで発行されます。</p>
              </div>
            </div>

            {result ? (
              <div className="result-area">
                <div className="result-summary">
                  <CheckCircle2 className="result-check" size={22} aria-hidden="true" />
                  <div>
                    <p className="result-count">
                      <strong>{result.card_count}</strong>枚のカードができました
                    </p>
                    <p className="result-deck">{result.deck}</p>
                  </div>
                </div>

                <div className="output-actions">
                  <button className="secondary-button" onClick={downloadLocal} type="button">
                    <Download size={18} aria-hidden="true" />
                    <span>TSVダウンロード</span>
                  </button>
                  <button className="secondary-button" onClick={copyTsv} type="button">
                    <Copy size={18} aria-hidden="true" />
                    <span>{tsvCopied ? "コピーしました" : "TSVをコピー"}</span>
                  </button>
                  {result.downloads.apkg ? (
                    <a
                      className="secondary-link"
                      href={result.downloads.apkg.url}
                      rel="noreferrer"
                      target="_blank"
                      title="APKGの期限付きリンクを開く"
                    >
                      <ExternalLink size={18} aria-hidden="true" />
                      <span>APKGリンクを開く</span>
                    </a>
                  ) : null}
                </div>

                {result.warnings.map((warning) => (
                  <div className="warning-box" key={warning}>
                    {warning}
                  </div>
                ))}

                {result.downloads.apkg ? (
                  <div className="qr-box">
                    <div className="qr-code">
                      <QRCodeSVG size={148} value={result.downloads.apkg.url} />
                    </div>
                    <div className="qr-help">
                      <p className="qr-title">
                        <Smartphone size={16} aria-hidden="true" />
                        スマホのAnkiに入れる
                      </p>
                      <p>QRコードを読み取るか、URLをコピーしてAnkiアプリに貼り付けてください。</p>
                      <p className="link-meta">
                        {result.downloads.apkg.filename}
                        <br />
                        有効期限: {new Date(result.downloads.apkg.expires_at).toLocaleString("ja-JP")}
                      </p>
                      <button className="secondary-button" onClick={copyApkgUrl} type="button">
                        <Link2 size={18} aria-hidden="true" />
                        <span>{apkgUrlCopied ? "コピーしました" : "URLをコピー"}</span>
                      </button>
                    </div>
                  </div>
                ) : null}

                <pre className="preview" aria-label="TSVプレビュー">
                  {previewLines}
                </pre>
              </div>
            ) : (
              <div className="empty-state">
                <div className="empty-cards" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </div>
                <p className="empty-title">まだカードはありません</p>
                <p className="empty-sub">問題テキストを変換すると、ここにデッキが表示されます。</p>
              </div>
            )}
          </section>
        </div>

        <footer className="privacy">
          入力したテキストは変換処理のためサーバーに送信されます。ダウンロードリンクは有効期限付きです。期限が切れたら、もう一度変換してください。
        </footer>
      </div>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
