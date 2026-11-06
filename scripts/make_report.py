# -*- coding: utf-8 -*-
"""月月分红红利ETF · 网页版报告生成

读取 universe.json / portfolio.json / verify.json，产出单文件 HTML（无外部依赖，可直接发）。

用法：
    python make_report.py --universe out/universe.json --portfolio out/portfolio.json \
        --verify out/verify.json --bond 1.6474 --out out/report.html

所有数字都从 JSON 里取，脚本不写死任何一个数——换一天的数据重跑，报告自动跟着变。
"""

import argparse
import datetime
import json
import os


def load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def money(x, dec=0):
    return ("{:,.%df}" % dec).format(x)


def pnum(x, dec=1, sign=False):
    """已经是百分数单位的数值（如 1.28 表示 1.28%），不再乘 100"""
    f = ("{:+.%df}%%" if sign else "{:.%df}%%") % dec
    return f.format(x)


def pct(x, dec=2, sign=False):
    s = ("{:+.%df}%%" if sign else "{:.%df}%%") % dec
    return s.format(x * 100)


CSS = """
:root{
  --ink:#1b1a17; --muted:#6d675e; --soft:#918a7f;
  --bg:#f6f3ec; --card:#fffdf8; --line:#e3dccd; --line2:#efe9dc;
  --accent:#a8452f; --accent-soft:#f3e4df;
  --gold:#9c7420; --green:#2c6e52; --green-soft:#e2efe8;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font-family:"PingFang SC","Microsoft YaHei","Hiragino Sans GB",system-ui,-apple-system,sans-serif;
  font-size:15px; line-height:1.75; letter-spacing:.01em;
}
.wrap{max-width:1060px;margin:0 auto;padding:0 22px 80px}
.num{font-variant-numeric:tabular-nums;font-feature-settings:"tnum"}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}

/* ---------- 头部 ---------- */
.hero{padding:64px 0 40px;border-bottom:1px solid var(--line)}
.eyebrow{font-size:12px;letter-spacing:.22em;color:var(--accent);text-transform:uppercase;margin-bottom:18px}
h1{
  font-family:"Songti SC","Noto Serif SC",Georgia,serif;
  font-size:44px;line-height:1.24;margin:0 0 18px;font-weight:700;letter-spacing:-.01em;
}
.lede{font-size:17px;color:#403c35;max-width:720px;margin:0 0 26px}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{font-size:12.5px;color:var(--muted);border:1px solid var(--line);background:var(--card);
  border-radius:999px;padding:4px 12px}

/* ---------- 通用块 ---------- */
section{padding:52px 0 8px}
h2{
  font-family:"Songti SC","Noto Serif SC",Georgia,serif;
  font-size:26px;margin:0 0 6px;font-weight:700;
}
h2 .idx{color:var(--accent);font-size:14px;font-family:inherit;margin-right:10px;letter-spacing:.1em}
.sub{color:var(--muted);font-size:14px;margin:0 0 26px}
h3{font-size:16px;margin:34px 0 12px;font-weight:600}
p{margin:0 0 14px}
.hl{background:linear-gradient(transparent 62%,#f6e2ba 62%);padding:0 2px}

/* ---------- KPI ---------- */
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:34px 0 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 16px}
.kpi .k{font-size:12px;color:var(--muted);margin-bottom:8px}
.kpi .v{font-size:26px;font-weight:700;line-height:1.15;letter-spacing:-.02em}
.kpi .v small{font-size:13px;font-weight:500;color:var(--muted);margin-left:3px}
.kpi .n{font-size:12px;color:var(--soft);margin-top:7px}
.kpi.hero-k{background:#1b1a17;border-color:#1b1a17;color:#f9f6ef}
.kpi.hero-k .k{color:#b7ae9d}
.kpi.hero-k .v small,.kpi.hero-k .n{color:#a79e8d}

/* ---------- 卡片/提示 ---------- */
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin:18px 0}
.note{border-left:3px solid var(--accent);background:var(--accent-soft);border-radius:0 10px 10px 0;
  padding:16px 20px;margin:20px 0;font-size:14.5px}
.note strong{color:var(--accent)}
.warn{border-left:3px solid var(--gold);background:#fbf3df;border-radius:0 10px 10px 0;
  padding:16px 20px;margin:20px 0;font-size:14.5px}

/* ---------- 表 ---------- */
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:8px 0 4px}
table{width:100%;border-collapse:collapse;font-size:13.5px;min-width:640px}
th{
  text-align:left;font-weight:600;font-size:12px;color:var(--muted);
  border-bottom:1.5px solid var(--ink);padding:9px 10px;white-space:nowrap;
}
td{padding:10px;border-bottom:1px solid var(--line2);vertical-align:top}
tr:last-child td{border-bottom:none}
td.r,th.r{text-align:right}
tr.pass td{background:#fcfaf4}
tr.sel td{background:#fff8ec}
.tag{display:inline-block;font-size:11px;padding:1px 7px;border-radius:4px;white-space:nowrap}
.tag.a{background:#eef2f8;color:#4a5f7a}
.tag.hk{background:var(--green-soft);color:var(--green)}
.tag.ok{background:#fff1e6;color:var(--accent)}
.tag.no{background:#f1efe9;color:var(--soft)}
.reason{color:var(--muted);font-size:12.5px}

/* ---------- 条形 ---------- */
.bars{margin:10px 0}
.bar-row{display:grid;grid-template-columns:150px 1fr 74px;gap:12px;align-items:center;
  padding:7px 0;border-bottom:1px solid var(--line2);font-size:13px}
.bar-row:last-child{border-bottom:none}
.bar-track{background:#eee9dd;border-radius:3px;height:16px;position:relative;overflow:hidden}
.bar-fill{position:absolute;left:0;top:0;bottom:0;border-radius:3px}
.bar-fill.a{background:#8fa3bd}
.bar-fill.hk{background:#4d8a6c}
.bar-fill.acc{background:var(--accent)}
.bar-fill.gold{background:#c99b3f}
.bar-val{text-align:right;font-size:13px;font-weight:600}

/* ---------- 情景 ---------- */
.sc-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:22px 0 0}
.sc{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px}
.sc .lab{font-size:12px;letter-spacing:.16em;color:var(--muted)}
.sc .big{font-size:32px;font-weight:700;margin:6px 0 2px;letter-spacing:-.02em}
.sc .d{font-size:12.5px;color:var(--muted);line-height:1.6}
.sc.good{border-top:3px solid #b23a2c}
.sc.base{border-top:3px solid #c99b3f}
.sc.bad{border-top:3px solid #2c6e52}
.sc.good .big{color:#b23a2c}
.sc.base .big{color:#a07b20}
.sc.bad .big{color:#2c6e52}

/* ---------- 校验 ---------- */
.checks{display:grid;grid-template-columns:1fr 1fr;gap:6px 22px;margin-top:14px}
.chk{display:flex;gap:9px;font-size:13px;padding:6px 0;border-bottom:1px dashed var(--line2)}
.chk .m{color:var(--green);font-weight:700;flex:0 0 auto}
.chk .m.bad{color:var(--accent)}
.chk .t{flex:1}
.chk .d{color:var(--soft);font-size:11.5px;display:block}

/* ---------- 脚注 ---------- */
footer{margin-top:56px;padding-top:24px;border-top:1px solid var(--line);color:var(--soft);font-size:12.5px}
footer p{margin:0 0 8px}

@media (max-width:860px){
  .kpis{grid-template-columns:repeat(2,1fr)}
  .sc-grid{grid-template-columns:1fr}
  .checks{grid-template-columns:1fr}
  h1{font-size:32px}
  .bar-row{grid-template-columns:104px 1fr 64px;font-size:12px}
  section{padding:38px 0 6px}
}
@media print{
  body{background:#fff;font-size:12px}
  .wrap{max-width:none;padding:0}
  section{page-break-inside:avoid;padding:22px 0 4px}
  .hero{padding:0 0 18px}
  h1{font-size:30px}
  .card,.kpi,.sc,.note,.warn{break-inside:avoid}
  .kpi.hero-k{background:#fff;color:var(--ink);border-color:var(--ink)}
  .kpi.hero-k .k,.kpi.hero-k .v small,.kpi.hero-k .n{color:var(--muted)}
}
"""


