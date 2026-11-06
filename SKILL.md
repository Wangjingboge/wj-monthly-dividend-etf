---
name: wj-monthly-dividend-etf
version: "1.0.0"
display_name: 月月分红的ETF组合-望京博格版
display_name_en: Monthly Dividend ETF Portfolio (WJ Bogle Edition)
author: 望京博格
description: 构建「月月分红」的红利ETF组合，并测算每月现金流与三年收益。基于 Wind 数据，先统计A股红利ETF与港股红利ETF（扣20%港股通红利税）跟踪指数的股息率，再筛出近一年真正月月分红的红利ETF，按「分红次数、规模、指数去重、派息兑现率、税后股息率」五道规则选出5只跟踪指数不重复的标的，以100万本金算出未来三年每月分红，并用好/中/坏三种市场情景推演三年收益率，最后做14项数据自检并生成单文件网页报告。当用户要做红利ETF月月分红组合、算100万本金每月能收多少分红、比较A股与港股红利ETF税后股息率、推演红利组合三年收益、或需要一份可发布的红利ETF组合说明书时使用。
description_zh: 月月分红红利ETF组合。统计A股与港股红利ETF跟踪指数股息率（港股扣20%红利税），筛出近一年月月分红的红利ETF，用五道规则（分红次数≥11、规模≥2亿、指数去重、派息兑现率≥60%、税后股息率排序）选出5只跟踪指数不重复的标的，以100万本金测算未来三年每月分红，并按好/中/坏三情景推演三年收益率，输出14项自检与单文件网页报告。
description_en: Build a monthly-distributing dividend ETF portfolio from Wind data. Screens A-share and Hong Kong dividend ETFs by index dividend yield (HK net of 20% dividend tax), filters those actually distributing every month in the past year, selects 5 ETFs tracking distinct indices via five hard rules, then projects monthly cash flow and 3-year returns on RMB 1,000,000 under good/base/bad scenarios, with a 14-point data audit and a single-file HTML report.
agent_created: true
---

# 月月分红的ETF组合 · 望京博格版

> 作者：望京博格 ｜ 数据来源：**Wind**（需在 AI 平台配置 Wind MCP）

一条流水线，从全市场筛到 5 只 ETF，最后交出一份网页报告：

| 步骤 | 产物 | 说明 |
|---|---|---|
| 1 | `raw/*.json` | Wind 原始返回，原样存盘，不手工抄数 |
| 2 | `out/universe.json` | 候选池 + 每只的入选/剔除原因 |
| 3 | `out/portfolio.json` | 5 只持仓、月分红、三情景三年现金流 |
| 4 | `out/verify.json` | 14 项数据自检 |
| 5 | `out/report.html` | 单文件网页报告，无外部依赖 |

**这份 Skill 最重要的一句话：** 指数股息率高 ≠ 你能拿到分红。中间隔着费率、隔基金管理人的分配意愿。所以筛选里必须有「派息兑现率」这一道。

---

## 第 0 步：前置检查（不可跳过）

### Wind MCP

| MCP 服务 | 用途 | 用到的工具 |
|---|---|---|
| `wind-fund-data` | ETF 分红次数、单位分红、费率、规模、价格、业绩 | `search_funds`、`get_fund_price_indicators`、`get_fund_performance` |
| `wind-index-data` | 跟踪指数的股息率 TTM | `get_index_fundamentals` |
| `wind-economic-data` | 10 年期国债收益率 | `query_economic_indicator_data` |

工具不在可用列表里就先 `ToolSearch` 载入 schema，别凭记忆拼参数。

### 先确认日期

```bash
date +"%Y-%m-%d %A"
```

取最近一个已收盘交易日，后面所有数据以这一天为准，报告里写同一天。

---

## 第 1 步：取月月分红的 ETF 名单（最关键的一步）

**用这一句，能同时扫到 A股和港股（跨境）两类：**

```
search_funds(question="筛选近一年分红次数大于等于10次的ETF，返回Wind代码、证券简称、跟踪指数名称、近1年分红次数、近1年单位分红、管理费率、托管费率、上市基金规模_WIND计算、ETF一级投资范围分类")
```

返回里关键四列：`近1年分红次数` `近1年单位分红` `跟踪指数名称` `上市基金规模_WIND计算`。

> **坑 1**：不要写成「筛选名称包含红利的股票型ETF」——那样只能拿到 A股，港股红利 ETF 属 `跨境ETF`，是另一个分类。
> **坑 2**：不要加「且近一年分红次数≥8次」这类组合条件后再叠加名称条件，实测会返回「没找到数据」。**分红次数单独作为主条件最稳。**
> **坑 3**：阈值写 10 而不是 12。写 12 会漏掉「12 个月里分 11 次」的产品；写 10 是为了把 11 次的那几只捞出来，真正的门槛交给脚本按 11 卡。

存 `raw/etf_dividend.json`。

---

## 第 2 步：取指数股息率（分两次，A股和港股分开查）

### A股

