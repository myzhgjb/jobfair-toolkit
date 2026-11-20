#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
招聘会岗位表 → 可用的数据结构（供 assets/library_template.html 直接消费）

用法:
    python parse_jobfair.py 岗位需求.xlsx -o data.json
    python parse_jobfair.py 岗位需求.xlsx -o data.json --sheet "岗位列表"

分类是两级判定：
  第一级  岗位名称关键词（含大量通用职称的业务含义）
  第二级  名称看不出方向时，按【公司所属行业】兜底（汽车公司的"研发工程师"→ 汽车类）
只有两级都判不出来的才落到「其他 / 未注明」。

输出 JSON 结构:
    {"cats":[...], "pri":[...], "tpl":{...}, "var":{...}, "c":[{n,i,e,d,h,j:[{j,c,p,e,m,n,v}]}]}

依赖: openpyxl
"""
import argparse
import json
import re
import sys
from collections import Counter

# ---------------------------------------------------------------- 岗位类别
# (类别, 优先级, 关键词)  顺序 = 匹配优先级
CATS = [
    ('测试 / 验证', 2, ['测试', '验证', '可靠性', '试验', '失效分析', 'fa工程', 'efa']),
    ('AI / 算法 / 数据', 3, ['agent', '大模型', 'llm', 'ai应用', 'ai开发', 'ai工程', '人工智能', '算法',
                            '机器学习', '深度学习', '视觉', 'nlp', '数据开发', '大数据', '数据分析',
                            '数据挖掘', '智能体', '生成式', '模型', 'ai engineer', 'aigc', 'ai产品', 'ai训练', 'ai算法']),
    ('嵌入式 / 软硬结合', 3, ['嵌入式', '单片机', 'mcu', '驱动', 'bsp', '固件', 'firmware', '底层软件', '软硬']),
    ('机器人', 3, ['机器人', '具身', 'ros', 'slam', '运动规划', '灵巧手', '无人']),
    ('电子 / 硬件 / 光电', 2, ['硬件', '电路', '电子工程', '射频', '模拟', 'ic设计', 'pcb', '电源', 'emc',
                              '天线', '光电', '光学', 'layout', '版图', '传感', '芯片设计', '数字ic', '电子', 'fpga']),
    ('电气 / 自动化 / 控制', 2, ['电气', '自动化', 'plc', '控制', '伺服', '电机', '变频', '运动控制',
                                '仪控', 'dcs', '电控', '气动', '机电', '调试']),
    ('芯片 / 半导体', 2, ['半导体', '晶圆', '工艺整合', '封装', '封测', '良率', '光刻', '刻蚀', '薄膜',
                         'cmp', '电镜', 'tem', 'sem', '芯片类', '器件']),
    ('软件研发', 3, ['软件', '后端', '前端', '全栈', 'java', 'web', '服务端', '程序', 'app', 'android',
                    'ios', '小程序', '.net', 'c#', 'php', 'python开发', '平台软件', '云原生', 'sdk',
                    'it工程师', 'it类', '架构师']),
    ('汽车 / 轨交 / 航空', 2, ['机务', '总装', '标定', '整车', '底盘', '线束', '涂装', '焊装', '车身',
                              '总布置', '车辆', '三电', '电池包', 'nvh', '悬架', '制动']),
    ('材料 / 化工', 1, ['材料工程', '高分子', '配方', '合成', '聚合', '涂料', '电镀', '表面处理',
                       '化学分析', '化验', '金相', '热处理', '材料']),
    ('生物医药 / 医疗', 1, ['临床', '药理', '毒理', '注册', '药政', '试剂', '细胞', '发酵', '纯化',
                           '生物信息', '生信', '医学', '医师', '药师', '护理', '检验科', 'gmp',
                           '病理', '兽医', '专题负责人', '分析方法', '制剂']),
    ('机械 / 结构 / 设计', 1, ['机械', '结构', '模具', '机构', '传动', '钣金', '暖通', '热设计', '仿真',
                              'cae', '有限元', '设计工程师', '工业设计', '平面设计', '美工', '数控',
                              '磨削', '夹具', '工艺装备', '总体设计']),
    ('工艺 / 制造 / 质量', 1, ['工艺', '制程', '生产', '制造', '装配', '焊接', '加工', '注塑', '冲压',
                              '铸造', '精益', 'ie工程', '计划员', '设备', '质量', '品质', 'qe', 'qa',
                              'me工程', 'pe工程', 'pmc', '标准化', '作业员', '操作工', '技术员',
                              '品检', 'qc', '车间', '运行', '值班', '运维', '维修', '质检', '制版', '纱线', '打样']),
    ('技术支持 / 售前售后', 2, ['技术支持', '售前', '售后', '技术服务', '应用工程', '技术工程',
                               '现场支持', 'fae']),
    ('项目管理', 1, ['项目管理', '项目经理', '项目专员', '项目助理', '项目工程', '现场工程师']),
    ('销售 / 市场 / 商务', 0, ['销售', '市场', '商务', '客户经理', '外贸', '业务', '渠道', 'bd',
                              '招商', '营销', '品牌', '电商', '行销', '视频剪辑', '广告优化', '置景', '新媒体']),
    ('职能 / 管培 / 人力', 0, ['管培', '培训生', '储备', '人力', '行政', '财务', '会计', '法务', '采购',
                              '供应链', '物流', '文员', '秘书', '总助', '总经理助理', '运营', '人事',
                              '招聘', '综合管理', '职能类', '总经理助理', '人事助理', '行政助理', '销售助理', '猎头',
                              '版师', '营运', '企划', '职能', '产品经理', '投资', '资产管理']),
    ('教育 / 科研', 0, ['教师', '讲师', '教研', '研究员', '博士后', '科研', '编辑', '研究', '助教',
                       '辅导员', '实验员']),
    ('建筑 / 土木 / 工程', 1, ['施工', '造价', '土建', '结构工程', '轨道', '巡检', '市政', '监理', '工程管理']),
]
EDU_WORDS = ['教师', '讲师', '研究员', '博士后', '科研', '教研', '助教', '辅导员']
SUBJECTS = ['语文', '数学', '英语', '物理', '化学', '生物', '政治', '历史', '地理', '科学',
            '音乐', '美术', '体育']

OTHER = '其他 / 未注明'

# ---------------------------------------------------------------- 企业行业
IND = [
    ('汽车/轨交/航空', ['汽车', '汽配', '车辆', '轨交', '轨道交通', '航空', '航天', '船舶', '机车']),
    ('材料/化工', ['材料', '高分子', '塑业', '化工', '涂料', '化学', '聚合物', '碳纤维', '树脂', '新材',
                  '橡胶', '玻璃', '陶瓷']),
    ('半导体/集成电路', ['半导体', '集成电路', '芯片', '晶圆', '微电子', '封测', '光刻', '封装']),
    ('生物医药/医疗器械', ['医药', '制药', '药业', '生物', '医疗', '器械', '临床', '诊断', '疫苗', '益生菌']),
    ('电子信息/通信', ['电子', '通信', '光电', '显示', '传感', '雷达', '天线', '线路板', '连接器', '电器']),
    ('新能源/新材料', ['新能源', '光伏', '锂电', '电池', '储能', '能源']),
    ('软件/互联网/AI', ['软件', '信息技术', '网络科技', '数据', '人工智能', '智能科技', '互联网', '数字']),
    ('高端装备/机器人', ['装备', '机器人', '自动化', '机床', '精密', '机械', '传动', '电机', '激光',
                        '焊接', '重工', '精工', '智能设备', '仪器']),
    ('教育/学校', ['学校', '中学', '小学', '大学', '学院', '教育', '培训', '幼儿园', '职业技术']),
    ('金融/投资/保险', ['银行', '证券', '保险', '期货', '基金', '投资', '资管', '金融', '信托']),
    ('国企/城投/物流', ['控股集团', '城投', '国资', '物流', '港口', '交通', '建设集团', '开发集团']),
    ('医院/科研院所', ['医院', '研究所', '研究院', '实验室', '检测', '计量', '检验']),
    ('建筑/土木', ['建筑', '装饰', '市政', '监理', '勘察', '设计院']),
]

IND2CAT = {
    '半导体/集成电路': '芯片 / 半导体',
    '材料/化工': '材料 / 化工',
    '新能源/新材料': '工艺 / 制造 / 质量',
    '电子信息/通信': '电子 / 硬件 / 光电',
    '汽车/轨交/航空': '汽车 / 轨交 / 航空',
    '高端装备/机器人': '机械 / 结构 / 设计',
    '生物医药/医疗器械': '生物医药 / 医疗',
    '软件/互联网/AI': '软件研发',
    '教育/学校': '教育 / 科研',
    '医院/科研院所': '生物医药 / 医疗',
    '金融/投资/保险': '职能 / 管培 / 人力',
    '国企/城投/物流': '职能 / 管培 / 人力',
    '建筑/土木': '建筑 / 土木 / 工程',
    '其他/综合': OTHER,
}

TPL = {
    '软件研发': ['接口与业务系统开发、前后端联调、代码评审与上线维护。',
                ['Java / Python / C# 之一', 'Spring Boot、MyBatis 等框架', 'MySQL 索引与 SQL 优化', 'Redis / MQ', 'RESTful 接口与 Git']],
    'AI / 算法 / 数据': ['模型训练与调优、数据处理、算法落地到业务。',
                        ['Python', 'PyTorch / TensorFlow', '机器学习 / 深度学习', 'Pandas / NumPy', '论文复现']],
    '嵌入式 / 软硬结合': ['MCU/SoC 固件开发、驱动移植、软硬件联调。',
                        ['C / C++', 'STM32 或 ARM', 'RTOS / Linux 驱动', 'UART / I2C / SPI / CAN', '示波器与逻辑分析仪']],
    '机器人': ['运动控制、感知规划算法、整机联调。',
              ['C++ / Python', 'ROS / ROS2', 'SLAM 或运动规划', 'PID 调参', '传感器标定']],
    '电子 / 硬件 / 光电': ['原理图与 PCB 设计、硬件调试、量产导入。',
                          ['模拟 / 数字电路', 'Altium / Cadence', '电源与 EMC', '器件选型', '示波器 / 频谱仪']],
    '电气 / 自动化 / 控制': ['电气系统设计、控制程序编写、现场调试。',
                            ['PLC（西门子 / 三菱）', '伺服 / 变频调试', 'EPLAN 电气图', '组态 / SCADA', '现场调试']],
    '芯片 / 半导体': ['器件工艺、版图或封测环节的技术工作。',
                     ['半导体器件物理', '光刻 / 刻蚀 / 薄膜', '版图与 EDA', '良率与 SPC', '洁净室规范']],
    '测试 / 验证': ['测试方案、用例编写、缺陷跟踪与回归。',
                   ['测试用例设计', '自动化测试（Python）', '万用表 / 示波器', '缺陷管理', '可靠性试验']],
    '汽车 / 轨交 / 航空': ['整车/部件设计验证、总装工艺、标定与试验。',
                          ['CATIA / UG', '整车或部件结构', 'CAN 总线 / 标定', '总装工艺', '法规与试验标准']],
    '材料 / 化工': ['配方与工艺开发、材料表征、量产转化。',
                   ['材料学基础', '配方设计', 'DSC / FTIR / SEM 表征', 'DOE 试验设计', '中试放大']],
    '生物医药 / 医疗': ['研发、注册、质量或临床相关工作。',
                       ['药理 / 病理基础', 'GMP 与法规', '实验操作', '数据记录规范', '英文文献阅读']],
    '机械 / 结构 / 设计': ['结构方案、三维建模、公差与可制造性评估。',
                          ['SolidWorks / Creo', '公差配合 GD&T', '材料与热处理', '强度校核', 'DFM']],
    '工艺 / 制造 / 质量': ['产线工艺制定、良率提升、质量体系与异常处理。',
                          ['SMT / 装配 / 焊接', 'DOE / SPC / FMEA', '8D 分析', '产线异常处理', 'ISO9001 / IATF16949']],
    '技术支持 / 售前售后': ['客户技术问题对接、方案讲解、现场支持。',
                            ['产品原理与方案', '需求转化', '现场排障', '技术文档与培训', '适应出差']],
    '项目管理': ['进度、成本、风险与跨部门协调。',
                ['项目计划', '跨部门协调', '成本与风险', 'PMP / IPD', '文档与汇报']],
    '销售 / 市场 / 商务': ['客户开发、方案报价、渠道维护。',
                          ['客户开发与谈判', '行业与产品知识', '报价与合同', 'CRM', '适应出差']],
    '职能 / 管培 / 人力': ['职能支持或轮岗培养，偏综合能力。',
                          ['沟通协调', 'Excel / 数据分析', '公文与汇报', '流程制度', '学习能力']],
    '教育 / 科研': ['教学、教研或科研辅助工作。',
                   ['学科功底', '教师资格证', '教研与课程设计', '论文 / 项目', '表达能力']],
    '建筑 / 土木 / 工程': ['施工管理、造价或现场技术。',
                          ['施工图识图', '造价软件', '现场管理', '验收规范', 'CAD / 广联达']],
    OTHER: ['岗位方向未在名称中注明，需现场确认具体职责。',
            ['专业基础', '学习能力', '沟通协作', '相关实习']],
}
VAR = {
    1: ['智能体编排、工具调用、知识库检索与效果评测。',
        ['Python', 'LangChain / LlamaIndex', 'RAG 与向量库', 'Prompt 工程', 'Function Calling / MCP']],
    2: ['页面与组件开发、状态管理、接口联调与性能优化。',
        ['HTML / CSS / JavaScript', 'Vue 3 或 React', '组件化与状态管理', 'Axios 联调', 'Vite / Webpack']],
    3: ['服务端接口开发、数据库设计、并发与性能优化。',
        ['Java + Spring Boot', 'MySQL 设计优化', 'Redis 缓存', '消息队列', 'Docker 部署']],
    4: ['数据管道搭建、清洗建模、指标看板。',
        ['SQL / Hive', 'Python 数据处理', 'ETL 与数仓分层', '指标体系', 'BI 可视化']],
}

HEADER_MAP = {
    '单位名称': 'co', '企业名称': 'co', '公司名称': 'co', '用人单位': 'co', '招聘单位': 'co',
    '单位简介': 'intro', '企业简介': 'intro', '公司简介': 'intro', '单位介绍': 'intro',
    '岗位名称': 'job', '职位名称': 'job', '招聘岗位': 'job', '岗位': 'job', '职位': 'job',
    '专业要求': 'major', '专业': 'major', '需求专业': 'major',
    '学历要求': 'edu', '学历': 'edu',
    '需求人数': 'num', '招聘人数': 'num', '人数': 'num', '计划人数': 'num',
}


def norm(x):
    return re.sub(r'\s+', ' ', str(x)).strip() if x is not None else ''


def split_out(t):
    """按分隔符拆岗位；括号内的不拆。"""
    out, buf, depth = [], [], 0
    for ch in t:
        if ch in '（(【[':
            depth += 1
            buf.append(ch)
        elif ch in '）)】]':
            depth = max(0, depth - 1)
            buf.append(ch)
        elif ch in '、，,;；\n' and depth == 0:
            s = ''.join(buf).strip()
            if s:
                out.append(s)
            buf = []
        else:
            buf.append(ch)
    s = ''.join(buf).strip()
    if s:
        out.append(s)
    return [x for x in out if len(x) >= 2 and not re.fullmatch(r'[（(].*[）)]', x)]


def ind_of(name, intro):
    """企业行业：先看名称里的强特征，再按名称/简介加权打分。"""
    # ① 名称强特征，避免"中国科学院…研究所"被"学院"抢走、"大飞机研究中心"被"研究"抢走
    if any(k in name for k in ['飞机', '航空', '航天', '船舶', '轨交', '轨道交通', '汽车', '汽配', '机车']):
        return '汽车/轨交/航空'
    if any(k in name for k in ['研究所', '研究院', '研究中心', '科学院']) and '职业技术' not in name:
        return '医院/科研院所'
    if any(k in name for k in ['学校', '中学', '小学', '大学', '学院', '职业技术', '幼儿园', '教育', '培训']):
        return '教育/学校'

    # ② 加权打分：名称命中优先于简介命中
    best, best_key = '其他/综合', (0, 0)
    for nm, kws in IND:
        nh = sum(1 for k in kws if k in name)
        ih = sum(1 for k in kws if k in intro[:120])
        key = (nh, nh * 3 + ih)
        if key > best_key:
            best, best_key = nm, key
    return best


def cat_of(name, industry=None):
    """两级判定：先看岗位名，看不出方向再按企业行业兜底。"""
    t = name.lower().replace(' ', '')

    # ① 教师 / 科研 / 科目名
    if any(k in t for k in EDU_WORDS):
        return '教育 / 科研', 0
    if any(t.startswith(s) or t == s for s in SUBJECTS):
        return '教育 / 科研', 0

    # ② 名称关键词：先括号前主干，再全名
    head = re.split(r'[（(]', name)[0].strip().lower().replace(' ', '')
    for c, pri, kws in CATS:
        if any(k in head for k in kws):
            return c, pri
    for c, pri, kws in CATS:
        if any(k in t for k in kws):
            return c, pri

    # ③ 笼统职称 → 按企业行业兜底
    if industry:
        target = IND2CAT.get(industry)
        if target and target != OTHER:
            return target, dict((c, p) for c, p, _ in CATS).get(target, 0)
        # 行业判不出，但明显是研发/技术岗 → 归工艺制造，别留在"其他"
        if any(k in t for k in ['研发', '工程师', '技术', '设计']):
            return '工艺 / 制造 / 质量', 1

    return OTHER, 0


def variant(cat, name):
    low = name.lower()
    if any(k in low for k in ['agent', '智能体', '大模型', 'llm']):
        return 1
    if cat == '软件研发':
        if '前端' in name or 'web' in low:
            return 2
        if '后端' in name or 'java' in low:
            return 3
    if cat == 'AI / 算法 / 数据' and '数据' in name:
        return 4
    return 0


def size_of(intro):
    pats = [r'员工\s*(?:人数)?\s*(?:超过|达|近|约)?\s*([0-9]+)\s*余?\s*人',
            r'现有[^。，,]{0,8}?([0-9]+)\s*余?\s*(?:名|人)员工',
            r'([0-9]+)\s*余?\s*名\s*员工',
            r'职工\s*([0-9]+)\s*余?\s*人']
    for p in pats:
        m = re.search(p, intro[:400])
        if m:
            n = int(m.group(1))
            if 5 <= n <= 500000:
                return n
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('xlsx')
    ap.add_argument('-o', '--out', default='data.json')
    ap.add_argument('--sheet', default=None, help='sheet 名，默认第一个')
    args = ap.parse_args()

    try:
        import openpyxl
    except ImportError:
        sys.exit('缺少 openpyxl。用 workbuddy 的 excel_env python：\n'
                 '  C:/Users/<你>/.workbuddy/binaries/python/envs/excel_env/Scripts/python.exe parse_jobfair.py ...')

    wb = openpyxl.load_workbook(args.xlsx, data_only=True)
    ws = wb[args.sheet] if args.sheet else wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))

    hi, best, cols = 0, 0, {}
    for i, r in enumerate(rows[:5]):
        m = {}
        for k, cell in enumerate(r):
            key = HEADER_MAP.get(norm(cell))
            if key and key not in m.values():
                m[k] = key
        if len(m) > best:
            hi, best, cols = i, len(m), m
    if not cols:
        sys.exit('没识别到表头，请检查列名是否包含 单位名称/岗位名称/专业要求 等')
    idx = {v: k for k, v in cols.items()}
    print(f'表头在第 {hi+1} 行，识别到列：{ {k: v for k, v in cols.items()} }')

    comps, cur = [], None
    for r in rows[hi + 1:]:
        g = lambda key: norm(r[idx[key]]) if key in idx and idx[key] < len(r) else ''
        name, intro = g('co'), g('intro')
        job, major, edu, num = g('job'), g('major'), g('edu'), g('num')
        if name and (cur is None or name != cur['n']):
            cur = {'n': name, 'd': intro, 'jobs': []}
            comps.append(cur)
        if not job or cur is None:
            continue
        cur['jobs'].append({'j': job, 'm': major, 'e': edu, 'c': num})
        if intro and not cur['d']:
            cur['d'] = intro

    merged = {}
    for c in comps:
        t = merged.setdefault(c['n'], {'n': c['n'], 'd': c['d'], 'jobs': []})
        t['jobs'] += c['jobs']
        if not t['d'] and c['d']:
            t['d'] = c['d']
    comps = list(merged.values())

    cats = [x[0] for x in CATS] + [OTHER]
    cid = {c: i for i, c in enumerate(cats)}
    pri = {c: p for c, p, _ in CATS}
    pri[OTHER] = 0

    out, cnt = [], Counter()
    for c in comps:
        ind = ind_of(c['n'], c['d'])
        jobs = []
        for j in c['jobs']:
            for k, nm in enumerate(split_out(j['j']) or [j['j']]):
                cat, p = cat_of(nm, ind)
                jobs.append({'j': nm, 'c': cid[cat], 'p': p, 'e': j['e'],
                             'm': j['m'][:80], 'n': j['c'] if k == 0 else '',
                             'v': variant(cat, nm)})
                cnt[cat] += 1
        hire = sum(int(re.findall(r'\d+', x['n'])[0]) for x in jobs
                   if x['n'] and re.findall(r'\d+', x['n']))
        out.append({'n': c['n'], 'i': ind, 'e': size_of(c['d']),
                    'd': c['d'][:260], 'h': hire, 'j': jobs})

    data = {'cats': cats, 'pri': [pri[x] for x in cats], 'tpl': TPL, 'var': VAR, 'c': out}
    json.dump(data, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

    total = sum(cnt.values())
    print(f'\n企业 {len(out)} 家 · 岗位 {total} 条')
    for k, v in cnt.most_common():
        print(f'  {k:<22s}{v:>5d}  {v*100//total:>2d}%')
    emp = sum(1 for c in out if c['e'])
    print(f'\n企业规模可从简介提取：{emp}/{len(out)}；其余为「规模未披露」')
    print(f'重点岗位（优先级 3）：{sum(1 for c in out for j in c["j"] if j["p"]==3)}')
    print('行业分布：')
    for k, v in Counter(c['i'] for c in out).most_common():
        print(f'  {k:<20s}{v}')
    print(f'\n已写出 {args.out}')


if __name__ == '__main__':
    main()