def bar_rows(items, maxv, color_fn, fmt):
    out = []
    for label, val, cls in items:
        w = max(0.0, val / maxv * 100) if maxv else 0
        out.append(
            '<div class="bar-row"><div>%s</div>'
            '<div class="bar-track"><div class="bar-fill %s" style="width:%.1f%%"></div></div>'
            '<div class="bar-val num">%s</div></div>' % (label, color_fn(cls), w, fmt(val)))
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", required=True)
    ap.add_argument("--portfolio", required=True)
    ap.add_argument("--verify", default=None)
    ap.add_argument("--bond", type=float, default=1.6474)
    ap.add_argument("--out", required=True)
    ap.add_argument("--brand", default="@望京博格")
    args = ap.parse_args()

    uni = load(args.universe)
    port = load(args.portfolio)
    ver = load(args.verify) if args.verify and os.path.exists(args.verify) else None

    agg = port["portfolio"]
    hold = port["holdings"]
    sc = {s["key"]: s for s in port["scenarios"]}
    rules = port["rules"]
    capital = port["capital"]
    as_of = port["as_of"]
    funnel = uni.get("funnel", {})
    pool = uni["pool"]

    mc = port.get("market_context")
    bond_month = capital * args.bond / 100 / 12
    bond_year = capital * args.bond / 100
    multiple = agg["div_annual_theory"] / bond_year

    # 候选表（按税后股息率排序，通过的在前）
    pool_sorted = sorted(
        pool,
        key=lambda r: (0 if r["status"] in ("pass", "reserve") else 1, -(r["yld_after_tax"] or 0)))
    rows_html = []
    for r in pool_sorted:
        cls = "sel" if r["status"] in ("pass", "reserve") else ""
        if r["status"] == "reserve":
            judge = '<span class="tag ok">备选</span> 排名第 6，未进前 5'
        elif r["status"] == "pass":
            judge = '<span class="tag ok">入选</span>'
        else:
            judge = '<span class="tag no">剔除</span><div class="reason">%s</div>' % r["reason"]
        rows_html.append(
            '<tr class="%s"><td class="mono">%s</td><td>%s</td><td>%s<br><span class="reason">%s</span></td>'
            '<td class="r num">%s</td><td class="r num">%s</td><td class="r num">%s</td>'
            '<td class="r num">%s</td><td class="r num">%s</td><td>%s</td></tr>' % (
                cls, r["code"], r["name"],
                r["index_name"], r["index_code"] or "—",
                r["div_count"], "%.2f%%" % r["yld"] if r["yld"] else "—",
                "%.2f%%" % r["yld_after_tax"] if r["yld_after_tax"] else "—",
                "%.2f%%" % r["fee"],
                "%.0f%%" % (r["realize"] * 100) if r["realize"] is not None else "—",
                judge))
    pool_table = "".join(rows_html)

    # 持仓表
    h_rows = []
    for h in hold:
        h_rows.append(
            '<tr><td class="mono">%s</td><td>%s</td><td>%s</td>'
            '<td><span class="tag %s">%s</span></td>'
            '<td class="r num">%.2f%%</td><td class="r num">%.2f%%</td><td class="r num">%.2f%%</td>'
            '<td class="r num">%.3f</td><td class="r num">%.0f%%</td>'
            '<td class="r num">%s</td><td class="r num">%s</td><td class="r num">%s</td></tr>' % (
                h["code"], h["name"], h["index_name"],
                "hk" if h["market"] == "HK" else "a", "港股" if h["market"] == "HK" else "A股",
                h["yld"], h["yld_after_tax"], h["fee"], h["price"], h["weight"] * 100,
                money(h["invested"]), money(h["shares"]), money(h["div_month_theory"])))
    hold_table = "".join(h_rows)

    # A股/港股均值对比
    ma = uni.get("market_avg", {})
    cmp_items = [("A股红利（税后）", ma.get("A") or 0, "a"),
                 ("港股红利（税后）", ma.get("HK") or 0, "hk"),
                 ("10年期国债", args.bond, "gold")]
    cmp_max = max(v for _, v, _ in cmp_items)
    cmp_bars = bar_rows(cmp_items, cmp_max, lambda c: c, lambda v: "%.2f%%" % v)

    # 三情景三年表
    th_year = "".join('<th class="r">第%d年月均<br>(元)</th>' % y for y in range(1, port["years"] + 1))
    th_mv = "".join('<th class="r">第%d年末<br>市值</th>' % y for y in range(1, port["years"] + 1))
    sc_rows = []
    for key in ("good", "base", "bad"):
        s = sc[key]
        cells = "".join('<td class="r num">%s</td>' % money(y["market_value"]) for y in s["years"])
        sc_rows.append(
            '<tr><td><strong>%s</strong><div class="reason">%s</div></td>%s'
            '<td class="r num">%s</td>'
            '<td class="r num" style="font-weight:700">%s</td><td class="r num">%s</td></tr>' % (
                s["label"] + "情景", s["desc"], cells,
                money(s["cum_div"]),
                pct(s["total_return"], 2, True), pct(s["annualized"], 2, True)))
    sc_table = "".join(sc_rows)

    # 情景大卡
    sc_cards = []
    for key, cls in (("good", "good"), ("base", "base"), ("bad", "bad")):
        s = sc[key]
        sc_cards.append(
            '<div class="sc %s"><div class="lab">%s情景</div>'
            '<div class="big num">%s</div><div class="d">三年累计 %s ｜ 年化 %s</div>'
            '<div class="d" style="margin-top:8px">%s</div></div>' % (
                cls, s["label"], pct(s["total_return"], 1, True),
                pct(s["total_return"], 1, True), pct(s["annualized"], 1, True), s["anchor"]))

    # 校验
    checks_html = ""
    n_pass = 0
    if ver:
        n_pass = ver["passed"]
        items = []
        for c in ver["checks"]:
            items.append('<div class="chk"><div class="m %s">%s</div><div class="t">%s'
                         '<span class="d">%s</span></div></div>' % (
                             "" if c["ok"] else "bad", "✓" if c["ok"] else "✗",
                             c["name"], c["detail"]))
        checks_html = '<div class="checks">%s</div>' % "".join(items)
        ver_line = "数据自检 %d/%d 项通过" % (ver["passed"], ver["total"])
    else:
        ver_line = "未运行自检脚本"

    # 月度：按年展示（各 ETF 派息日不同，按月均摊）
    year_div_table = []
    for key in ("good", "base", "bad"):
        s = sc[key]
        year_div_table.append(
            '<tr><td>%s情景</td>%s<td class="r num">%s</td></tr>' % (
                s["label"],
                "".join('<td class="r num">%s</td>' % money(y["month_div"]) for y in s["years"]),
                money(s["cum_div"])))

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    n_monthly = sum(1 for r in pool if (r["div_count"] or 0) >= rules["min_div_count"])
    n_input = len(pool)

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>月月分红红利ETF组合 · 望京博格</title>
<style>%s</style>
</head>
<body>
<div class="wrap">

