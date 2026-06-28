import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { CheckCircle2, Copy, Download, ExternalLink, Loader2, RotateCcw } from "lucide-react";
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

  function reset() {
    setSource("");
    setResult(null);
    setError("");
  }

  return (
    <main className="app-shell">
      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Anki Quiz Converter</p>
            <h1>演習問題解答をAnki用ファイルへ変換</h1>
          </div>
        </header>

        <div className="notice" role="note">
          入力された問題文は変換処理のためサーバーに送信されます。リンク作成をONにすると、Anki用の.apkgファイルが期限付きダウンロードリンクとして一時的に保存されます。
        </div>

        <div className="grid">
          <section className="panel input-panel" aria-labelledby="input-title">
            <div className="panel-head">
              <div>
                <h2 id="input-title">入力</h2>
                <p>NotebookLMなどからコピーした演習問題解答を貼り付けます。</p>
              </div>
              <label className="toggle">
                <input
                  checked={createDownloadLink}
                  disabled={!canCreateApkgLink}
                  onChange={(event) => setCreateDownloadLink(event.target.checked)}
                  type="checkbox"
                />
                <span>{canCreateApkgLink ? "APKGリンク作成" : "R2未設定"}</span>
              </label>
            </div>

            <textarea
              aria-label="変換元テキスト"
              className="source-textarea"
              onChange={(event) => setSource(event.target.value)}
              placeholder="薬理学Ⅲ（アレルギー疾患治療薬）演習問題解答..."
              value={source}
            />

            {error ? <div className="error-box" role="alert">{error}</div> : null}

            <div className="actions">
              <button className="primary-button" disabled={!canConvert} onClick={convert} type="button">
                {isConverting ? <Loader2 className="spin" size={18} aria-hidden="true" /> : <CheckCircle2 size={18} aria-hidden="true" />}
                <span>{isConverting ? "変換中" : "変換"}</span>
              </button>
              <button className="icon-button" disabled={!source && !result} onClick={reset} title="リセット" type="button">
                <RotateCcw size={18} aria-hidden="true" />
              </button>
            </div>
          </section>

          <section className="panel output-panel" aria-labelledby="output-title">
            <div className="panel-head">
              <div>
                <h2 id="output-title">出力</h2>
                <p>{result ? result.deck : "TSVは即時ダウンロード、APKGはリンク作成ONで発行されます。"}</p>
              </div>
            </div>

            <div className="output-actions">
              <button className="secondary-button" disabled={!result} onClick={downloadLocal} type="button">
                <Download size={18} aria-hidden="true" />
                <span>TSVダウンロード</span>
              </button>
              <button className="secondary-button" disabled={!result} onClick={copyTsv} type="button">
                <Copy size={18} aria-hidden="true" />
                <span>コピー</span>
              </button>
              <a
                aria-disabled={!result?.downloads.apkg}
                className={`secondary-link ${result?.downloads.apkg ? "" : "disabled"}`}
                href={result?.downloads.apkg?.url ?? "#"}
                rel="noreferrer"
                target="_blank"
                title={result?.downloads.apkg ? "APKGの期限付きリンクを開く" : "APKGリンク作成がOFF、またはR2設定が未設定です"}
              >
                <ExternalLink size={18} aria-hidden="true" />
                <span>{result?.downloads.apkg ? "APKGリンクを開く" : "APKGリンク未作成"}</span>
              </a>
            </div>

            {result?.warnings.map((warning) => (
              <div className="warning-box" key={warning}>{warning}</div>
            ))}

            {result?.downloads.apkg ? (
              <div className="link-meta">
                <span>{result.downloads.apkg.filename}</span>
                <span>有効期限: {new Date(result.downloads.apkg.expires_at).toLocaleString("ja-JP")}</span>
              </div>
            ) : null}

            <pre className="preview" aria-label="TSVプレビュー">
              {previewLines || "ここにTSVプレビューが表示されます。"}
            </pre>
          </section>
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
