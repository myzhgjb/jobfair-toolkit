#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
苏州工业园区校园引才平台（campus.o-hr.com）抓取器

三个子命令：
  discover                     列出平台在挂的招聘活动（用无头浏览器渲染首页取链接）
  fetch --fair-key KEY         抓某场活动：活动信息 + 所有分会场 + 参会企业 + 岗位
  detail --in jobs.json        对 jobs 里的每个岗位补抓 JD/专业/HR 邮箱（带断点续传）

输出统一 schema（可直接喂给 assets/warbook_template.html 或 scripts/match_resume.py）：
{
  "event": {"name","display_date","fair_key","stops":[{"key","name","registered_count"}],
            "source_url","fetched_at"},
  "companies": [{"n","i","sz","ty","addr","d","hire",
                 "jobs":[{"k","j","kk","e","n","s","mj","rq","du","ml"}]}],
  "stats": {"companies":N,"jobs":M,"hire":X}
}

只用标准库 + 无头浏览器（discover 子命令）。无需登录。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = "https://campus.o-hr.com"
API = BASE + "/api"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome", "chromium", "chromium-browser", "msedge",
]


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def http_json(url, retries=3, timeout=25, backoff=2.0):
    """GET JSON。403/拦截页自动退避重试（平台有 WAF，封的是 IP）。"""
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8", "replace")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                # WAF 拦截页返回 HTML
                raise RuntimeError("返回非 JSON（疑似 WAF 拦截，稍等再试）: " + raw[:80])
        except Exception as e:  # noqa: BLE001
            last = e
            if i < retries - 1:
                time.sleep(backoff * (i + 1))
    raise last


def find_chrome():
    for c in CHROME_CANDIDATES:
        if os.path.sep in c:
            if os.path.exists(c):
                return c
        else:
            from shutil import which
            p = which(c)
            if p:
                return p
    return None


def dump_dom(url, budget=12000):
    exe = find_chrome()
    if not exe:
        raise RuntimeError("找不到 Chrome/Edge，discover 子命令需要无头浏览器")
    out = subprocess.run(
        [exe, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
         f"--virtual-time-budget={budget}", "--dump-dom", url],
        capture_output=True, timeout=90,
    )
    return out.stdout.decode("utf-8", "replace")


def cmd_discover(args):
    html = dump_dom(BASE + "/")
    keys = []
    for m in re.finditer(r"activity-single/fair/([A-Za-z0-9]+)", html):
        if m.group(1) not in keys:
            keys.append(m.group(1))
    if not keys:
        log("首页没解析到活动链接，可能页面改版；请手动从浏览器复制 fair key")
        return
    rows = []
    for k in keys[: args.limit]:
        try:
            d = http_json(f"{API}/web/activities/fair?key={k}")
            for it in d.get("result") or []:
                rows.append({
                    "fair_key": it.get("key"),
                    "name": it.get("name"),
                    "date": it.get("display_date"),
                    "status": it.get("registration_status"),
                    "stops": [{"key": s.get("key"), "name": s.get("name"),
                               "registered_count": s.get("registered_count")}
                              for s in (it.get("stops") or [])],
                })
        except Exception as e:  # noqa: BLE001
            log(f"  {k} 读取失败: {e}")
        time.sleep(0.5)
    print(json.dumps(rows, ensure_ascii=False, indent=1))