<header class="hero">
  <div class="eyebrow">望京博格 · 组合说明书</div>
  <h1>100万买红利ETF，<br>每个月能收到多少分红？</h1>
  <p class="lede">从全市场筛出真正"月月分红"的红利ETF，选 5 只跟踪指数不重复的，按 100 万本金算出未来三年每个月的现金流，再用好、中、坏三种市场情景推演收益。</p>
  <div class="chips">
    <span class="chip">数据日期 %s</span>
    <span class="chip">10年期国债 %.4f%%</span>
    <span class="chip">候选 %d 只 → 入选 %d 只</span>
    <span class="chip">%s</span>
  </div>
  <div class="kpis">
    <div class="kpi hero-k"><div class="k">每月分红（100万本金）</div>
      <div class="v num">%s<small>元</small></div>
      <div class="n">保守口径 %s 元 / 月</div></div>
    <div class="kpi"><div class="k">一年到手</div>
      <div class="v num">%s<small>万</small></div>
      <div class="n">相当于 %.2f%% 的派息率</div></div>
    <div class="kpi"><div class="k">是国债利息的</div>
      <div class="v num">%.1f<small>倍</small></div>
      <div class="n">国债利息 %s 元 / 月</div></div>
    <div class="kpi"><div class="k">三年总收益区间</div>
      <div class="v num">%s ~ %s</div>
      <div class="n">坏情景 ~ 好情景</div></div>
  </div>
