# 数据源与接口速查

> 2026-11-13 修订：**91job 岗位 JD 是可以公开反查的**（见 §2.3）。旧版本此处结论有误，已纠正。

## 1. 判断活动归属

| 活动类型 | 通常出现在哪 | 特征 |
|---|---|---|
| 学院 / 专业专场双选会 | 校就业网（91job）招聘会列表 | 企业 20-80 家，主办是学院，岗位高度集中在某专业 |
| 校级大型双选会 | 校就业网 + 校就业公众号 | 企业 200-400 家，主办是招生就业处 |
| 市级 / 区级综合场（如"校园苏州日"） | 市人才办、人社局公众号，独立平台（FlashOffer 等） | 企业 300+，主办是市委人才办，**校就业网往往查不到** |
| 行业专场（生物医药、纺织服装等） | 校就业网 + 学院公众号 | 名称里带行业 |
| 校级「双高协同」等小型定向专场 | 校就业网 91job | 企业 40-60 家，制造业/半导体占比高，软件开发岗稀少 |

**先用企业数量级和主办单位判断是哪一类，再决定去哪抓数据。**

## 2. 91job 智慧就业平台（江苏高校通用）

站点形如 `https://<学校简称>.91job.org.cn`，页面重定向到 `/sub-station/home/<学校代码>`。
前端是 Vue SPA，数据走 `/web/wsjysc/lbxq/` 下的 JSON 接口，**无需登录**。

### 2.1 接口清单（已验证）

| 用途 | 方法与地址 | 请求体 / 参数 |
|---|---|---|
| 招聘会列表 | `GET /web/wsjysc/wzsy/getLbsj?lmid=<栏目id>&row=14` | — |
| 招聘会详情 | `GET /web/wsjysc/lbxq/getZphxq/{zphid}` | — |
| 参会单位 | `POST /web/wsjysc/lbxq/getZphxqCzdwPageList` | `{"zphid":"...","current":1,"size":500}` |
| 单位详情 | `GET /web/wsjysc/lbxq/getZphDwxq` | `?zphid=...&dwid=...` |
| **企业在本场招聘会的岗位列表** | `POST /web/wsjysc/lbxq/getZphDwxqZwlbPageList` | `{"current":1,"id":"<dwid>","size":100,"zphid":"...","xxdm":"10332"}` |
| **岗位 JD 详情** | `GET /web/wsjysc/lbxq/getZpgwxq` | `?zpgwid=<岗位id>&xxdm=10332` |

`xxdm`：苏州大学 `10285`，苏州科技大学 `10332`。其他学校用 `/sub-station/home/<代码>` 里的代码。
详情页路由：`/sub-station/recruitment/meetingDetail?zphid=<id>` 或 `/sub-station/recruitmentDetail?zphid=<id>&xxdm=<代码>`。

### 2.2 四个必须记住的坑

1. **参会单位接口的分页参数是 `current` / `size`**，不是 `pageNum` / `pageSize`。
   传错不报错，永远返回第 1 页——会静默丢数据。判断方法：比对 `result.total` 与实际拿到条数。
2. **单位详情接口只接受 GET**，POST 返回 405。
3. **`POST /lbxq/getZpgwPageList` 不会按招聘会过滤**，返回的是全平台最新岗位，别用它凑数。
   要本场岗位必须走 `getZphDwxqZwlbPageList`，且 `id` 传的是参会单位表里的 `dwid`。
4. **WAF（创宇盾）会封 IP**。高频请求后返回 HTML 拦截页「您的 IP 最近有可疑的攻击行为」，
   表现为接口返回体不是 JSON。应对：请求间隔 ≥ 0.4s、每 20 次额外歇 3s、
   **全部结果落盘做断点续传**、403 后指数退避 25s 起。封禁通常几十分钟到几小时自动解除，
   期间不要狂试（换 UA / 换 GET / 换 form 都无效，是 IP 级封禁）。

### 2.3 全量岗位 JD 抓取链路（2026-11-13 跑通，48 家 / 126 岗）

```
getZphxqCzdwPageList ──▶ dwid 列表（含 dwmc / lxr / lxdh / 岗位名）
        │
        ├─▶ getZphDwxq            (可选) 企业行业/性质/规模/简介
        └─▶ getZphDwxqZwlbPageList  per dwid ──▶ zpgwid 列表
                                        │
                                        └─▶ getZpgwxq per zpgwid ──▶ 完整 JD
```

**`getZpgwxq` 返回字段**（这是全部 JD 的来源，别再依赖 Excel）：

| 字段 | 内容 |
|---|---|
| `zwmc` / `zwlb` | 岗位名 / 平台岗位类别 |
| `gwzz` | 岗位职责正文（HTML） |
| `rzzg` | 任职资格 |
| `zwms` | JSON 字符串，内含 `gwzz` 职责、`xzfl` 薪资福利 |
| `xlyq` / `yjnx` | 学历要求 / 年薪参考（万元） |
| `zprs` / `gzdd` / `zydm` | 招聘人数 / 工作地 / 专业要求 |
| `jljsyx` | HR 简历接收邮箱（**未登录时脱敏**，形如 `h*@synmatic.com`，域名仍可见） |

**邮箱诚实性**：脱敏邮箱保留原样，不要猜测补全；报告里要显式说明「平台脱敏」。

### 2.4 无头浏览器兜底

SPA 页面可用 `chrome --headless=new --dump-dom --virtual-time-budget=15000 <url>` 渲染；
若只需要校验生成的 HTML 是否渲染正常，用 `--dump-dom --virtual-time-budget=6000 file:///...` 再 grep 关键串，
比 Playwright 轻得多。

### 2.5 单位详情能拿到什么

```
dwmc 单位名称   dwxz 单位性质   dwhy 所属行业   dwgm 单位规模
dwjj 单位简介   dwdz 单位地址   dwlogo logo
```

`dwgm` 和 `dwhy` 恰好补上招聘会 Excel 最常缺的两列。有 `dwid` 后可以批量查，不必靠企业名人工比对。

## 3. 招聘会 Excel 的典型形态

- 单表 5-6 列：`单位名称 / 单位简介 / 岗位名称 / 专业要求 / 学历要求 / 需求人数`
- 单位名称是**合并单元格**，只有首行有值 → 必须向下填充
- 岗位名称一格里可能塞了 20 个岗位，用 `、，,;` 分隔，**括号内的逗号不能拆**
- 没有企业规模、没有岗位 JD、没有联系人、没有展位号

遇到这种表，页面里必须显式说明缺什么，并把"技术要求"标注为推断。
**若企业上了 91job，优先走 §2.3 拿真实 JD，不要用推断冒充。**

## 4. 其他可用来源

| 来源 | 能拿到 | 备注 |
|---|---|---|
| 学校就业公众号推文 | 活动时间线、场馆、进校门、交通、现场服务 | 常是唯一写清"几点在哪"的来源 |
| 本地宝 / 应届生求职网 | 宣讲会时间地点、部分参会名单 | 信息滞后，需与公众号核对 |
| 承办平台（FlashOffer 等） | 现场展位、扫码投递 | 多为小程序，公开网页抓不到 |
| 企业官网 / 招聘公众号 | 岗位 JD 正文 | 只对重点企业逐家补，别全量爬 |