```
get_index_fundamentals(question="查询以下指数的Wind代码、证券简称和股息率TTM：中证红利、上证红利、红利低波、红利低波100、沪深300红利、中证央企红利、上证国企红利、中证国企红利、标普中国A股大盘红利低波50、中证智选高股息策略")
```

### 港股（**必须用代码查，不能用名字**）

```
get_index_fundamentals(question="查询指数930914.CSI、931233.CSI、931722.CSI、930840.CSI、SPAHLVCP.SPI、HSSCHKY.HI、HSSCSOY.HI、HSMCHYI.HI、987016.CNI的证券简称与股息率TTM")
```

> **坑 4**：港股用中文名查（"中证港股通高股息投资指数"），Wind 会返回到成分股列表（一堆 `1398.HK` 工商银行），不是指数数据。**必须给代码。**
> **坑 5**：`红利低波` 会返回 `h30269.CSI`（全收益）。价格指数是 `H30269.CSI`，写报告用后者。
> **坑 6**：「筛选红利指数按股息率排序」这类写法一律别用，会吐出全收益/净收益/人民币/美元/CPR 各种版本。

存 `raw/index_yield_a.json`、`raw/index_yield_hk.json`，格式统一为 `{"columns":["code","name","yld"],"rows":[...]}`。

---

## 第 3 步：取价格、规模、业绩锚点（一次批量）

```
get_fund_price_indicators(windcode="520550.SH,510720.SH,561580.SH,159333.SZ,513530.SH,159209.SZ,159589.SZ,513630.SH,159581.SZ,513820.SH,159331.SZ,530880.SH,520810.SH", indexes="最新交易日,中文简称,最新成交价,最新净值,基金规模,上市日期")
```

规模返回单位是**元**，要除以 1e8 换成亿元。

业绩只用于给三情景找锚点，不参与分红测算：

```
get_fund_performance(question="查询XXXXXX、XXXXXX的近1年回报、近1年年化波动率、近1年最大回撤")
```

> **坑 7**：业绩要取「入选的那 5 只」，不是「你以为会入选的那 5 只」。选完再补取，别先取后选——会取错标的。

存 `raw/price.json`、`raw/performance.json`。

---

## 第 4 步：取十年期国债

```
query_economic_indicator_data(question="中国国债10年期到期收益率", observation=3)
```

用返回里最后一个交易日的值。`S0059749` 无权限时换 `M1001654`（查询语句里带「中国」两字能命中）。存 `raw/bond.json`。

---

## 第 5 步：跑脚本

```bash
SK=~/.workbuddy/skills/wj-monthly-dividend-etf/scripts

python $SK/build_universe.py \
  --dividend raw/etf_dividend.json \
  --yield raw/index_yield_a.json raw/index_yield_hk.json \
  --price raw/price.json --out out/universe.json

python $SK/build_portfolio.py \
  --universe out/universe.json --perf raw/performance.json --out out/portfolio.json

python $SK/verify.py \
  --universe out/universe.json --portfolio out/portfolio.json --out out/verify.json

python $SK/make_report.py \
  --universe out/universe.json --portfolio out/portfolio.json \
  --verify out/verify.json --bond 1.6474 --out out/report.html
```

`verify.py` 退出码非 0 就是有 FAIL，**报告不许直接发**，先查数据。

---

## 五道硬规则（改口径只改 `references/assumptions.json`）

| # | 规则 | 默认值 | 为什么 |
|---|---|---|---|
| R1 | 近一年分红次数 ≥ N | 11 | 12 个月最多允许缺 1 次，缺 2 次就不叫月月分红 |
| R2 | 只留场内 ETF | — | `01xxxx.OF` 联接基金不是跟踪标的，费率口径也不同 |
| R3 | 规模 ≥ X 亿 | 2.0 | 清盘红线 5000 万，太小进出会砸出折溢价 |
| R4 | 同指数只留一只 | 费率最低→规模最大 | 避免 5 只 ETF 买成同一个东西 |
| R5 | 派息兑现率 ≥ Y | 60% | 剔除「指数很能派、基金却不分」 |
| R6 | 按税后股息率取前 5 | 5 | 港股先扣 20% 红利税再排名 |

> **顺序不能换**：R3（规模）必须在 R4（去重）之前。
> 实测踩过：上国红利有两只 ETF，费率低的 0.55% 那只规模只有 0.46 亿，先去重会把它选成代表，然后它被规模门槛剔掉，**整条指数就凭空消失了**——而这条指数当时排第二。

---

## 数据口径（固定，不许改写）

```
指数股息率      = Wind 股息率TTM（成分股加权），单位 %
港股税后股息率  = 名义股息率 × (1 − 20%)       20% = 内地个人投资者港股通红利税率
综合费率        = 管理费率 + 托管费率
可持续派息率    = 税后股息率 − 综合费率        分红要先付管理费和托管费
派息兑现率      = 近12个月单位分红 / 现价 ÷ 可持续派息率
月分红          = 持有金额 × 可持续派息率 / 12
保守月分红      = 持有金额 × min(实际派息率, 可持续派息率) / 12
三年总收益      = (期末市值 − 投入 + 三年累计分红) / 投入
```