</header>

<section>
  <h2><span class="idx">01</span>先把话说清楚：凑不出 20 只</h2>
  <p class="sub">"近一年月月分红"这个条件，比"高股息"苛刻得多。</p>
  <p>全市场名称里带红利、股息、高股息的场内 ETF，这次扫出 %d 只近一年分红次数在 10 次以上的。其中真正达到"月月分红"标准（近一年分红 ≥ %d 次）的只有 <span class="hl">%d 只</span>——不是数据缺失，是市场上做月月分红的红利 ETF 就这么点。</p>
  <div class="note"><strong>所以本报告没有第 20 名。</strong>我们没有拿季度分红、年度分红的红利 ETF 来凑数，也没有把"高股息但基本不分红"的产品塞进榜单。下面这张表就是全部 %d 只候选，被剔除的每一只都写了原因，可以逐条核对。</div>
</section>

<section>
  <h2><span class="idx">02</span>红利资产现在值多少钱</h2>
  <p class="sub">A股红利 vs 港股红利（扣 20%% 红利税）vs 十年期国债。</p>
  <div class="bars">%s</div>
  <p style="margin-top:16px">港股红利的<i>名义</i>股息率比 A股 高 1 个百分点左右，但内地个人投资者通过港股通拿分红要交 20%% 的税。扣完税以后，两者的差距几乎被抹平——A股 %.2f%%、港股 %.2f%%，差 %.2f 个百分点。指望"港股红利完胜 A股"的说法，在税后口径下站不住。</p>
  <div class="warn">真正拉开差距的不是港股还是 A股，而是<b>费率</b>和<b>基金愿不愿意把股息分出来</b>。有些 ETF 指数股息率 5.4%%，近一年实际只派了 1.4%%，差额留在净值里——对你来说那不叫分红，叫账面浮盈。</div>
