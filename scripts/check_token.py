"""トークンの状態を確かめる（投稿はしない）。

表示するのは、有効かどうか・有効期限・権限・つながっているアカウント名だけ。
トークンそのものは表示しない。
"""
import datetime, json, os, sys, urllib.error, urllib.parse, urllib.request

API = "https://graph.facebook.com/v26.0"
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "").strip()
IG_USER_ID = os.environ.get("IG_USER_ID", "").strip()
JST = datetime.timezone(datetime.timedelta(hours=9))


def get(path, **params):
    params["access_token"] = TOKEN
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode(errors="replace").replace(TOKEN, "***")}


def when(ts):
    if not ts:
        return "なし（期限切れにならない）"
    return datetime.datetime.fromtimestamp(ts, JST).strftime("%Y-%m-%d %H:%M（日本時間）")


def main():
    if not TOKEN:
        sys.exit("IG_ACCESS_TOKEN がありません")
    d = get("debug_token", input_token=TOKEN).get("data", {})
    print("有効:", d.get("is_valid"))
    print("種類:", d.get("type"))
    print("有効期限:", when(d.get("expires_at")))
    print("データアクセスの期限:", when(d.get("data_access_expires_at")))
    print("権限:", ", ".join(d.get("scopes", [])))
    acct = get(IG_USER_ID, fields="username,media_count")
    print("Instagramアカウント:", acct.get("username"), "/ 投稿数:", acct.get("media_count"), acct.get("error", ""))
    days = None
    if d.get("expires_at"):
        days = (d["expires_at"] - datetime.datetime.now(JST).timestamp()) / 86400
        print(f"期限まで: あと{days:.0f}日")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"valid={str(bool(d.get('is_valid'))).lower()}\n")
            f.write(f"days_left={'' if days is None else int(days)}\n")
    if not d.get("is_valid"):
        sys.exit("トークンが無効です。作り直しが必要です。")


if __name__ == "__main__":
    main()
