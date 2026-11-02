"""もちもち16タイプ：その日のリールを1本だけInstagramに公開する。

- queue.json から「今日（日本時間）」の分を探して公開する
- 公開済みのものは posted.json に記録し、二重投稿しない
- 在庫が少なくなったら、GitHubのIssueでお知らせする
- トークンはログに出さない

環境変数
  IG_ACCESS_TOKEN   … GitHub Secrets に保存したトークン（必須）
  IG_USER_ID        … InstagramのユーザーID
  VIDEO_BASE_URL    … 動画を置いてあるURLの先頭（省略時は jsDelivr 経由）
  DRY_RUN=1         … 公開せずに、アップロード（下準備）まで確かめる
  TARGET_DATE       … 日付を指定するとき（YYYY-MM-DD、テスト用）
"""
import datetime, json, os, sys, time, urllib.error, urllib.parse, urllib.request

API = "https://graph.facebook.com/v26.0"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JST = datetime.timezone(datetime.timedelta(hours=9))
LOW_STOCK_DAYS = 7

TOKEN = os.environ.get("IG_ACCESS_TOKEN", "").strip()
IG_USER_ID = os.environ.get("IG_USER_ID", "").strip()
REPO = os.environ.get("GITHUB_REPOSITORY", "mochi16type/mochi16type-reels")
SHA = os.environ.get("GITHUB_SHA", "main")
BASE = os.environ.get("VIDEO_BASE_URL") or f"https://cdn.jsdelivr.net/gh/{REPO}@{SHA}/videos/"
DRY = os.environ.get("DRY_RUN") == "1"


def redact(s):
    return str(s).replace(TOKEN, "***") if TOKEN else str(s)


def call(method, path, **params):
    params["access_token"] = TOKEN
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}"
    if method == "GET":
        req = urllib.request.Request(f"{url}?{data.decode()}")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(redact(f"Graph API {method} {path} -> {e.code}: {body}")) from None


def load(name, default):
    p = os.path.join(ROOT, name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(name, obj):
    with open(os.path.join(ROOT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def write_output(key, value):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def publish(entry):
    video_url = BASE + entry["file"]
    print(f"動画: {entry['file']}")
    c = call("POST", f"{IG_USER_ID}/media", media_type="REELS", video_url=video_url,
             caption=entry["caption"], share_to_feed="true", thumb_offset="0")
    cid = c["id"]
    print("アップロード受付:", cid)
    for _ in range(60):  # 最大10分待つ
        time.sleep(10)
        st = call("GET", cid, fields="status_code,status")
        code = st.get("status_code")
        print("処理状況:", code)
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"動画の処理に失敗しました: {st}")
    else:
        raise RuntimeError("動画の処理が10分以内に終わりませんでした")
    if DRY:
        print("DRY_RUN のため公開はしません（アップロードと処理は成功）")
        return None
    pub = call("POST", f"{IG_USER_ID}/media_publish", creation_id=cid)
    print("公開しました:", pub.get("id"))
    return pub.get("id")


def main():
    if not TOKEN or not IG_USER_ID:
        sys.exit("IG_ACCESS_TOKEN と IG_USER_ID が必要です")
    today = os.environ.get("TARGET_DATE") or datetime.datetime.now(JST).date().isoformat()
    queue = load("queue.json", [])
    posted = load("posted.json", [])
    done = {p["date"] for p in posted}

    remaining = [q for q in queue if q["date"] > today and q["date"] not in done]
    write_output("remaining_days", len(remaining))
    print(f"今日: {today} / これから先の在庫: {len(remaining)}本")

    todays = [q for q in queue if q["date"] == today]
    if not todays:
        print("今日の分は予定にありません")
        write_output("posted", "none")
        return
    entry = todays[0]
    if today in done and not DRY:
        print("今日の分は公開済みです")
        write_output("posted", "already")
        return
    media_id = publish(entry)
    if media_id:
        posted.append({"date": today, "file": entry["file"], "media_id": media_id,
                       "at": datetime.datetime.now(JST).isoformat(timespec="seconds")})
        save("posted.json", posted)
        write_output("posted", "yes")
    else:
        write_output("posted", "dry")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # トークンを含めずにエラーを出す
        print("エラー:", redact(e), file=sys.stderr)
        sys.exit(1)
