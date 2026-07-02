import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Copy,
  Download,
  ExternalLink,
  FileText,
  Gauge,
  Link2,
  Loader2,
  QrCode,
  RotateCcw,
  Send,
  ShieldCheck,
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

  const canConvert = source.trim().length > 0 && !isConverting;
  const canCreateApkgLink = capabilities?.apkg_download_links_enabled === true;
  const previewLines = useMemo(() => result?.tsv.split("\n").slice(0, 18).join("\n") ?? "", [result]);
  const sourceStats = useMemo(() => {
    const trimmed = source.trim();
    return {
      chars: source.length,
      lines: trimmed ? trimmed.split(/\r?\n/).length : 0,
    };
  }, [source]);
  const modeLabel = createDownloadLink && canCreateApkgLink ? "TSV + APKG" : "TSV";
  const linkStatus = capabilities === null ? "確認中" : canCreateApkgLink ? "APKG link ready" : "TSV only";

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
      <section className="top-strip" aria-label="変換概要">
        <div className="brand-lockup">
          <span className="brand-mark">AQ</span>
          <div>
            <p>Anki Quiz Converter</p>
            <h1>問題文から、すぐ使える暗記カードへ。</h1>
          </div>
        </div>
        <div className="status-cluster">
          <span>{modeLabel}</span>
          <span>{linkStatus}</span>
          <span>{result ? `${result.card_count} cards` : `${sourceStats.lines} lines`}</span>
        </div>
      </section>

      <section className="hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">Paste. Convert. Import.</p>
          <h2>NotebookLMの出力をAnki形式へ整える専用スタジオ</h2>
        </div>
        <div className="flow-meter" aria-hidden="true">
          <span className="flow-dot is-on">Input</span>
          <ArrowRight size={18} />
          <span className={`flow-dot ${isConverting ? "is-on" : ""}`}>Parse</span>
          <ArrowRight size={18} />
          <span className={`flow-dot ${result ? "is-on" : ""}`}>Export</span>
        </div>
      </section>

      <section className="workspace-grid">
        <section className="editor-stage" aria-labelledby="input-title">
          <div className="stage-toolbar">
            <div>
              <p className="stage-label">Source</p>
              <h3 id="input-title">変換元テキスト</h3>
            </div>
            <label className="link-switch">
              <input
                checked={createDownloadLink}
                disabled={!canCreateApkgLink}
                onChange={(event) => setCreateDownloadLink(event.target.checked)}
                type="checkbox"
              />
              <span>{canCreateApkgLink ? "APKGリンクを作成" : "リンク作成不可"}</span>
            </label>
          </div>

          <textarea
            aria-label="変換元テキスト"
            className="source-textarea"
            onChange={(event) => setSource(event.target.value)}
            placeholder="薬理学Ⅲ（アレルギー疾患治療薬）演習問題解答..."
            value={source}
          />

          <div className="editor-footer">
            <span>{sourceStats.chars.toLocaleString("ja-JP")} chars</span>
            <span>{sourceStats.lines.toLocaleString("ja-JP")} lines</span>
            <span>{canConvert ? "Ready" : "Waiting"}</span>
          </div>

          {error ? (
            <div className="error-box" role="alert">
              <AlertTriangle size={18} aria-hidden="true" />
              <span>{error}</span>
            </div>
          ) : null}
        </section>

        <aside className="output-stage" aria-labelledby="output-title">
          <div className="result-card lead-result">
            <div className="result-head">
              <div>
                <p className="stage-label">Result</p>
                <h3 id="output-title">{result?.deck ?? "まだ変換していません"}</h3>
              </div>
              <Gauge size={22} aria-hidden="true" />
            </div>
            <div className="big-count">
              <strong>{result?.card_count ?? 0}</strong>
              <span>cards</span>
            </div>
          </div>

          <div className="action-row">
            <button className="export-button" disabled={!result} onClick={downloadLocal} type="button">
              <Download size={18} aria-hidden="true" />
              <span>TSV</span>
            </button>
            <button className="export-button" disabled={!result} onClick={copyTsv} type="button">
              <Copy size={18} aria-hidden="true" />
              <span>Copy</span>
            </button>
            <a
              aria-disabled={!result?.downloads.apkg}
              className={`export-link ${result?.downloads.apkg ? "" : "disabled"}`}
              href={result?.downloads.apkg?.url ?? "#"}
              rel="noreferrer"
              target="_blank"
              title={result?.downloads.apkg ? "APKGの期限付きリンクを開く" : "APKGリンク作成がOFFです"}
            >
              <ExternalLink size={18} aria-hidden="true" />
              <span>APKG</span>
            </a>
          </div>

          {result?.warnings.map((warning) => (
            <div className="warning-box" key={warning}>
              <AlertTriangle size={16} aria-hidden="true" />
              <span>{warning}</span>
            </div>
          ))}

          {result?.downloads.apkg ? (
            <div className="qr-card">
              <QRCodeSVG size={118} value={result.downloads.apkg.url} />
              <div>
                <p className="qr-title">
                  <QrCode size={16} aria-hidden="true" />
                  {result.downloads.apkg.filename}
                </p>
                <p className="qr-expire">有効期限: {new Date(result.downloads.apkg.expires_at).toLocaleString("ja-JP")}</p>
                <button className="inline-button" onClick={copyApkgUrl} type="button">
                  <Link2 size={16} aria-hidden="true" />
                  <span>{apkgUrlCopied ? "コピー済み" : "URLをコピー"}</span>
                </button>
              </div>
            </div>
          ) : null}

          <div className="preview-card">
            <div className="preview-head">
              <FileText size={16} aria-hidden="true" />
              <span>TSV preview</span>
            </div>
            <pre className="preview" aria-label="TSVプレビュー">
              {previewLines || "ここにTSVプレビューが表示されます。"}
            </pre>
          </div>
        </aside>
      </section>

      <section className="safety-band">
        <ShieldCheck size={19} aria-hidden="true" />
        <p>
          入力された問題文は変換処理のためサーバーに送信されます。リンク作成をONにすると、APKGファイルが一時保存され、期限付きURLが発行されます。
        </p>
      </section>

      <div className="command-bar">
        <button className="icon-button" disabled={!source && !result} onClick={reset} title="リセット" type="button">
          <RotateCcw size={18} aria-hidden="true" />
        </button>
        <button className="primary-button" disabled={!canConvert} onClick={convert} type="button">
          {isConverting ? <Loader2 className="spin" size={19} aria-hidden="true" /> : <Send size={19} aria-hidden="true" />}
          <span>{isConverting ? "変換中" : "変換する"}</span>
        </button>
        <span className="command-hint">
          <CheckCircle2 size={16} aria-hidden="true" />
          {result ? "Export ready" : "Paste source"}
        </span>
      </div>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
