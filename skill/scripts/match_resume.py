#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简历 → 岗位对口度打分

从简历纯文本里自动识别主攻技术簇，再给岗位逐条打分。不依赖特定人名/学校。

用法：
  python match_resume.py --jobs jobfair.json --resume resume.txt -o matched.json
  python match_resume.py --jobs jobfair.json --resume resume.txt --report
  python match_resume.py --jobs jobfair.json --primary backend,ai        # 手动指定主攻
  python match_resume.py --jobs jobfair.json --resume resume.txt --min-edu 本科

输出：原地写回每个岗位的 sc（1-5 分）与 w（一句理由），并打印统计。
sc=5 强对口 / 4 同方向 / 3 相关 / 2 弱相关 / 0 不对口
"""
import argparse
import collections
import json
import re
import sys

# ── 技术簇词表（小写匹配）────────────────────────────────────────────────
CLUSTERS = {
    "backend": [r"\bjava\b", r"spring", r"mybatis", r"juc", r"\bjvm\b", r"后端", r"服务端",
                r"微服务", r"springboot", r"spring cloud", r"mysql", r"redis", r"\bapi\b",
                r"dubbo", r"kafka", r"rabbitmq", r"并发", r"\bgo\b", r"golang"],
    "frontend": [r"前端", r"\bvue\b", r"\breact\b", r"javascript", r"typescript", r"html",
                 r"\bcss\b", r"小程序", r"vite", r"webpack", r"elementui", r"element-plus"],
    "ai": [r"\bagent\b", r"智能体", r"大模型", r"\bllm\b", r"\brag\b", r"\bmcp\b", r"prompt",
           r"机器学习", r"深度学习", r"pytorch", r"tensorflow", r"\bnlp\b", r"算法", r"推理",
           r"向量", r"langchain", r"transformer", r"微调", r"多模态"],
    "data": [r"数据分析", r"大数据", r"\bsql\b", r"hive", r"spark", r"etl", r"数据仓库", r"\bbi\b",
             r"数据挖掘", r"指标体系"],
    "embedded": [r"嵌入式", r"单片机", r"stm32", r"固件", r"驱动", r"rtos", r"freertos", r"\bmcu\b",
                 r"\nbsp\b", r"\bi2c\b", r"\bspi\b", r"裸机", r"\bcan\b"],
    "hardware": [r"硬件", r"电路", r"\bpcb\b", r"数电", r"模电", r"射频", r"\bfpga\b", r"电源",
                 r"电磁", r"信号完整性", r"原理图", r"\ballegro\b"],
    "chip": [r"半导体", r"芯片", r"ic设计", r"版图", r"封装", r"晶圆", r"光刻", r"刻蚀",
             r"工艺整合", r"\bpie\b", r"\bdft\b", r"良率", r"器件"],
    "testing": [r"测试", r"自动化测试", r"selenium", r"pytest", r"测试开发", r"用例", r"缺陷"],
    "mechanical": [r"机械", r"结构设计", r"模具", r"\bcad\b", r"solidworks", r"\bug\b", r"钣金",
                   r"热设计", r"流体", r"ansys", r"有限元"],
    "bio": [r"生物", r"细胞", r"分子", r"药理", r"制剂", r"发酵", r"纯化", r"\bpcr\b", r"蛋白"],
    "ops": [r"运维", r"网络工程", r"系统集成", r"技术支持", r"实施", r"\bdocker\b", r"kubernetes",
            r"\bk8s\b", r"linux"],
    "design": [r"ui设计", r"\bux\b", r"交互设计", r"平面设计", r"视觉设计", r"figma",
               r"sketch", r"作品集", r"工业设计", r"美工"],
    "sales": [r"销售", r"市场", r"商务", r"客户经理", r"外贸", r"营销"],
    "func": [r"人力", r"财务", r"会计", r"行政", r"法务", r"采购", r"供应链", r"管培", r"储备"],
}

# 相邻簇：命中这些算「同方向」，给 4 分
NEIGHBOR = {
    "backend": {"frontend", "data", "ai", "ops", "testing"},
    "frontend": {"backend", "data", "testing"},
    "ai": {"backend", "data", "testing"},
    "data": {"backend", "ai", "ops"},
    "embedded": {"hardware", "chip", "testing"},
    "hardware": {"embedded", "chip", "testing"},
    "chip": {"hardware", "embedded", "testing"},
    "testing": {"backend", "frontend", "embedded", "hardware", "chip", "ops"},
    "ops": {"backend", "testing", "data"},
    "mechanical": {"hardware"},
    "bio": set(),
    "sales": {"func"},
    "func": {"sales"},
}

# 岗位名命中的「泛技术词」——名字看不出方向时靠 JD 判
GENERIC = r"工程师|研发|开发|技术|产品|助理|专员|实习生|储备|管培"

VETO_NAME = r"销售|市场|商务|采购|财务|人事|行政|法务|客服|教师|讲师|管培|储备|职能|操作工|普工|技工|保安|司机|仓管"

# 方向否决：简历主攻不是这个领域时，岗位名里出现这些词直接判 0
VETO_BY_DIR = [
    (r"数字后端|版图|封装|晶圆|光刻|刻蚀|工艺整合|\bpie\b|\bdft\b|模拟ic|射频ic", "chip"),
    (r"机械|结构设计|模具|流体|液冷|热设计", "mechanical"),
    (r"生物|细胞|分子|药理|制剂|发酵|纯化", "bio"),
    (r"\bbim\b|建筑|土建|平面设计|视觉设计|\bui/ux\b|品牌|文案|内容创作|插画|美工|"
     r"工业设计|结构设计", "design"),
]


def hits(text, patterns):
    n = 0
    for p in patterns:
        if re.search(p, text, re.I):
            n += 1
    return n


def analyze_resume(text):
    """返回 {cluster: 命中次数}，按次数降序"""
    t = text.lower()
    scores = {c: hits(t, pats) for c, pats in CLUSTERS.items()}
    return collections.Counter({k: v for k, v in scores.items() if v > 0})


def score_job(job, primary, secondary, edu_ok):
    name = (job.get("j") or "").lower()
    jd = ((job.get("rq") or "") + "\n" + (job.get("du") or "")).lower()
    text = name + "\n" + jd

    if not text.strip():
        return 0, ""

    # 名称明显是销售/职能类，直接不对口
    if re.search(VETO_NAME, name) and not re.search(r"软件|开发|java|算法|数据|测试", name):
        return 0, ""

    # 方向否决
    for pat, need in VETO_BY_DIR:
        if need not in primary and re.search(pat, name):
            return 0, ""

    ch = {c: hits(text, pats) for c, pats in CLUSTERS.items()}
    name_hit = {c: hits(name, pats) for c, pats in CLUSTERS.items()}

    # 5 分：只给主攻方向
    for c in primary:
        if name_hit.get(c, 0) > 0:
            return 5, f"岗位名直接命中主攻方向（{c}）"
    for c in primary:
        if ch.get(c, 0) >= 2:
            return 5, f"JD 明确要求主攻方向（{c}）"
    # 4 分：主攻方向只沾一点，或次要方向命中
    for c in primary:
        if ch.get(c, 0) >= 1:
            return 4, f"JD 提到主攻方向（{c}）"
    for c in secondary:
        if name_hit.get(c, 0) > 0 or ch.get(c, 0) >= 2:
            return 4, f"命中次要方向（{c}）"
    # 3 分：与主攻相邻
    for c in primary:
        nb = NEIGHBOR.get(c, set())
        if any(name_hit.get(x, 0) > 0 for x in nb):
            return 3, "与你方向相邻的岗位"
    # 2 分：其它技术岗
    tech = ("backend", "frontend", "ai", "data", "embedded", "hardware", "chip", "testing", "ops")
    if any(name_hit.get(c, 0) > 0 for c in tech):
        return 2, "技术岗但与你的方向不同"
    if re.search(r"测试|技术支持|实施|运维", name):
        return 3, "测试 / 支持类，可作备选"
    return 0, ""


def edu_rank(e):
    e = e or ""
    if "博士" in e:
        return 3
    if "硕士" in e:
        return 2
    if "本科" in e:
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True, help="fetch_campus.py 输出的 json")
    ap.add_argument("--resume", help="简历纯文本（pdf/docx 先转 txt）")
    ap.add_argument("--primary", help="手动指定主攻方向，逗号分隔，如 backend,ai")
    ap.add_argument("--min-edu", default="本科", help="本人最高学历，低于岗位要求则降档")
    ap.add_argument("-o", "--out", help="输出路径，默认覆盖 --jobs")
    ap.add_argument("--report", action="store_true", help="打印对口清单")
    a = ap.parse_args()

    data = json.load(open(a.jobs, encoding="utf-8"))

    if a.primary:
        primary = [x.strip() for x in a.primary.split(",") if x.strip()]
        secondary = []
        print(f"主攻方向（手动）：{primary}", file=sys.stderr)
    else:
        if not a.resume:
            sys.exit("要么给 --resume，要么给 --primary")
        text = open(a.resume, encoding="utf-8", errors="replace").read()
        cnt = analyze_resume(text)
        if not cnt:
            sys.exit("简历里没识别出技术栈词，请用 --primary 手动指定")
        strong = [(c, n) for c, n in cnt.most_common() if n >= 3]
        if not strong:
            strong = cnt.most_common(1)
        primary = [c for c, n in strong[:2]]
        secondary = [c for c, n in strong[2:4]]
        print("简历技术簇命中：", dict(cnt.most_common()), file=sys.stderr)
        print(f"判定主攻：{primary}，次要：{secondary}", file=sys.stderr)

    my_edu = edu_rank(a.min_edu)
    stat = collections.Counter()
    hits_by_co = collections.defaultdict(int)

    for c in data["companies"]:
        for j in c["jobs"]:
            sc, why = score_job(j, primary, secondary, my_edu)
            if sc and edu_rank(j.get("e")) > my_edu:
                sc = max(1, sc - 2)
                why += "（要求硕士/博士，需冲刺）"
            j["sc"], j["w"] = sc, why
            if sc >= 3:
                stat[sc] += 1
                hits_by_co[c["n"]] += 1
            else:
                stat[0] += 1

    data.setdefault("stats", {})
    data["stats"].update({
        "match_primary": primary,
        "match_secondary": secondary,
        "match_5": stat[5], "match_4": stat[4], "match_3": stat[3],
        "match_co": len(hits_by_co),
    })

    out = a.out or a.jobs
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    print(f"\n对口岗位 {stat[5]+stat[4]+stat[3]} / {data['stats'].get('jobs', '?')}"
          f"（5分 {stat[5]} · 4分 {stat[4]} · 3分 {stat[3]}），涉及 {len(hits_by_co)} 家企业")
    print(f"输出：{out}", file=sys.stderr)

    if a.report:
        rows = []
        for c in data["companies"]:
            for j in c["jobs"]:
                if j.get("sc", 0) >= 3:
                    rows.append((j["sc"], j["j"], c["n"], j.get("e", ""), j.get("s", ""), j.get("w", "")))
        rows.sort(key=lambda x: (-x[0], x[2]))
        for r in rows:
            print(f"{r[0]} | {r[1][:30]:30s} | {r[2][:24]:24s} | {r[3]:4s} | {r[4]:11s} | {r[5]}")


if __name__ == "__main__":
    main()