def cmd_fetch(args):
    fair = http_json(f"{API}/web/activities/fair?key={args.fair_key}")
    items = fair.get("result") or []
    if not items:
        raise SystemExit("该 fair key 无数据")
    ev = items[0]
    stops = ev.get("stops") or []
    if args.stop_key:
        stops = [s for s in stops if s.get("key") == args.stop_key]
    log(f"活动：{ev.get('name')}（{ev.get('display_date')}），分会场 {len(stops)} 个")

    companies = {}
    seen_keys = set()
    for s in stops:
        skey = s.get("key")
        log(f"  拉取分会场 {s.get('name')}（{skey}）…")
        d = http_json(f"{API}/web/activity-stop/{skey}")
        jobs = (d.get("result") or {}).get("jobs") or []
        log(f"  岗位 {len(jobs)} 条")
        for j in jobs:
            if j.get("url_key") in seen_keys:
                continue
            seen_keys.add(j.get("url_key"))
            c = j.get("company") or {}
            name = (c.get("name") or "").strip()
            if not name:
                continue
            e = companies.setdefault(name, {
                "n": name,
                "i": (c.get("trade_text") or "").strip(),
                "sz": (c.get("person_text") or "").strip(),
                "ty": (c.get("type_text") or "").strip(),
                "addr": (c.get("address") or "").strip(),
                "d": (c.get("intro") or "").strip(),
                "hire": 0,
                "jobs": [],
            })
            e["jobs"].append({
                "k": j.get("url_key"),
                "j": (j.get("title") or "").strip(),
                "kk": (j.get("category_new_text") or "").strip(),
                "e": (j.get("education_text") or "").strip(),
                "n": j.get("posnum") or 0,
                "s": (j.get("salary") or "").strip(),
                "mj": "", "rq": "", "du": "", "ml": "",
            })
            e["hire"] += j.get("posnum") or 0
        time.sleep(0.6)

    out = {
        "event": {
            "name": ev.get("name"),
            "display_date": ev.get("display_date"),
            "fair_key": ev.get("key"),
            "stops": [{"key": s.get("key"), "name": s.get("name"),
                       "registered_count": s.get("registered_count")} for s in stops],
            "source_url": f"{BASE}/#/activity-single/fair/{ev.get('key')}",
            "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
        },
        "companies": list(companies.values()),
    }
    out["stats"] = {
        "companies": len(out["companies"]),
        "jobs": sum(len(c["jobs"]) for c in out["companies"]),
        "hire": sum(c["hire"] for c in out["companies"]),
        "registered": sum(s.get("registered_count") or 0 for s in stops),
    }
    write(out, args.out)
    log(f"完成：{out['stats']}")


def cmd_detail(args):
    data = json.load(open(args.infile, encoding="utf-8"))
    flat = [(c, j) for c in data["companies"] for j in c["jobs"] if j.get("k")]
    if args.limit:
        flat = flat[: args.limit]
    log(f"待补详情 {len(flat)} 条")

    done, fail = 0, []
    for i, (c, j) in enumerate(flat):
        if j.get("rq") or j.get("du"):
            done += 1
            continue
        try:
            d = http_json(f"{API}/web/job/{j['k']}", retries=2)
            r = d.get("result") or {}
            m = r.get("new_majors")
            majors = []
            if isinstance(m, dict):
                majors = [v for v in m.values() if v]
            elif isinstance(m, list):
                majors = [v for v in m if v]
            if not majors and r.get("major_text"):
                majors = [r["major_text"]]
            j["mj"] = "、".join(str(x).strip() for x in majors if str(x).strip())
            j["rq"] = (r.get("description") or "").strip()
            j["du"] = (r.get("duty") or "").strip()
            j["ml"] = (r.get("email") or "").strip()
            done += 1
        except Exception as e:  # noqa: BLE001
            fail.append((j["k"], str(e)))
            log(f"  失败 {j['k']}: {e}")
        if (i + 1) % 10 == 0:
            write(data, args.infile)
            log(f"  {i+1}/{len(flat)}  成功 {done} 失败 {len(fail)}")
        time.sleep(args.delay)
        if (i + 1) % 20 == 0:
            time.sleep(3)
    write(data, args.infile)
    log(f"详情完成：成功 {done}/{len(flat)}，失败 {len(fail)}")
    if fail:
        log("失败 key：" + ", ".join(k for k, _ in fail))


def write(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser(description="园区校园引才平台抓取器")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover", help="列出在挂的招聘活动")
    d.add_argument("--limit", type=int, default=6)
    d.set_defaults(func=cmd_discover)

    f = sub.add_parser("fetch", help="抓活动 + 企业 + 岗位")
    f.add_argument("--fair-key", required=True, help="如 kODEOpiI（从活动页 URL 取）")
    f.add_argument("--stop-key", help="只抓某个分会场")
    f.add_argument("-o", "--out", default="jobfair.json")
    f.set_defaults(func=cmd_fetch)

    t = sub.add_parser("detail", help="补抓 JD / 专业 / 邮箱")
    t.add_argument("--in", dest="infile", required=True)
    t.add_argument("--limit", type=int, default=0, help="只抓前 N 条（调试用）")
    t.add_argument("--delay", type=float, default=0.45, help="请求间隔秒，别低于 0.4（WAF）")
    t.set_defaults(func=cmd_detail)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
