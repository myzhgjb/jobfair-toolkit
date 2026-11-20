#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 jobfair.json（已含匹配分）归类并渲染成单文件 HTML

  python build_page.py --in jobfair.json -o 招聘会-投递清单.html \
      --event-name "2026 秋季双选会" --date "11月20日 14:30-17:00" \
      --place "园区人才市场" --profile "Java 后端 / AI Agent" --degree 本科

产物：单文件、离线可开、手机可打勾、备注存 localStorage、可导出 Markdown。
"""
import argparse
import collections
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(os.path.dirname(HERE), "assets", "warbook_template.html")

CATS = ["测试 / 验证", "AI / 算法 / 数据", "嵌入式 / 软硬结合", "机器人", "电子 / 硬件 / 光电",
        "电气 / 自动化 / 控制", "芯片 / 半导体", "软件研发", "汽车 / 轨交 / 航空", "材料 / 化工",
        "生物医药 / 医疗", "机械 / 结构 / 设计", "工艺 / 制造 / 质量", "技术支持 / 售前售后",
        "项目管理", "销售 / 市场 / 商务", "职能 / 管培 / 人力", "教育 / 科研", "建筑 / 土木 / 工程",
        "其他 / 未注明"]
PRI = [2, 3, 3, 3, 2, 2, 2, 3, 2, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 0]

MAP = {
    "测试工程师": 0, "硬件测试": 0, "软件测试": 0, "测试开发": 0, "故障分析师": 0,
    "算法工程师": 1, "机器视觉": 1, "机器人算法": 1, "机器学习": 1, "深度学习": 1,
    "自然语言处理": 1, "数据分析师": 1,
    "嵌入式软件开发": 2, "嵌入式硬件": 4, "DSP开发": 4,
    "工业机器人工程师": 3, "机器人调试工程师": 3,
    "硬件工程师": 4, "电子技术研发工程师": 4, "电子工程师": 4, "电子工程设计": 4,
    "电器研发": 4, "汽车电子工程师": 4, "模拟版图工程师": 6,
    "电气工程师": 5, "自动化设计工程师": 5, "电机工程师": 5, "电控工程师": 5,
    "机电工程师": 5, "机电设备": 12,
    "集成电路IC设计": 6, "数字后端工程师": 6, "半导体技术": 6, "半导体设备工程师": 6,
    "半导体工艺工程师": 6, "封装工程师": 6, "工艺整合工程师（PIE）": 6,
    "芯片测试工程师": 6, "IC验证工程师": 6,
    "Java": 7, "C++": 7, "C#": 7, "C": 7, ".NET": 7, "全栈工程师": 7, "前端开发": 7,
    "软件研发工程师": 7, "运维工程师": 7, "网络信息安全工程师": 7, "系统集成": 7,
    "汽车机械工程师": 8, "汽车售后服务": 13,
    "化工研发": 9, "药物合成": 9, "化学分析": 9, "医药化学分析": 9, "材料工艺工程师": 9,
    "医疗器械研发": 10, "试剂研发": 10, "细胞培养技术员": 10, "计算机辅助药物设计": 10,
    "机械设计": 11, "机械工程师": 11, "机械结构工程师": 11, "模具设计": 11, "机械制图": 11,
    "工业设计": 11, "结构工程师": 11, "线路结构设计": 11, "UI设计师": 11,
    "机械工艺工程师": 12, "工艺/制程工程师": 12, "生产运营管理": 12, "生产计划管理": 12,
    "生产设备管理": 12, "生产主管/督导": 12, "普工/操作工": 12, "技工": 12, "机电技师": 12,
    "机械维修/保养": 12, "生产制造岗": 12, "质量管理/测试": 12, "QA工程师": 12, "QC质检": 12,
    "品控/品质主管": 12, "工程质量管理": 12, "供应商/采购质量管理": 12, "化验/检验": 12,
    "检验工程师": 12, "生产产品管理": 12, "生产项目工程师": 14, "设施工程师": 12, "品质分析岗": 12,
    "技术支持工程师": 13, "售后技术支持": 13, "客户服务工程师": 13, "现场应用工程师": 13,
    "FAE工程师": 13, "售后客服": 13, "客服专员": 13,
    "项目管理岗位": 14, "项目经理/主管": 14, "项目助理": 14, "项目专员": 14, "项目执行": 14,
    "电子/电器项目经理": 14,
    "销售工程师": 15, "销售顾问": 15, "大客户代表": 15, "汽车销售": 15, "保险顾问": 15,
    "证券经纪人": 15, "柜员": 15, "外贸业务员": 15, "市场推广": 15, "市场专员": 15,
    "市场运营": 15, "营销管理岗": 15, "短视频运营": 15, "视频编辑": 15, "买手": 15,
    "销售团队经理": 15,
    "管培生/培训生": 16, "储备干部": 16, "职能岗": 16, "采购专员/助理": 16, "供应商开发": 16,
    "财务专员/助理": 16, "人力资源专员/助理": 16, "HRBP": 16, "会计": 16, "关务专员": 16,
    "仓库管理员": 16, "生产物料管理（PMC）": 16, "产品经理": 16, "产品助理": 16,
    "运营助理/专员": 16,
    "科研人员": 17, "理科教师": 17, "战略研究": 17,
    "土木/土建工程师": 18, "建筑机电工程师": 18,
}

IND_FALLBACK = [
    (r"半导体|集成电路|电子技术", 6),
    (r"机械制造|机电|重工|装备|仪器|自动化|电气", 12),
    (r"制药|生物|医疗", 10),
    (r"互联网|计算机|软件", 7),
    (r"新能源", 12),
    (r"建筑|建材", 18),
    (r"科研|学术", 17),
    (r"物流|交通|贸易|快消|金融|基金|证券|保险", 16),
]

NAME_RULES = [
    (r"教师|讲师|教研|研究员|博士后|科研|助教|辅导员|实验员|青年科技人才", 17),
    (r"管培|培训生|储备|职能岗|人力|HRBP|行政|财务|会计|采购|关务|仓库|文员|人事助理|"
     r"行政助理|销售助理$|总经理助理|总经办助理|财务助理|物控助理|关务助理|项目助理|"
     r"运营助理|产品助理|商务助理", 16),
    (r"销售|市场|商务|营销|外贸|业务|客户经理|客服|运营|推广|视频|券|经纪|柜员|买手|BD", 15),
    (r"FAE|售后|技术支持|现场应用|客户服务|技术服务", 13),
    (r"项目经理|项目管理|项目专员|项目执行|项目工程师|项目助理", 14),
    (r"IC设计|版图|数字后端|数字前端|DFT|验证工程|芯片|半导体|封装|晶圆|制程整合|工艺整合|"
     r"PIE|光刻|刻蚀|电镜|SEM工程|TEM工程|FIB|Surface", 6),
    (r"测试|验证|可靠性|试验|失效分析|FA工程", 0),
    (r"算法|机器视觉|机器学习|深度学习|自然语言|数据|AI|智能体|大模型", 1),
    (r"嵌入式|单片机|驱动|固件|Firmware", 2),
    (r"机器人|具身|ROS|SLAM", 3),
    (r"硬件|电路|射频|模拟|PCB|电源|EMC|天线|光电|光学|光机|FPGA|电子|电器|传感", 4),
    (r"电气|自动化|PLC|控制|伺服|电机|变频|运动控制|机电|电控|调试", 5),
    (r"软件|后端|前端|全栈|Java|Web|服务端|程序员|Android|iOS|小程序|\.NET|C#|C\+\+|"
     r"Python|架构|SDK|运维|信息安全", 7),
    (r"汽车|整车|底盘|线束|三电|电池|NVH|悬架|制动|涂装|焊装", 8),
    (r"材料|高分子|配方|合成|聚合|涂料|电镀|表面处理|化学分析|化验|金相|热处理", 9),
    (r"临床|药理|毒理|注册|药政|试剂|细胞|发酵|纯化|生物|医学|药师|GMP|病理|制剂|医药", 10),
    (r"机械|结构|模具|机构|传动|钣金|暖通|热设计|仿真|CAE|有限元|工业设计|美工|数控|夹具", 11),
    (r"工艺|制程|生产|制造|装配|焊接|加工|注塑|冲压|铸造|精益|质量|品质|QE|QA|PMC|"
     r"标准化|操作工|技术员|质检|设备|维修|设施", 12),
    (r"土木|土建|施工|造价|建筑|市政|监理|工程管理", 18),
]


def classify(title, trade, pcat, coname=""):
    t = (title or "").strip()
    head = re.split(r"[（(]", t)[0]
    for pat, idx in NAME_RULES:
        if re.search(pat, head, re.I):
            return idx
    for pat, idx in NAME_RULES:
        if re.search(pat, t, re.I):
            return idx
    if pcat in MAP:
        return MAP[pcat]
    if re.search(r"纳米|半导体|微电子|集成电路|晶圆", coname):
        return 6
    for pat, idx in IND_FALLBACK:
        if trade and re.search(pat, trade):
            return idx
    return 19


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--event-name", default="")
    ap.add_argument("--date", default="")
    ap.add_argument("--place", default="")
    ap.add_argument("--profile", default="", help="简历方向标签，如 'Java 后端 / AI Agent'")
    ap.add_argument("--degree", default="本科")
    ap.add_argument("--site-key", help="localStorage 前缀，默认按活动名+日期生成；不同场次必须不同")
    a = ap.parse_args()

    data = json.load(open(a.infile, encoding="utf-8"))
    ev = data.get("event") or {}
    cos = data["companies"]

    for c in cos:
        for j in c["jobs"]:
            idx = classify(j["j"], c.get("i"), j.get("kk"), c["n"])
            j["c"] = idx
            j["p"] = PRI[idx]
            j.setdefault("sc", 0)
            j.setdefault("w", "")
        c["maxs"] = max([j.get("sc", 0) for j in c["jobs"]] or [0])
        c["nhit"] = sum(1 for j in c["jobs"] if j.get("sc", 0) >= 3)
        c["hire"] = sum(j.get("n") or 0 for j in c["jobs"])
        c["jobs"].sort(key=lambda x: (-x.get("sc", 0), -x.get("n", 0)))

    cos.sort(key=lambda c: (-c["maxs"], -c["nhit"], -c["hire"]))

    n_job = sum(len(c["jobs"]) for c in cos)
    n_hit = sum(1 for c in cos for j in c["jobs"] if j.get("sc", 0) >= 3)

    site_key = a.site_key
    if not site_key:
        base = (ev.get("fair_key") or ev.get("name") or "jobfair") + (ev.get("display_date") or "")
        site_key = "jf-" + re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5]", "", base)[:16]

    tpl = open(TPL, encoding="utf-8").read()
    payload = json.dumps({"cats": CATS, "pri": PRI, "co": cos}, ensure_ascii=False)
    html = (tpl
            .replace("__DATA__", payload.replace("</", "<\\/"))
            .replace("{{EVENT_NAME}}", a.event_name or ev.get("name") or "招聘会")
            .replace("{{EVENT_DATE}}", a.date or ev.get("display_date") or "")
            .replace("{{EVENT_PLACE}}", a.place or "以官方通知为准")
            .replace("{{PROFILE_LABEL}}", a.profile or "按简历标注")
            .replace("{{DEGREE}}", a.degree)
            .replace("{{SOURCE_URL}}", ev.get("source_url") or "")
            .replace("{{FETCHED_AT}}", ev.get("fetched_at") or "")
            .replace("{{REGISTERED}}", str((data.get("stats") or {}).get("registered") or ""))
            .replace("{{SITE_KEY}}", site_key)
            .replace("{{TOTAL_CO}}", str(len(cos))))
    open(a.out, "w", encoding="utf-8").write(html)
    print(f"企业 {len(cos)} / 岗位 {n_job} / 对口 {n_hit}")
    print(f"输出 {a.out}  {round(os.path.getsize(a.out)/1024)} KB")


if __name__ == "__main__":
    main()
