#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
招聘会岗位数据提取脚本
用法:
    python extract_jobs.py <招聘会.xlsx> [输出.json] [--kw 关键词1,关键词2,...]

功能:
    1. 读取招聘会 Excel（企业列表 sheet + 岗位列表 sheet，sheet 名模糊匹配）
    2. 岗位 sheet 的单位名称向下填充（处理合并单元格产生的空值）
    3. 输出结构化 JSON: {"companies": [...], "jobs": [...]}
    4. 可选 --kw: 按关键词在 职位名称/职责/专业 中命中并打印候选岗位清单（含展位号）

兼容: openpyxl（若默认 python 缺 openpyxl，依次尝试系统 python / venv）
"""
import sys, os, json, re, argparse

def find_col(header_row, keywords, default=None):
    """在表头行中按关键词模糊匹配列号（1-based）"""
    for c in range(1, header_row + 60 if header_row else 61):
        pass
    return default

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('xlsx')
    ap.add_argument('out', nargs='?', default='_raw_data.json')
    ap.add_argument('--kw', default=None, help='逗号分隔关键词，命中则打印候选清单')
    args = ap.parse_args()

    import openpyxl
    wb = openpyxl.load_workbook(args.xlsx, data_only=True)

    # ---- sheet 模糊匹配 ----
    ws_companies = ws_jobs = None
    for ws in wb.worksheets:
        t = ws.title
        if '企业' in t or '单位' in t:
            ws_companies = ws
        elif '岗位' in t or '职位' in t:
            ws_jobs = ws
    if ws_companies is None or ws_jobs is None:
        print('SHEETS:', [w.title for w in wb.worksheets], file=sys.stderr)
        sys.exit('ERROR: 找不到 企业列表/岗位列表 sheet')

    # ---- 企业列表: 展位号 / 专区 / 单位名称 ----
    hdr = [ws_companies.cell(row=1, column=c).value for c in range(1, ws_companies.max_column + 1)]
    def col_of(names, fallback):
        for i, h in enumerate(hdr):
            if h and any(k in str(h) for k in names):
                return i + 1
        return fallback
    c_booth = col_of(['展位'], 1)
    c_zone  = col_of(['专区', '分区', '区域'], 2)
    c_name  = col_of(['单位', '企业', '名称'], 3)

    companies = []
    for r in range(2, ws_companies.max_row + 1):
        name = ws_companies.cell(row=r, column=c_name).value
        if name:
            companies.append({
                'booth': ws_companies.cell(row=r, column=c_booth).value,
                'zone': ws_companies.cell(row=r, column=c_zone).value,
                'name': str(name).strip(),
            })

    # ---- 岗位列表: 表头自适应 ----
    jhdr = [ws_jobs.cell(row=1, column=c).value for c in range(1, ws_jobs.max_column + 1)]
    def jcol_of(names, fallback):
        for i, h in enumerate(jhdr):
            if h and any(k in str(h) for k in names):
                return i + 1
        return fallback
    J = {
        'seq':    jcol_of(['序号'], 1),
        'zone':   jcol_of(['分区', '专区'], 2),
        'comp':   jcol_of(['单位', '企业'], 3),
        'pos':    jcol_of(['职位名称', '岗位名称', '职位'], 4),
        'mail':   jcol_of(['邮箱', 'email'], 5),
        'cat':    jcol_of(['职位类别', '岗位类别'], 6),
        'major':  jcol_of(['大类', '专业'], 7),
        'duty':   jcol_of(['岗位职责', '工作职责', '职责'], 8),
        'req':    jcol_of(['任职', '要求'], 9),
    }

    jobs, cur = [], None
    for r in range(2, ws_jobs.max_row + 1):
        row = {ws_jobs.cell(row=1, column=c).value: ws_jobs.cell(row=r, column=c).value
               for c in range(1, ws_jobs.max_column + 1)}
        if not any(v for v in row.values()):
            continue
        comp = row.get(jhdr[J['comp'] - 1])
        if comp:
            cur = str(comp).strip()
        jobs.append({
            'row': r,
            'company': cur,
            'position': row.get(jhdr[J['pos'] - 1]),
            'email': row.get(jhdr[J['mail'] - 1]),
            'category': row.get(jhdr[J['cat'] - 1]),
            'major': row.get(jhdr[J['major'] - 1]),
            'duty': row.get(jhdr[J['duty'] - 1]),
            'req': row.get(jhdr[J['req'] - 1]),
        })

    data = {'companies': companies, 'jobs': jobs}
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print('companies:', len(companies), ' job rows:', len(jobs), ' ->', args.out)

    # ---- 可选: 关键词初筛 ----
    if args.kw:
        booth = {c['name']: c['booth'] for c in companies}
        kws = [k.strip() for k in args.kw.split(',') if k.strip()]
        pat = re.compile('|'.join(kws), re.I)
        print('\n===== 关键词候选岗位 =====')
        for j in jobs:
            if not j.get('position'):
                continue
            text = ' '.join(str(j.get(k) or '') for k in ('position', 'category', 'major', 'duty', 'req'))
            if pat.search(text):
                b = booth.get(j['company'], '?')
                print(f"{b:>4} | {j['company']} | {str(j['position'])[:60].replace(chr(10), ' / ')}")

if __name__ == '__main__':
    main()