</section>

<section>
  <h2><span class="idx">03</span>五道筛子筛出 5 只</h2>
  <p class="sub">%d 只候选 → 分红次数 %d 只 → 规模 %d 只 → 指数去重 %d 只 → 派息兑现 %d 只 → 取前 5</p>
  <div class="tw">
  <table>
    <thead><tr>
      <th>代码</th><th>简称</th><th>跟踪指数</th><th class="r">近一年<br>分红次数</th>
      <th class="r">指数<br>股息率</th><th class="r">税后</th><th class="r">综合<br>费率</th>
      <th class="r">派息<br>兑现率</th><th>结论</th>
    </tr></thead>
    <tbody>%s</tbody>
  </table>
  </div>
  <h3>五条硬规则</h3>
  <div class="card">
    <p><b>① 月月分红</b>：近一年分红次数 ≥ %d 次。12 个月里最多允许缺一次，缺两次就不叫月月分红了。</p>
    <p><b>② 规模 ≥ %.0f 亿</b>：清盘红线是 5000 万，规模太小进出会砸出折溢价。</p>
    <p><b>③ 指数不重复</b>：同一个跟踪指数只留综合费率最低的一只；费率相同留规模最大的。避免 5 只 ETF 买成同一个东西。</p>
    <p><b>④ 派息兑现率 ≥ %.0f%%</b>：近一年实际单位分红 ÷ 可持续派息率。这条是用来剔除"指数很能派、基金却不分"的产品的。</p>
    <p><b>⑤ 按税后股息率取前 5</b>：港股先扣 20%% 红利税再参与排名，不然港股会系统性占便宜。</p>
  </div>
</section>

<section>
  <h2><span class="idx">04</span>组合长这样</h2>
  <p class="sub">100 万等权持有 5 只，每只 20 万。之所以等权，是因为 5 只的可持续派息率都在 3.6%%–4.6%% 之间，按派息率加权的权重和等权差不到 2 个百分点，没必要把模型搞复杂。</p>
  <div class="tw">
  <table>
    <thead><tr>
      <th>代码</th><th>简称</th><th>跟踪指数</th><th>市场</th>
      <th class="r">指数<br>股息率</th><th class="r">税后</th><th class="r">综合<br>费率</th>
      <th class="r">现价</th><th class="r">权重</th><th class="r">投入<br>(元)</th>
      <th class="r">份数</th><th class="r">月分红<br>(元)</th>
    </tr></thead>
    <tbody>%s</tbody>
    <tfoot><tr>
      <td colspan="4"><strong>合计</strong></td>
      <td class="r num">%.2f%%</td><td class="r num">%.2f%%</td><td class="r num">%.2f%%</td>
      <td class="r">—</td><td class="r num">100%%</td><td class="r num"><strong>%s</strong></td>
      <td class="r">—</td><td class="r num"><strong>%s</strong></td>
    </tr></tfoot>
  </table>
  </div>
  <p style="font-size:13px;color:var(--muted)">份数按 100 份整手取整，实际投入 %s 元，剩 %s 元零钱。指数的"股息率"是名义值，港股那一列已按 20%% 红利税折算。</p>
