# -*- coding: utf-8 -*-
"""
91job 招聘会全量抓取：企业 → 岗位 → JD 正文。

用法：
  python fetch_91job.py --zphid 1000000000081511 --xxdm 10332 --work ./out all

  # 或分步（断点续传，随时可重跑）
  python fetch_91job.py --zphid ... --work ./out step1
  python fetch_91job.py --zphid ... --work ./out step2
  python fetch_91job.py --zphid ... --work ./out step3

产物（均在 --work 目录，纯 JSON）：
  step1_companies.json   参会企业
  step2_jobs.json        per-dwid 岗位列表
  step2b_details.json    per-dwid 企业详情（可选，step2b）
  step3_jd.json          per-zpgwid 完整 JD

⚠️ 站点有创宇盾 WAF，会按 IP 封禁。务必保持默认节流参数，且所有结果落盘续传。
   被封时返回的是 HTML 拦截页而非 JSON，脚本会自动退避；封禁通常几十分钟自动解除，
   期间不要换 UA / 换请求方式狂试（IP 级封禁，无效）。
"""
import argparse
import json
import os
import time

import requests

BASE = "https://usts.91job.org.cn"  # 其他学校换域名前缀，形如 https://<简称>.91job.org.cn


def build_session(zphid, xxdm, base):
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Content-Type": "application/json",
        "Origin": base,
        "Referer": base + "/sub-station/recruitmentDetail?zphid=" + zphid + "&xxdm=" + xxdm,
        "X-Requested-With": "XMLHttpRequest",
    })
    return s


def req(s, method, path, base, payload=None, params=None, tries=5):
    url = base + path
    for i in range(tries):
        try:
            r = s.post(url, json=payload, timeout=25) if method == "POST" \
                else s.get(url, params=params, timeout=25)
            txt = r.text.lstrip()
            if r.status_code == 200 and txt.startswith(("{", "[")):
                return r.json()
            print("  ! HTTP %s len=%d %s" % (r.status_code, len(r.text), path[:60]), flush=True)
        except Exception as ex:
            print("  ! ERR %s" % ex, flush=True)
        time.sleep(25 + i * 20)
        print("  ... retry %d" % (i + 1), flush=True)
    return None


def unwrap(res):
    """统一把各种返回结构解成 list。"""
    if not res:
        return []
    r = res.get("result", res)
    if isinstance(r, list):
        return r
    if isinstance(r, dict):
        for k in ("records", "rows", "list", "data", "items"):
            if isinstance(r.get(k), list):
                return r[k]
        for v in r.values():
            if isinstance(v, dict):
                for k in ("records", "rows", "list"):
                    if isinstance(v.get(k), list):
                        return v[k]
    return []


class Fetcher:
    def __init__(self, args):
        self.a = args
        os.makedirs(args.work, exist_ok=True)
        self.s = build_session(args.zphid, args.xxdm, args.base)

    def load(self, name, default=None):
        p = os.path.join(self.a.work, name)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        return default

    def save(self, name, obj):
        with open(os.path.join(self.a.work, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)

    def call(self, method, path, payload=None, params=None):
        return req(self.s, method, path, self.a.base, payload, params)

    def nap(self, i):
        time.sleep(self.a.gap)
        if i % self.a.pause_every == 0:
            time.sleep(self.a.pause)

    def step1(self):
        a = self.a
        res = self.call("POST", "/web/wsjysc/lbxq/getZphxqCzdwPageList",
                        {"zphid": a.zphid, "current": 1, "size": 500, "xxdm": a.xxdm})
        if not res:
            raise SystemExit("step1 FAILED（可能被 WAF 封 IP，稍后重跑）")
        r = res.get("result")
        print("[step1] 参会企业 %d 家 / total=%s" %
              (len(unwrap(res)), r.get("total") if isinstance(r, dict) else "?"), flush=True)
        self.save("step1_companies.json", res)

    def step2(self):
        a = self.a
        comps = unwrap(self.load("step1_companies.json"))
        cache = self.load("step2_jobs.json", {})
        print("[step2] 企业岗位列表：%d 家，已缓存 %d" % (len(comps), len(cache)), flush=True)
        for i, c in enumerate(comps, 1):
            dwid = c.get("dwid")
            if dwid in cache:
                continue
            res = self.call("POST", "/web/wsjysc/lbxq/getZphDwxqZwlbPageList",
                            {"current": 1, "id": dwid, "size": 100,
                             "zphid": a.zphid, "xxdm": a.xxdm})
            if res:
                cache[dwid] = res
                print("  %2d/%d %-28s %d 岗" %
                      (i, len(comps), c.get("dwmc", "")[:26], len(unwrap(res))), flush=True)
                self.save("step2_jobs.json", cache)
            else:
                print("  %2d/%d %s FAILED" % (i, len(comps), c.get("dwmc", "")), flush=True)
            self.nap(i)
        print("[step2] done, cached %d" % len(cache), flush=True)

    def step2b(self):
        a = self.a
        comps = unwrap(self.load("step1_companies.json"))
        cache = self.load("step2b_details.json", {})
        print("[step2b] 企业详情：%d 家" % len(comps), flush=True)
        for i, c in enumerate(comps, 1):
            dwid = c.get("dwid")
            if dwid in cache:
                continue
            res = self.call("GET", "/web/wsjysc/lbxq/getZphDwxq",
                            params={"dwid": dwid, "zphid": a.zphid})
            if res:
                cache[dwid] = res
                self.save("step2b_details.json", cache)
            self.nap(i)
        print("[step2b] done, cached %d" % len(cache), flush=True)

    def step3(self):
        a = self.a
        jobs = self.load("step2_jobs.json", {})
        cache = self.load("step3_jd.json", {})
        alljobs = []
        for dwid, res in jobs.items():
            for r in unwrap(res):
                alljobs.append(r)
        print("[step3] 岗位 JD：共 %d 岗，已缓存 %d" % (len(alljobs), len(cache)), flush=True)
        for i, r in enumerate(alljobs, 1):
            zpgwid = r.get("zpgwid")
            if not zpgwid or zpgwid in cache:
                continue
            res = self.call("GET", "/web/wsjysc/lbxq/getZpgwxq",
                            params={"zpgwid": zpgwid, "xxdm": a.xxdm})
            if res:
                cache[zpgwid] = res
                self.save("step3_jd.json", cache)
            if i % 25 == 0:
                print("  ... %d/%d cached=%d" % (i, len(alljobs), len(cache)), flush=True)
                time.sleep(4)
            self.nap(i)
        print("[step3] done, cached %d" % len(cache), flush=True)


def main():
    p = argparse.ArgumentParser(description="91job 招聘会全量抓取")
    p.add_argument("--zphid", required=True, help="招聘会 ID，见详情页 URL")
    p.add_argument("--xxdm", default="10332", help="学校代码，苏科大 10332 / 苏大 10285")
    p.add_argument("--work", required=True, help="输出目录")
    p.add_argument("--base", default=BASE, help="站点根地址")
    p.add_argument("--gap", type=float, default=0.45, help="请求间隔秒，别调小")
    p.add_argument("--pause-every", type=int, default=20)
    p.add_argument("--pause", type=float, default=3.0)
    p.add_argument("step", nargs="?", default="all",
                   choices=["all", "step1", "step2", "step2b", "step3"])
    a = p.parse_args()
    f = Fetcher(a)
    steps = ["step1", "step2", "step2b", "step3"] if a.step == "all" else [a.step]
    for st in steps:
        getattr(f, st)()
    print("DONE. JSON files in", a.work, flush=True)


if __name__ == "__main__":
    main()
