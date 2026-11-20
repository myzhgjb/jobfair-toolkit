# 园区校园引才平台（campus.o-hr.com）接口速查

> 2026-11-20 实测全通，**全部公开、无需登录**。苏州工业园区的校招/实习生岗位都在这套库里，
> 由新建元圆才运营。覆盖园区绝大多数官方招聘会（含"SIP 职通车"各条线）。

## 0. 先判断这场会是不是这个平台的

| 特征 | 说明 |
|---|---|
| 主办是园区人才办 / 新建元圆才 | 一定是，活动页形如 `campus.o-hr.com/#/activity-single/fair/<key>` |
| 学校自办的双选会（苏科大、苏大） | 通常不在，走 91job（见 `sources-and-api.md`） |
| 市级"校园苏州日" | 两边都可能有，先用数量级核对 |

判断方法：在平台首页看「引才活动」列表里有没有这一场。

## 1. 接口清单

| 用途 | 方法与地址 | 说明 |
|---|---|---|
| 活动详情 | `GET /api/web/activities/fair?key=<fair_key>` | 返回 `result[0]`，含 `name / display_date / stops[]`，每个 stop 有 `key` 和 `registered_count` |
| **本场企业 + 岗位** | `GET /api/web/activity-stop/<stop_key>` | `result.jobs[]`，一趟拿全，**这是主力接口** |
| **岗位详情（JD）** | `GET /api/web/job/<url_key>` | `description`（任职要求）/ `duty`（职责）/ `new_majors` / `email` |
| 平台全部岗位 | `GET /api/web/jobs?page=N` | 每页 15，`meta.last_page` 给总页数；**不带招聘会过滤** |

`fair_key` 从活动页 URL 取；`stop_key` 从 fair 接口的 `stops[].key` 取；
`url_key` 从 activity-stop 返回的 `jobs[].url_key` 取。

## 2. 岗位字段对照

列表接口（activity-stop）：
```
url_key  title  salary(如 12-18万)  monthsalary_min/max  month_num
posnum(招聘人数)  category_new_text(平台类别)  education_text(学历)
area  dept  posttime  overtime(截止)  fullpart_text
company{name, logo, person_text(规模), type_text(性质), trade_text(行业), intro, address}
```

详情接口（job/<url_key>）在此基础上多出：
```
new_majors(专业，dict 或 list 两种形态都要兼容)  major_text
description(任职要求)  duty(岗位职责)  email(HR 邮箱，未脱敏)
```

**详情接口是唯一 JD 来源**，列表接口没有。

## 3. 三个必须记住的坑

1. **`registered_count` ≠ 实际挂岗企业数。**
   官方推文爱写"上百家企业"，平台实数常常是报名 92、挂岗 89。
   对外一律用接口数字，别跟着宣传口径。

2. **详情要逐个请求，必须限速。**
   374 条按 0.45s 间隔跑约 4 分钟；每 20 条额外歇 3s。跑到 200 条以后偶发失败，
   重试 2 次基本能补上。结果**每 10 条落盘一次**，中断可续。

3. **`new_majors` 有两种格式**：`{"0":"计算机","1":"软件工程"}` 或 `["计算机","软件工程"]`。
   统一转 list 再 join，别直接当字符串用。

## 4. 已知不存在的接口（别浪费时间）

- `/api/web/activities/fair/{key}` → 404，只能 query 传参
- `/api/web/activities`、`/activities/fairs`、`/activities/fair/list` → 全 404
- `/api/web/jobs/{key}` → 404，详情是单数 `job`
- 给 `/api/web/jobs` 加 `fair=` / `stop_key=` 过滤 → 参数被忽略，永远返回全平台 1265 条

活动列表只能靠渲染首页 DOM 拿到 `#/activity-single/fair/<key>` 链接（`fetch_campus.py discover`）。

## 5. 地址

苏州工业园区人才市场：旺墩路 168 号 市场大厦（湖东行政中心广场）。
日常场次 8:30–12:00，专场多在 14:30–17:00。
