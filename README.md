# Anki Quiz Converter Web

薬理学の演習問題解答テキスト（またはPDF）を、Ankiインポート用TSV・WordHolic用CSV・Ankiデッキ（.apkg）に変換するWebアプリです。

- **入力**: `問1` 形式の◯×問題テキスト、または文字が埋め込まれたPDF
- **出力**: Anki TSV / WordHolic CSV（画面でコピー・保存）、.apkg（期限付きダウンロードリンク＋QRコード）
- **構成**: FastAPI バックエンド（Render）＋ React/Vite フロントエンド（Cloudflare Pages）

## ディレクトリ構成

| パス | 内容 |
| --- | --- |
| `src/quiz_converter.py` | 変換ロジック本体（タイトル・問題・解答の柔軟な判定、CLIあり） |
| `src/wordholic_builder.py` | Anki TSVからWordHolic用CSV（5列）を生成 |
| `src/apkg_builder.py` | Anki TSVから.apkgを生成（genanki、決定的なデッキID/GUID） |
| `src/pdf_extractor.py` | PDFからのテキスト抽出（pypdf、CJK間の不要スペース除去） |
| `src/api.py` | FastAPI アプリ（CORS、エラーログ、各エンドポイント） |
| `src/api_helpers.py` | 日本語エラーメッセージ・ダウンロードファイル名の生成 |
| `src/download_store.py` | .apkgをサーバーメモリに一時保存し、トークン付きURLで配信 |
| `web/` | Cloudflare Pages向け React/Vite フロントエンド |
| `tests/` | 標準ライブラリ `unittest` で走るテスト |
| `example/` | サンプル一式（`sauce/`: 入力テキスト・PDF、`output/`: 変換結果のTSV/CSV） |

## ローカル起動

バックエンド（`http://localhost:8000`）:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.api:app --reload
```

フロントエンド（別ターミナル、`http://localhost:5173`）:

```bash
cd web
npm install
cp .env.example .env   # VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

変換ロジックだけをCLIで試すこともできます:

```bash
python3 src/quiz_converter.py "example/sauce/アレルギー疾患治療薬.txt"
```

## 環境変数（バックエンド）

`.env.example` 参照。

| 変数 | デフォルト | 説明 |
| --- | --- | --- |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | 許可するオリジン（カンマ区切り） |
| `PUBLIC_BASE_URL` | （リクエストURLから推測） | ダウンロードURLの組み立てに使用。プロキシ配下（Renderなど）では明示推奨 |
| `DOWNLOAD_LINK_TTL_SECONDS` | `1800`（30分） | ダウンロードリンクの有効期限 |
| `DOWNLOAD_MAX_ENTRIES` | `100` | メモリに保持する.apkgの最大件数（超過分は古い順に削除） |
| `LOG_LEVEL` | `INFO` | APIのログレベル |

## API

### `GET /api/health`

死活確認。`{"status": "ok"}` を返します。

### `GET /api/capabilities`

フロントエンドが機能の有無を判定するためのエンドポイント。

```json
{
  "apkg_download_links_enabled": true,
  "link_ttl_seconds": 1800
}
```

### `POST /api/convert`

テキストを変換します。

```http
POST /api/convert
Content-Type: application/json

{
  "source": "薬理学Ⅲ（アレルギー疾患治療薬）演習問題解答...",
  "create_download_link": true
}
```

成功時:

```json
{
  "deck": "薬理学Ⅲ::アレルギー疾患治療薬",
  "card_count": 50,
  "tsv": "#separator:Tab\n...",
  "tsv_filename": "薬理学Ⅲ_アレルギー疾患治療薬.tsv",
  "wordholic_csv": "FrontText,BackText,Comment,FrontTextLanguage,BackTextLanguage\r\n...",
  "wordholic_filename": "薬理学Ⅲ_アレルギー疾患治療薬_WordHolic.csv",
  "apkg_filename": "薬理学Ⅲ_アレルギー疾患治療薬.apkg",
  "downloads": {
    "tsv": null,
    "apkg": {
      "url": "https://your-api-domain.example.com/api/download/xxxxxxxx",
      "filename": "薬理学Ⅲ_アレルギー疾患治療薬.apkg",
      "expires_at": "2026-07-02T12:30:00+00:00",
      "expires_in_seconds": 1800
    }
  },
  "warnings": []
}
```

- `create_download_link: true` の場合、.apkgをサーバーメモリに一時保存し、`downloads.apkg` にトークン付きURLを返します。外部ストレージ（R2など）は不要です
- 変換に失敗した場合は400と日本語メッセージ（例: `解答選択肢が見つかりません。`）を返します
- WordHolic CSVの生成に失敗しても変換自体は成功し、`warnings` で通知します

### `GET /api/download/{token}`

有効期限内であれば.apkgバイナリを返します。期限切れ・不明トークンは404と日本語メッセージを返します。

- リンクを知っている人は有効期限内であれば誰でもダウンロードできます
- サーバー再起動やスリープ（Render無料プラン）でリンクは無効になります。その場合は再変換してください
- フロントエンドはURLのQRコードを表示するので、PCで変換してスマホのAnkiアプリでインポートできます

### `POST /api/extract-pdf`

テキスト入力の代わりにPDFをアップロードして、抽出したテキストを変換元にできます。抽出結果は変換前に画面のテキスト欄で確認・修正できます。

```http
POST /api/extract-pdf
Content-Type: multipart/form-data

