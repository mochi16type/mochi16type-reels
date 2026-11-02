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
    raw = get("debug_token", input_token=TOKEN)
    if "error" in raw:
        print("debug_token:", raw["error"])
    d = raw.get("data", {})
    me = get("me", fields="id,name")
    print("トークンの持ち主:", me.get("name"), me.get("id"), me.get("error", ""))
    perms = get("me/permissions")
    if "data" in perms:
        print("許可された権限:", ", ".join(p["permission"] for p in perms["data"] if p.get("status") == "granted"))
    else:
        print("権限の取得:", perms.get("error"))
    pages = get("me/accounts", fields="name,instagram_business_account{id,username}")
    if "data" in pages:
        for pg in pages["data"]:
            ig = pg.get("instagram_business_account") or {}
            print("Facebookページ:", pg.get("name"), "→ Instagram:", ig.get("username"), ig.get("id"))
        if not pages["data"]:
            print("Facebookページ: なし")
    else:
        print("ページの取得:", pages.get("error"))
    if d:
        print("有効:", d.get("is_valid"))
        print("種類:", d.get("type"))
        print("有効期限:", when(d.get("expires_at")))
        print("データアクセスの期限:", when(d.get("data_access_expires_at")))
        print("権限:", ", ".join(d.get("scopes", [])))
    else:
        print("有効期限: 確認できません（システムユーザーのトークンは、通常は期限なし）")
    acct = get(IG_USER_ID, fields="username,media_count")
    print("Instagramアカウント:", acct.get("username"), "/ 投稿数:", acct.get("media_count"), acct.get("error", ""))
    days = None
    if d.get("expires_at"):
        days = (d["expires_at"] - datetime.datetime.now(JST).timestamp()) / 86400
        print(f"期限まで: あと{days:.0f}日")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"valid={str(bool(d.get('is_valid') or 'id' in me)).lower()}\n")
            f.write(f"days_left={'' if days is None else int(days)}\n")
    if not (d.get("is_valid") or "id" in me):
        sys.exit("トークンが無効です。作り直しが必要です。")
    if "error" in acct:
        sys.exit("Instagramアカウントにアクセスできません。トークンにアカウントが割り当てられているか確認してください。")


if __name__ == "__main__":
    main()
