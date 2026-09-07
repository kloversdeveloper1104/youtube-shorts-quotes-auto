# YouTube Shorts 自動運営 (名言・モチベーション系 / ランニングコスト0円)

GitHub Actions上で1日2回、以下を自動で行います。

1. オリジナルの名言テキストを用意(Gemini APIで新規生成、失敗時は同梱のfallback名言集から選択)
2. 無料の音声合成(edge-tts / gTTS)でナレーションを作成
3. コードで生成したグラデーション背景+同期字幕で縦型動画を組み立て
4. YouTube Data APIで自分のチャンネルにShortsとして投稿

**あなたのPCの電源には依存しません**(GitHub のサーバー上で動きます)。ただし後述の初回セットアップだけは、あなたのPC/ブラウザで一度だけ行う必要があります。

---

## 0. 全体の流れ(所要時間目安 30〜60分、費用は基本0円)

1. Google Cloud で YouTube Data API を有効化し、OAuthクライアントを作る
2. `authorize_youtube.py` を自分のPCで1回だけ実行し、リフレッシュトークンを取得する
3. (任意)Gemini APIキーを取得する
4. GitHubにこのリポジトリをpushする
5. GitHub Secretsに認証情報を登録する
6. Actionsを手動実行して動作確認 → あとは自動運転

---

## 1. Google Cloud / YouTube API の準備

1. [Google Cloud Console](https://console.cloud.google.com/) で新しいプロジェクトを作成
2. 「APIとサービス」→「ライブラリ」→ **YouTube Data API v3** を有効化
3. 「APIとサービス」→「OAuth同意画面」を設定
   - User Type: 外部
   - スコープに `.../auth/youtube.upload` を追加
   - テストユーザーに自分のGoogleアカウント(チャンネルを持っているアカウント)を追加
4. 「認証情報」→「認証情報を作成」→「OAuthクライアントID」
   - アプリケーションの種類: **デスクトップアプリ**
   - 作成後、JSONをダウンロードして `client_secret.json` にリネームし、このプロジェクトのルートフォルダに置く(**絶対にGitHubにpushしないこと**。`.gitignore`済みです)

> ⚠️ **重要な注意(7日間の期限について)**
> OAuth同意画面が「テスト」ステータスのままだと、リフレッシュトークンは **7日で失効** します。24時間365日ノータッチで動かし続けるには、OAuth同意画面を「本番環境」に公開する必要があります。`youtube.upload` は「制限付きスコープ」のため、本番公開には Google の審査(無料ですが数日〜数週間かかることがあります)が必要です。
> 審査が通るまでの間は、7日ごとに `authorize_youtube.py` を再実行してGitHub Secretsを更新する運用でも動きます(完全放置にはなりませんが、費用は0円のままです)。

---

## 2. リフレッシュトークンの取得(自分のPCで1回だけ)

```bash
pip install google-auth-oauthlib
python authorize_youtube.py
```

ブラウザが開くのでログインし、権限を許可してください。ターミナルに

```
YT_CLIENT_ID=...
YT_CLIENT_SECRET=...
YT_REFRESH_TOKEN=...
```

と表示されるので、あとで使うためにメモしておいてください。

---

## 3. (任意) Gemini APIキーの取得

[Google AI Studio](https://aistudio.google.com/) で無料のAPIキーを発行できます。設定しない場合は、同梱の `src/quotes_fallback.json`(約60個のオリジナル名言)からランダムに選ばれます。

---

## 4. GitHubへpush

```bash
cd auto1
git init
git add .
git commit -m "feat: YouTube Shorts自動投稿の初期構築"
git branch -M main
git remote add origin https://github.com/<あなたのユーザー名>/<リポジトリ名>.git
git push -u origin main
```

公開リポジトリ(Public)にすると、GitHub Actionsの実行時間が無料枠無制限になります(名言動画のコード自体に秘密情報は含まれないので、Publicで問題ありません。認証情報はSecretsに入れるため漏れません)。

---

## 5. GitHub Secretsの登録

リポジトリの **Settings → Secrets and variables → Actions → New repository secret** から、以下を登録してください。

| Secret名 | 値 |
|---|---|
| `YT_CLIENT_ID` | 手順2で取得 |
| `YT_CLIENT_SECRET` | 手順2で取得 |
| `YT_REFRESH_TOKEN` | 手順2で取得 |
| `GEMINI_API_KEY` | 手順3で取得(任意、未設定でも動作します) |

---

## 6. 動作確認

リポジトリの **Actions** タブ →「Publish YouTube Short」→「Run workflow」で手動実行できます。成功すると、あなたのチャンネルにShortsが1本投稿されます。ログは同タブから確認できます。

失敗する場合は、まず `SKIP_UPLOAD=1` を一時的にSecretsではなくローカルの `.env` に設定し、`python src/main.py` をローカルで実行して `output/short.mp4` が正しく生成されるか確認すると原因を切り分けやすいです。

---

## 7. スケジュールの変更

`.github/workflows/publish_short.yml` の `cron` を編集してください(UTC基準)。デフォルトは日本時間 8:00 と 20:00 の1日2回です。頻度を上げるほどGitHub Actionsの実行時間を消費します(Publicリポジトリなら実質無制限、Privateなら無料枠は月2,000分)。

---

## カスタマイズ

- **名言を増やす/変える**: `src/quotes_fallback.json` を編集
- **配色を変える**: `src/generate_video.py` の `PALETTES`
- **投稿する曜日/時間**: ワークフローの `cron`
- **BGMの雰囲気**: `src/generate_video.py` の `_make_ambient_audio` の周波数

---

## 知っておくべきリスク・限界

- **収益化・アルゴリズム面**: YouTubeは「大量生産的・反復的なコンテンツ」を収益化対象外にするポリシーを持っています。完全自動生成のみで長期運用する場合、収益化やおすすめ表示で不利になる可能性があります。サムネイルやテーマに定期的にバリエーションを持たせることを推奨します。
- **無料TTS(edge-tts)の安定性**: 非公式ラッパーのため、Microsoft側の仕様変更で将来動かなくなる可能性があります(コード側でgTTSへの自動フォールバックを用意済み)。
- **OAuthの7日失効**: 上記「1.」参照。放置運用には本番公開申請が必要です。
- **著作権**: 名言はすべてオリジナル文章(fallbackリストは自作、Gemini生成分も「実在の人物の名言の引用/意訳をしない」よう指示済み)。BGMも音声合成のコードで生成しているため、既存音源の著作権侵害リスクはありません。