file=<PDFファイル>
```

成功時:

```json
{
  "text": "薬理学Ⅲ（アレルギー疾患治療薬）演習問題解答...",
  "page_count": 3,
  "char_count": 1234
}
```

- **文字が埋め込まれたPDFのみ対応**します。スキャン画像や写真のPDF（テキスト層がないPDF）は非対応で、OCRは行いません
- アップロード上限は10MB、ページ数上限は50ページです

エラー時は400（PDF以外）・413（サイズ超過）・422（PDF処理失敗）で日本語メッセージを返します。

| 状況 | ステータス | メッセージ |
| --- | --- | --- |
| PDF以外のファイル | 400 | `PDFファイルを選択してください。` |
| 10MB超過 | 413 | `ファイルサイズが大きすぎます。…` |
| 暗号化PDF | 422 | `パスワード付き（暗号化された）PDFには対応していません。…` |
| テキスト層なし | 422 | `PDFから文字を抽出できませんでした。画像として保存されたPDF…` |
| 50ページ超過 | 422 | `ページ数が多すぎます。50ページ以下のPDFをアップロードしてください。` |
| 破損など | 422 | `PDFを読み取れませんでした。ファイルが壊れていないか確認してください。` |

## 変換の仕様

### タイトル・問題・解答の柔軟な判定

`演習問題解答` という定型タイトルがなくても変換できます。判定は次の優先順位で行い、フォールバックした場合は `warnings` に日本語の注意を載せて返します（フロントエンドにも表示されます）。

- **タイトル / デッキ名**
  1. `…（…）演習問題解答` の厳密形式
  2. 冒頭付近の `科目（単元）` 形式（`演習問題`・`問題集`・`小テスト`・`まとめ` などの語尾、または語尾なしでも可）→ `科目::単元`
  3. 上記に当てはまらない場合は先頭の見出し行をデッキ名に使用（警告あり）
  4. 見出しも取れない場合はデッキ名 `変換デッキ`（警告あり）
- **問題番号**: `問1` に加えて `問題1` `設問1` `Q1`（全角も可）を認識。番号が無くても変換は続行（警告あり）
- **解答記号**: `（○）`（○〇◯／×✕✖）に加えて、`（正）`『（誤）』などの語、`答え：○` のような接頭辞、行末の記号も認識
- **選択肢**: 番号付き（`1.` など）が無い箇所は、行ごとに「文＋解答記号」を判定するフォールバックを使用（警告あり）

### 出力の補足

- カードのタグ列には `問N` に加えて、`第N回` の記載や `以下は予想問題` の直後の問題を検出して `第N回` / `予想問題` タグを付けます
- 解答記号の後ろに続く文（`※註：…` など）は、カード表面の末尾に註として付加します
- 入力中のURL（NotebookLMの画像URLなど）は変換前に除去します
- WordHolic CSVは `FrontText,BackText,Comment,FrontTextLanguage,BackTextLanguage` の5列・CRLF区切りで生成します
- .apkgのデッキID・ノートGUIDはデッキ名とカード内容から決定的に生成するため、再変換して再インポートしても重複しません

## デプロイ

### Cloudflare Pages（フロントエンド）

`web/` をデプロイします。

- Build command: `npm run build`
- Build output directory: `dist`
- Root directory: `web`
- Environment variable: `VITE_API_BASE_URL=https://your-api-domain.example.com`

### Render（バックエンド）

`render.yaml` にBlueprint定義があります（Python 3.12 / freeプラン）。`CORS_ORIGINS` と `PUBLIC_BASE_URL` はダッシュボードで設定してください。

start command:

```bash
uvicorn src.api:app --host 0.0.0.0 --port $PORT
```

デプロイ設定を変更した場合は `DEPLOY_NOTES.md` に記載します。

## テスト

```bash
python3 -m unittest discover -s tests
```
