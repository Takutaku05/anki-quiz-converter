# Anki Quiz Converter Web

薬理学の演習問題解答テキストをAnkiインポート用TSVとWordHolic用CSVに変換するWebアプリです。

## 構成

- `src/quiz_converter.py`: 既存の変換ロジック
- `src/wordholic_builder.py`: Anki TSVからWordHolic CSVを生成するロジック
- `src/pdf_extractor.py`: アップロードされたPDFからテキストを抽出するロジック（pypdf）
- `src/api.py`: FastAPI API
- `src/download_store.py`: 変換した.apkgをサーバーメモリに一時保存し、トークン付きURLで配信
- `web/`: Cloudflare Pages向けReact/Viteフロントエンド
- `tests/`: 標準ライブラリ `unittest` で走る最低限のテスト

## ローカル起動

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.api:app --reload
```

別ターミナルでフロントエンドを起動します。

```bash
cd web
npm install
cp .env.example .env
npm run dev
```

ブラウザで `http://localhost:5173` を開きます。

## 期限付きダウンロードリンク

`POST /api/convert` はAnki TSVとWordHolic CSVを返します。APKGリンク作成が有効な場合は、APKGをサーバーメモリに一時保存し、`GET /api/download/{token}` のURLも返します。外部ストレージ（R2など）は不要です。

- リンクの有効期限は `DOWNLOAD_LINK_TTL_SECONDS`（デフォルト30分）
- サーバー再起動やスリープ（Render無料プラン）でリンクは無効になります。その場合は再変換してください
- フロントエンドはURLのQRコードを表示するので、PCで変換してスマホのAnkiアプリでインポートできます
- WordHolic CSVは `FrontText,BackText,Comment,FrontTextLanguage,BackTextLanguage` の5列で生成します

必要な環境変数:

```bash
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,https://your-pages-domain.pages.dev

# プロキシ配下（Renderなど）ではダウンロードURLの組み立てに使うため明示推奨
PUBLIC_BASE_URL=https://your-api-domain.example.com
DOWNLOAD_LINK_TTL_SECONDS=1800
DOWNLOAD_MAX_ENTRIES=100
```

リンクはトークン付きURLです。リンクを知っている人は、有効期限内であればファイルをダウンロードできます。

## Cloudflare Pages

Cloudflare Pagesには `web/` をデプロイします。

- Build command: `npm run build`
- Build output directory: `dist`
- Root directory: `web`
- Environment variable: `VITE_API_BASE_URL=https://your-api-domain.example.com`

## FastAPIデプロイ

`render.yaml` を追加しています。Renderにデプロイする場合は、`CORS_ORIGINS` と `PUBLIC_BASE_URL` を設定してください。

start command:

```bash
uvicorn src.api:app --host 0.0.0.0 --port $PORT
```

## API

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

`GET /api/download/{token}` は有効期限内であれば.apkgバイナリを返します。期限切れ・不明トークンは404と日本語メッセージを返します。

変換失敗時は日本語メッセージを返します。

- `解答選択肢が見つかりません。`

問題番号（`問1` など）が見つからない場合は失敗せず、`warnings` で通知して変換を続行します。

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

### PDFからのテキスト抽出

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

エラー時は422（PDF処理失敗）・413（サイズ超過）・400（PDF以外）で日本語メッセージを返します。

- `パスワード付き（暗号化された）PDFには対応していません。…`（暗号化PDF）
- `PDFから文字を抽出できませんでした。画像として保存されたPDF（スキャンや写真）には対応していません。…`（テキスト層なし）
- `ページ数が多すぎます。50ページ以下のPDFをアップロードしてください。`（ページ数上限超過）
- `PDFを読み取れませんでした。ファイルが壊れていないか確認してください。`（破損など）

## テスト

```bash
python3 -m unittest discover -s tests
```