**为什么分红按"每份多少钱"算，不按"市值的百分比"算**：你买进去拿到的是固定份数，每份分红由成分股每股派息决定，跟股价涨跌无关。股价跌了，股息率是被动抬高的，**不是分红变多**。按"市值×股息率"算会把熊市里的分红算多，这是这类测算最常见的错。

**为什么可持续派息率要减费率**：成分股分红进入基金资产后，管理费和托管费先扣，剩下的才能分给你。不减费率等于凭空多算 0.2–0.6pp。

---

## 交付前自检（14 项，脚本自动跑）

1. 权重合计 = 100%
2. 逐只税后 / 可持续 / 派息率三项复算对得上
3. 月分红 = Σ(投入 × 可持续派息率 / 12)
4. 保守口径 ≤ 理论口径
5. 三情景三年分红与总收益复算
6. 5 只跟踪指数互不重复
7. 入选者分红次数 ≥ 11
8. 入选者规模 ≥ 2 亿
9. 港股税后 < 名义
10. 投入金额与权重一致（整手取整误差 < 1%）
11. 分红随情景单调（坏 ≤ 中 ≤ 好）
12. 剩余现金 = 本金 − 投入
13. 三情景年化公式与总收益自洽
14. 报告里所有数字均来自 JSON，无手写

**人眼还要再过一遍**：报告正文里出现的每个数字，都要能在 `portfolio.json` 里找到出处。凭印象写的数字，一定会和表里对不上。

---

## 常见坑

1. **凑不出 20 只就别凑**。2026-11-02 全市场近一年分红 ≥10 次的 ETF 只有 14 只，其中红利类 13 只、真正月月分红（≥11 次）12 只。用户要 20 只时，**按实际数量出报告并在正文第一段说明**，不要拿季度分红的红利 ETF 充数。
2. **港股 ETF 是跨境 ETF**，分类字段是 `跨境ETF`，跟 A股 `股票型ETF` 不是一类。
3. **同一指数有多个币种版本**（`港股通高股息(HKD)` / `港股通高股息CNY`），在 `index-aliases.json` 里映射到同一个 `code`，否则去重会失效。
4. **规模单位是元**，`2.61504e+09` 是 26.15 亿，不是 26 块。
5. **不要把「自由现金流」ETF 当红利**。它近一年也分 12 次，但分红来源和红利策略不是一回事，池子里标 `dividend: false` 剔除。
6. **派息兑现率会大于 100%**（实测有 167%、217% 的），说明当年分配里含资本利得或往期留存，不是可持续水平。模型取 min 封顶，但报告里要提示"去年分得多不代表明年也这么多"。
7. **ETF 分红 ≠ 投资者收益**。除息日净值等额下跌，分红是净值搬运。报告必须写这句，否则读者会以为白捡钱。

---

## 复用规则（避免重复取数）

| 用户新要求 | 该做什么 |
|---|---|
| 只改本金（100万 → 50万） | 不取数，`build_portfolio.py --capital 500000` 重跑 |
| 只改情景假设 | 改 `references/assumptions.json` 的 `scenarios`，重跑后两步 |
| 改成 3 只 / 8 只 | 改 `rules.top_n`，重跑 |
| 换一个交易日 | 分红次数、股息率、价格、业绩、国债全部重取 |
| 同一天再问一次 | `raw/` 和 `out/` 还在就直接重跑后两步 |

## 参考文件

- `references/assumptions.json`：五道规则的阈值 + 三情景假设（改口径只改这里）
- `references/index-aliases.json`：ETF 明细里「跟踪指数名称」→ 指数代码 + 市场 + 是否红利类
- `references/methodology.md`：公式推导、情景锚点、2026-11-02 回归基准
- `scripts/build_universe.py`：分红明细 + 股息率 + 价格 → 候选池（含剔除原因与漏斗）
- `scripts/build_portfolio.py`：候选池 → 5 只持仓 + 月分红 + 三情景
- `scripts/verify.py`：14 项自检，退出码即结论
- `scripts/make_report.py`：三份 JSON → 单文件 HTML 报告
- `sample/`：2026-11-02 的 Wind 原始返回，改脚本后先拿它跑一遍，结果要和 `methodology.md` 的回归基准对得上

## 运行环境

- Python 3.10+，仅用标准库（无需装包）
- 本机 `python` 不在 PATH 时用 `C:\Users\99388\.workbuddy\binaries\python\versions\3.13.12\python.exe`
- 中间文件放**当前工作区**（`raw/`、`out/`），不要写进 Skills 目录

## 已知边界

- 组合按月均摊展示现金流，**不是逐笔派息日历**：各 ETF 派息日分散在月中不同时点，实际到账日以基金公告为准
- 港股税后按 20% 单一税率折算；红筹股、REITs 实际税负可能更高，会让税后股息率再低 0.1pp 左右
- 情景假设是人为设定，锚定的是近一年价格波动，**测不出极端行情**
- ETF 分红政策可变，今天的兑现率不代表明天
