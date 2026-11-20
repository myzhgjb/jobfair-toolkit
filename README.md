# 招聘会岗位工具包 · jobfair-toolkit

把一场招聘会从"网上找信息"到"现场打勾投递"整条链路自动化：
**抓参会企业与岗位 JD → 按简历标对口度 → 生成可勾选可备注的单页清单 → 发布成手机可用的链接。**

仓库里同时放着 `skill/`——一套可直接复用的脚本和 Skill 定义，下次换一场招聘会，三条命令重跑即可。

## 在线预览

| 入口 | 地址 |
|---|---|
| GitHub Pages（长期有效） | **https://myzhgjb.github.io/jobfair-toolkit/** |
| WorkBuddy 托管 | https://szpark-jobfair.app.workbuddy.host/?sharecode=24WXRWZLBC |

手机浏览器打开 →「添加到主屏幕」，就是一个全屏、可离线使用的投递清单。

## 本次实例：2026-11-20 苏州工业园区秋季青年人才供需对接会（本地场）

| 指标 | 数值 |
|---|---|
| 参会企业 | 89 家（平台报名 92 家，其余 3 家未挂岗位） |
| 在招岗位 | 375 个 |
| 需求人数 | 2241 人 |
| 已抓 JD 全文 | 375 / 375（任职要求 + 岗位职责 + 专业要求 + HR 邮箱） |
| 时间地点 | 11-20 14:30–17:00，园区人才市场（旺墩路 168 号） |

数据全部来自苏州工业园区校园引才平台 `campus.o-hr.com` 的公开接口，**无需登录**。

### 页面做了什么

- **全部 89 家企业都在页面上**，对口企业置顶 + 左侧色条 + 「对口 N」徽章，不对口的往下翻也在，不会被隐藏
- 每家企业左侧一个 **23px 勾选框**，勾完整卡变绿，底部实时显示「已投 X / 89」
- 每家底部一个 **备注输入框**，边聊边记
- 岗位标签带 ★ 的是 ≥4 分对口岗，点「JD」展开任职要求 / 职责 / 专业 / HR 投递邮箱
- 左侧 20 类岗位导航（带计数），顶部行业 / 学历 / 投递状态筛选，搜索支持专业名
- 勾选与备注存 localStorage，刷新不丢；「导出记录」可复制成 Markdown

## 目录结构

```
.
├── 11.20园区招聘会-参会企业与岗位清单.html    # 主力产物（合并版）
├── 11.20园区招聘会-参会企业与岗位全库.html    # 纯浏览版（无匹配干扰）
└── skill/                                    # 可复用工具链
    ├── SKILL.md
    ├── scripts/
    │   ├── fetch_campus.py    # 园区平台：discover / fetch / detail
    │   ├── match_resume.py    # 简历 → 技术簇 → 岗位打分
    │   ├── build_page.py      # 归类 + 注入模板 → 单文件 HTML
    │   ├── fetch_91job.py     # 江苏高校 91job 平台
    │   └── parse_jobfair.py   # 招聘会 Excel 解析
    ├── assets/
    │   ├── warbook_template.html   # 投递清单模板（勾选/备注/导出）
    │   ├── library_template.html   # 全量库模板
    │   └── pwa/                    # 可添加到桌面的 PWA 壳
    └── references/
        ├── campus-platform-api.md  # 园区平台接口速查
        ├── sources-and-api.md      # 91job 接口速查
        └── taxonomy.md             # 20 类岗位归类词表
```

## 三条命令跑完一场招聘会

```bash
# 1) 列出平台上在挂的活动，拿 fair_key
python skill/scripts/fetch_campus.py discover

# 2) 抓活动 + 全部参会企业 + 岗位
python skill/scripts/fetch_campus.py fetch --fair-key kODEOpiI -o jobfair.json

# 3) 补 JD / 专业 / HR 邮箱（375 条约 4 分钟，断点续传）
python skill/scripts/fetch_campus.py detail --in jobfair.json

# 4) 按简历打分
python skill/scripts/match_resume.py --jobs jobfair.json --resume resume.txt --report

# 5) 生成单文件页面
python skill/scripts/build_page.py --in jobfair.json -o 投递清单.html \
  --event-name "2026 秋季双选会" --date "11月20日 14:30-17:00" \
  --place "园区人才市场" --profile "Java 后端 / AI Agent"
```

## 接口要点（踩过的坑）

| 坑 | 说明 |
|---|---|
| 详情接口没有列表批量 | JD 只能逐岗 `GET /api/web/job/{url_key}`，必须限速 0.45s，否则被 WAF 封 IP |
| `registered_count` ≠ 挂岗企业数 | 报名 92 家，实际挂岗 89 家。对外一律用接口实数 |
| `fair=` / `stop_key=` 过滤无效 | 加了也返回全平台 1265 条，必须直接打 `activity-stop/{stop_key}` |
| 平台把研发岗挂在"储备干部"类目 | 归类必须**岗位名优先于平台类别** |
| 「数字后端工程师」是 IC 物理设计 | 不是 Java 后端，匹配时须否决 |
| `new_majors` 有两种格式 | `{"0":"计算机"}` 和 `["计算机"]` 都要兼容 |

更多见 `skill/references/campus-platform-api.md`。

## 说明

- 岗位数据版权归各招聘企业，本仓库仅做信息聚合，供个人求职使用
- 对口度按简历自动打分，规则见页面顶部，仅供参考
- 本仓库不含本人的简历与联系方式；页面中出现的企业邮箱，是平台公示的**简历投递接收邮箱**，本身就是面向求职者公开的