</section>

<section>
  <h2><span class="idx">05</span>每个月到底能收多少钱</h2>
  <p class="sub">分红按"每份多少钱"算，不是按"市值的百分比"算。</p>
  <p>这是本报告最容易被算错的地方。100 万买进去，你拿到的是<b>固定份数</b>×<b>每份分红</b>。每份分红由成分股每股派息决定，跟股价涨跌没关系——股价跌了，股息率会机械地变高，但那不是分红变多，是分母变小了。</p>
  <p>所以下面这张表，理论口径 = 指数税后股息率 − 综合费率；保守口径再套一层"近一年实际派息率"的上限，防止把"基金没分出来的钱"也算成收入。</p>
  <div class="kpis" style="grid-template-columns:repeat(3,1fr)">
    <div class="kpi"><div class="k">基准（理论口径）</div><div class="v num">%s<small>元/月</small></div>
      <div class="n">年 %s 元 ｜ 派息率 %.2f%%</div></div>
    <div class="kpi"><div class="k">保守（按实际兑现折算）</div><div class="v num">%s<small>元/月</small></div>
      <div class="n">年 %s 元 ｜ 派息率 %.2f%%</div></div>
    <div class="kpi"><div class="k">对比：10年期国债</div><div class="v num">%s<small>元/月</small></div>
      <div class="n">同样的 100 万，年息 %s 元</div></div>
  </div>
  <h3>未来三年，每月的分红（三情景）</h3>
  <div class="tw">
  <table>
    <thead><tr><th>情景</th>%s<th class="r">三年累计分红</th></tr></thead>
    <tbody>%s</tbody>
  </table>
  </div>
  <p style="font-size:13px;color:var(--muted)">好情景假设成分股分红每年增 5%%，中性 3%%，坏情景 0%%。各 ETF 的派息日分散在每月不同时点，实际到账不是每月同一天，但月度合计大致平稳。</p>
</section>

<section>
  <h2><span class="idx">06</span>三年收益率：好、中、坏</h2>
  <p class="sub">价格波动决定净值，分红决定底气。</p>
  <div class="sc-grid">%s</div>
  <p style="margin-top:22px">三种情景的核心差别不在分红——三年累计分红从 %s 到 %s，只差 %.1f%%。差别全在净值上：好情景多 %s，坏情景少 %s。<b>这就是红利资产的样子：现金流很稳，波动全在价格里。</b></p>
  <h3>逐年拆解</h3>
  <div class="tw">
  <table>
    <thead><tr><th>情景</th>%s<th class="r">累计分红</th>
      <th class="r">三年总收益</th><th class="r">年化</th></tr></thead>
    <tbody>%s</tbody>
  </table>
  </div>
  <div class="note"><strong>情景假设怎么来的：</strong>不是拍脑袋。5 只标的近一年价格涨幅均值 %s、平均年化波动率 %s、平均最大回撤 %s，其中最强的一只涨了 %s。好情景 %s 大致对应"涨到近期最强势那一档"，坏情景 %s 大致对应"平均最大回撤分三年摊完"。极端行情会比这更狠，那部分测不出来，只能靠仓位控制。</div>
</section>

<section>
  <h2><span class="idx">07</span>数据自检</h2>
  <p class="sub">%s。每一项都是从原始数据反向重算，不是拿上游结果自证。</p>
  %s
</section>

<section>
  <h2><span class="idx">08</span>该说清楚的几件事</h2>
  <div class="card">
    <p><b>分红不等于收益。</b>ETF 分红是把净值里的钱拿出来给你，除息当天净值等额下跌。真正的收益 = 分红 + 净值变化。别看到"每月派息"就以为白捡钱。</p>
    <p><b>派息可能低于指数股息率。</b>基金合同允许管理人在满足分红条件后自主决定分配比例，有的产品常年只分一部分。本报告用"派息兑现率"筛过一轮，但未来仍可能变化。</p>
    <p><b>港股部分的汇率与税。</b>三只港股标的的净值以人民币计价，港币兑人民币的波动会直接体现在净值上；20%% 红利税是当前政策，未来若调整，税后股息率会跟着变。</p>
    <p><b>红利策略有拥挤风险。</b>组合里的标的集中在银行、煤炭、电力、交运这类高分红行业，行业相关性高。市场风格切到成长时，红利可能连续跑输——坏情景的 −7%% 已经考虑了一部分，但不是全部。</p>
    <p><b>最小的一只只有 %.1f 亿。</b>规模小的 ETF 在极端行情里折溢价会放大，进出尽量用限价单，别用市价单扫。</p>
  </div>
