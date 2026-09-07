"""【初回セットアップ専用・自分のPCで1回だけ実行】

Google Cloud ConsoleでダウンロードしたOAuthクライアントの client_secret.json を使い、
ブラウザでGoogleログイン/同意を行って、GitHub Actionsで使うリフレッシュトークンを取得する。

使い方:
    1. Google Cloud Console で OAuth クライアントID(種類: デスクトップアプリ)を作成し、
       client_secret.json をこのファイルと同じフォルダに置く。
    2. pip install google-auth-oauthlib
    3. python authorize_youtube.py
    4. ブラウザが開くのでログインし、YouTubeアップロード権限を許可する。
    5. ターミナルに表示される CLIENT_ID / CLIENT_SECRET / REFRESH_TOKEN を
       GitHub Secrets (YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN) に登録する。

このスクリプトの実行はPCを消す前に1回だけでよい。
以降はGitHub Actions側がリフレッシュトークンだけで自動的に新しいアクセストークンを取得する。
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRETS_FILE = "client_secret.json"


def main() -> None:
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    print("\n===== 以下をGitHub Secretsに登録してください =====")
    print(f"YT_CLIENT_ID={creds.client_id}")
    print(f"YT_CLIENT_SECRET={creds.client_secret}")
    print(f"YT_REFRESH_TOKEN={creds.refresh_token}")
    print("====================================================\n")

    if not creds.refresh_token:
        print(
            "警告: refresh_tokenが取得できませんでした。\n"
            "Google Cloud Consoleでこのアプリの認可を一度取り消してから、再実行してください。\n"
            "(https://myaccount.google.com/permissions)"
        )


if __name__ == "__main__":
    main()
