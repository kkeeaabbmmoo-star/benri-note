#!/usr/bin/env python3
"""便利ノート publisher.

Usage (daily routine):
  python3 tools/publish.py /workspace/benri-note-secret/entries/2026-10-20.json
Options:
  --repo DIR        repo dir (default: this script's parent repo)
  --pass-file FILE  passphrase file (default: /workspace/benri-note-secret/passphrase.txt)
  --no-push         encrypt + update index only (no git commit/push)
  --delete DATE     remove DATE's .enc and index entry (then commit/push unless --no-push)
The plain entry JSON must stay OUTSIDE the repo. Only ciphertext is written here.
"""
import argparse, base64, json, os, re, secrets, subprocess, sys, datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

ITER = 200_000
SECTIONS = ["health", "savings", "news", "pikmin", "mail"]
FLAGS = {"check", "prio", "forget", None}
b64 = lambda b: base64.b64encode(b).decode()

def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "item"

def derive(pw, salt):
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(pw.encode())

def load_index(path):
    if os.path.exists(path):
        with open(path) as f: return json.load(f)
    return {"v": 1, "kdf": {"alg": "PBKDF2-SHA256", "iter": ITER, "salt": b64(secrets.token_bytes(16))}, "dates": []}

def fix_yui(it):
    """ゆい's corner: her Grok app still calls herself ゆず; show ゆい (由依)."""
    if not str(it.get("slug","")).startswith("yui"): return
    it["title"] = it["title"].replace("ゆず", "ゆい")
    d = it.get("detail", "")
    m = re.match(r"(「.*?」)(.*)\Z", d, re.S)
    if m:
        d = m.group(1).replace("ゆず", "ゆい") + m.group(2)
    else:
        d = d.replace("ゆず", "ゆい")
    d = d.replace("（中では前の名前で名乗ってるね）", "")
    it["detail"] = d

def normalize(e):
    date = e["date"]; datetime.date.fromisoformat(date)
    seen = set()
    for sec in e["sections"]:
        if sec["key"] not in SECTIONS: sys.exit(f"unknown section {sec['key']}")
        for it in sec["items"]:
            slug = slugify(it.get("slug") or it["title"])
            iid = f"{date}-{sec['key']}-{slug}"
            if iid in seen: sys.exit(f"duplicate id {iid}")
            seen.add(iid); it["id"] = iid; it["slug"] = slug
            fix_yui(it)
            if it.get("flag") not in FLAGS: sys.exit(f"bad flag {it.get('flag')} in {iid}")
    top = []
    for t in e.get("top3", []):
        if isinstance(t, str):  # "section/slug" or full id
            t = t if t.startswith(date) else f"{date}-{t.replace('/', '-')}"
            if t not in seen: sys.exit(f"top3 ref not found: {t}")
            top.append(t)
    e["top3"] = top
    return e

def git(repo, *a):
    subprocess.run(["git", "-C", repo, *a], check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entry", nargs="?")
    ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--pass-file", default="/workspace/benri-note-secret/passphrase.txt")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--delete")
    a = ap.parse_args()
    data = os.path.join(a.repo, "data"); os.makedirs(data, exist_ok=True)
    ipath = os.path.join(data, "index.json")
    idx = load_index(ipath)
    if a.delete:
        p = os.path.join(data, f"{a.delete}.enc")
        if os.path.exists(p): os.remove(p)
        idx["dates"] = [d for d in idx["dates"] if d != a.delete]
        msg = f"remove {a.delete}"
    else:
        if not a.entry: sys.exit("entry json required")
        if os.path.abspath(a.entry).startswith(os.path.abspath(a.repo) + os.sep):
            sys.exit("refusing: plain entry must live outside the repo")
        with open(a.entry) as f: e = normalize(json.load(f))
        with open(a.entry, "w") as f: json.dump(e, f, ensure_ascii=False, indent=1)  # write back ids
        pw = open(a.pass_file).read().strip()
        salt = base64.b64decode(idx["kdf"]["salt"]); iv = secrets.token_bytes(12)
        ct = AESGCM(derive(pw, salt)).encrypt(iv, json.dumps(e, ensure_ascii=False).encode(), b"benri-note:" + e["date"].encode())
        with open(os.path.join(data, f"{e['date']}.enc"), "w") as f:
            json.dump({"v": 1, "alg": "AES-GCM", "kdf": "PBKDF2-SHA256", "iter": ITER, "salt": idx["kdf"]["salt"], "iv": b64(iv), "aad": "benri-note:" + e["date"], "ct": b64(ct)}, f)
        if e["date"] not in idx["dates"]: idx["dates"].append(e["date"])
        msg = f"entry {e['date']}"
    idx["dates"] = sorted(set(idx["dates"]))
    idx["updated"] = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec="seconds")
    with open(ipath, "w") as f: json.dump(idx, f, ensure_ascii=False, indent=1)
    print(f"{msg}: index has {len(idx['dates'])} dates -> {idx['dates'][-3:]}")
    if not a.no_push:
        git(a.repo, "add", "-A", "data")
        r = subprocess.run(["git", "-C", a.repo, "diff", "--cached", "--quiet"])
        if r.returncode: git(a.repo, "commit", "-q", "-m", msg)
        git(a.repo, "push", "-q", "origin", "HEAD")
        print("pushed")

if __name__ == "__main__":
    main()