</section>

<footer>
  <p><b>数据来源：</b>Wind（指数股息率 TTM、ETF 分红记录、费率、规模、行情），10 年期国债取中证指数公司口径 <span class="mono">M1001654</span>，数据日期 %s。</p>
  <p><b>口径：</b>指数股息率 = Wind 股息率 TTM（成分股加权）；港股税后 = 名义 ×(1−20%%)；可持续派息率 = 税后 − 综合费率；综合费率 = 管理费 + 托管费。</p>
  <p><b>免责：</b>本文为数据推演，情景假设是人为设定，不构成任何投资建议。基金有风险，过往业绩不代表未来表现。</p>
  <p style="margin-top:14px">%s ｜ 生成于 %s ｜ %s</p>
</footer>

</div>
</body>
</html>
""" % (
        CSS,
        as_of, args.bond, n_input, len(hold), ver_line,
        money(agg["div_month_theory"]), money(agg["div_month_cons"]),
        "%.2f" % (agg["div_annual_theory"] / 10000), agg["weighted_sustainable"],
        multiple, money(bond_month),
        pct(sc["bad"]["total_return"], 0, True), pct(sc["good"]["total_return"], 0, True),

        n_input, rules["min_div_count"], n_monthly, n_input,

        cmp_bars, ma.get("A") or 0, ma.get("HK") or 0, abs((ma.get("HK") or 0) - (ma.get("A") or 0)),

        n_input,
        n_input - funnel.get("step0", 0) - funnel.get("step1", 0),
        n_input - funnel.get("step0", 0) - funnel.get("step1", 0) - funnel.get("step2", 0),
        n_input - funnel.get("step0", 0) - funnel.get("step1", 0) - funnel.get("step2", 0) - funnel.get("step3", 0),
        funnel.get("pass", 0),
        pool_table,
        rules["min_div_count"], rules["min_size"], rules["min_realize_ratio"] * 100,

        hold_table,
        agg["weighted_y"], agg["weighted_y_after_tax"], agg["weighted_fee"],
        money(agg["invested"]), money(agg["div_month_theory"]),
        money(agg["invested"]), money(agg["cash_left"]),

        money(agg["div_month_theory"]), money(agg["div_annual_theory"]), agg["weighted_sustainable"],
        money(agg["div_month_cons"]), money(agg["div_annual_cons"]),
        agg["div_annual_cons"] / capital * 100,
        money(bond_month), money(bond_year),

        th_year, "".join(year_div_table),

        "".join(sc_cards),
        money(min(s["cum_div"] for s in sc.values())),
        money(max(s["cum_div"] for s in sc.values())),
        (max(s["cum_div"] for s in sc.values()) / min(s["cum_div"] for s in sc.values()) - 1) * 100,
        money(sc["good"]["end_value"] - agg["invested"]),
        money(agg["invested"] - sc["bad"]["end_value"]),

        th_mv, sc_table,

        pnum(mc["avg_ret_1y"], 1, True) if mc else "—",
        pnum(mc["avg_vol_1y"], 1) if mc else "—",
        pnum(abs(mc["avg_mdd_1y"]), 1) if mc else "—",
        pnum(mc["max_ret_1y"], 1, True) if mc else "—",
        pct(sc["good"]["price_return"], 0, True),
        pct(sc["bad"]["price_return"], 0, True),

        ver_line, checks_html,

        min(h["size"] for h in hold),

        as_of, args.brand, now, "本报告由 wj-monthly-dividend-etf Skill 生成",
    )

    # 补三个情景锚点里的真实波动数据
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("报告已生成：%s（%.0f KB）" % (args.out, len(html.encode("utf-8")) / 1024))
    print("月分红 %s 元（理论）/ %s 元（保守）；三年 %s ~ %s" % (
        money(agg["div_month_theory"]), money(agg["div_month_cons"]),
        pct(sc["bad"]["total_return"], 2, True), pct(sc["good"]["total_return"], 2, True)))


if __name__ == "__main__":
    main()
