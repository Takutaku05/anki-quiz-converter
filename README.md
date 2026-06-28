# Anki Quiz Converter Web

薬理学の演習問題解答テキストをAnkiインポート用TSVに変換するWebアプリです。

## 構成

- `src/quiz_converter.py`: 既存の変換ロジック
- `src/api.py`: FastAPI API
- `src/r2_storage.py`: Cloudflare R2へアップロードし、署名付きURLを発行
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

`POST /api/convert` は、R2設定が揃っている場合にAPKGをR2へ保存し、署名付きURLを返します。設定がない場合も変換自体は成功し、ブラウザ内でTSVをダウンロードできます。

必要な環境変数:

```bash
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,https://your-pages-domain.pages.dev
R2_ACCOUNT_ID=your_cloudflare_account_id
R2_ACCESS_KEY_ID=your_r2_access_key_id
R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
R2_BUCKET_NAME=your_r2_bucket_name
R2_PUBLIC_PREFIX=generated
R2_LINK_TTL_SECONDS=86400
```

リンクはAPKGファイルへの署名付きURLです。リンクを知っている人は、有効期限内であればファイルをダウンロードできます。

## Cloudflare Pages

Cloudflare Pagesには `web/` をデプロイします。

- Build command: `npm run build`
- Build output directory: `dist`
- Root directory: `web`
- Environment variable: `VITE_API_BASE_URL=https://your-api-domain.example.com`

## FastAPIデプロイ

`render.yaml` を追加しています。Renderにデプロイする場合は、上記のR2環境変数と `CORS_ORIGINS` を設定してください。

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
  "apkg_filename": "薬理学Ⅲ_アレルギー疾患治療薬.apkg",
  "downloads": {
    "tsv": null,
    "apkg": {
      "url": "https://...",
      "filename": "薬理学Ⅲ_アレルギー疾患治療薬.apkg",
      "expires_at": "2026-06-29T12:00:00+00:00",
      "expires_in_seconds": 86400
    }
  },
  "warnings": []
}
```

変換失敗時は日本語メッセージを返します。

- `タイトルからデッキ名を抽出できません。`
- `問題ブロックが見つかりません。`
- `解答選択肢が見つかりません。`

## テスト

```bash
python3 -m unittest discover -s tests
```
