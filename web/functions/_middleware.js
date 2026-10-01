// 旧URL（pages.dev）へのアクセスに移転のお知らせを返し、新ドメインへ誘導する。
// プレビューデプロイ（<hash>.anki-quiz-converter.pages.dev）や新ドメインには影響しない。
const OLD_HOST = "anki-quiz-converter.pages.dev";
const NEW_ORIGIN = "https://anki-quiz.takutakus.com";
const REDIRECT_SECONDS = 5;

export async function onRequest(context) {
  const url = new URL(context.request.url);
  if (url.hostname !== OLD_HOST) {
    return context.next();
  }

  const destination = new URL(url.pathname + url.search, NEW_ORIGIN).href;
  return new Response(renderNotice(destination), {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Robots-Tag": "noindex",
    },
  });
}

function escapeHtml(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderNotice(destination) {
  // meta refresh の url= はクォートで区切られるため、引用符はパーセントエンコードしておく
  const href = escapeHtml(destination.replace(/'/g, "%27").replace(/"/g, "%22"));
  return `<!doctype html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<meta name="theme-color" content="#fbf3e7">
<meta http-equiv="refresh" content="${REDIRECT_SECONDS}; url='${href}'">
<link rel="canonical" href="${href}">
<link rel="icon" type="image/svg+xml" href="${NEW_ORIGIN}/favicon.svg">
<title>移転しました — Anki Quiz Converter</title>
<style>
  :root {
    --kinari: #fbf3e7;
    --card: #fffdf9;
    --ink: #46352a;
    --ink-soft: #8b7663;
    --mikan: #ec7b2e;
    --mikan-deep: #c25e17;
    --line: #ebdcc6;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    min-height: 100vh;
    display: grid;
    place-items: center;
    padding: 24px 16px;
    background: var(--kinari);
    color: var(--ink);
    font-family: "Hiragino Maru Gothic ProN", "Hiragino Kaku Gothic ProN", "Yu Gothic", ui-sans-serif, system-ui, sans-serif;
    line-height: 1.7;
  }
  main {
    width: 100%;
    max-width: 480px;
    padding: 36px 28px;
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 20px;
    box-shadow: 0 6px 0 var(--line);
    text-align: center;
  }
  h1 { margin: 0 0 12px; font-size: 1.4rem; }
  p { margin: 0 0 8px; }
  .note { color: var(--ink-soft); font-size: 0.9rem; }
  .url { word-break: break-all; font-weight: 700; }
  a.button {
    display: inline-block;
    margin: 20px 0 16px;
    padding: 12px 28px;
    background: var(--mikan);
    color: #fff;
    font-weight: 700;
    text-decoration: none;
    border-radius: 999px;
    box-shadow: 0 4px 0 var(--mikan-deep);
  }
  a.button:active { transform: translateY(2px); box-shadow: 0 2px 0 var(--mikan-deep); }
</style>
</head>
<body>
<main>
  <h1>このページは移転しました</h1>
  <p>Anki Quiz Converter は新しいアドレスに引っ越しました。</p>
  <p class="url">${escapeHtml(NEW_ORIGIN.replace("https://", ""))}</p>
  <a class="button" href="${href}">新しいページへ移動する</a>
  <p class="note"><span id="countdown">${REDIRECT_SECONDS}</span>秒後に自動で移動します。<br>ブックマークの更新をお願いします。</p>
</main>
<script>
  (function () {
    var el = document.getElementById("countdown");
    var left = ${REDIRECT_SECONDS};
    var timer = setInterval(function () {
      left -= 1;
      if (left <= 0) { clearInterval(timer); left = 0; }
      el.textContent = String(left);
    }, 1000);
  })();
</script>
</body>
</html>`;
}
