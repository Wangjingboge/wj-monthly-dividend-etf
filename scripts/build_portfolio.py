# -*- coding: utf-8 -*-
"""月月分红红利ETF · 组合构建与三年测算

输入 universe.json（上一支脚本的产出），输出持仓、月分红、三情景三年现金流与收益率。

用法：
    python build_portfolio.py --universe out/universe.json --out out/portfolio.json

模型要点（别改口径，改之前先看 references/methodology.md）：
  1. 可持续派息率 = 指数税后股息率 - 综合费率。ETF 分红来自成分股股息，先扣管理费托管费，
     所以长期能分出来的钱不会超过这个数。
  2. 分红按「每份多少钱」算，不按「市值的百分比」算。份额在持有期不变，
     分红金额由成分股每股分红决定，与股价涨跌无关——股价跌了，股息率是被动抬高的，不是分红变多。
  3. 保守口径再套一层「派息兑现率」上限：min(近12月实际派息率, 可持续派息率)。
     有的基金把股息留在净值里不分，账面上股息率好看，口袋里没钱。
"""

import argparse
import json
import math
import os


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", required=True)
    ap.add_argument("--assumptions", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "references", "assumptions.json"))
    ap.add_argument("--perf", default=None, help="ETF 近1年业绩 JSON（可选，用于给情景找锚点）")
    ap.add_argument("--capital", type=float, default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    uni = load(args.universe)
    cfg = load(args.assumptions)
    rules = cfg["rules"]
    capital = args.capital or cfg["capital"]
    years = cfg["years"]
    holdings_in = uni["selected"]
    n = len(holdings_in)
    if n == 0:
        raise SystemExit("没有入选标的，检查上游筛选")

    # ---- 权重 ----
    if rules.get("weight_mode") == "yield":
        raw = [h["yld_after_tax"] for h in holdings_in]
        total = sum(raw)
        weights = [w / total for w in raw]
        cap = rules.get("weight_cap", 1.0)
        weights = [min(w, cap) for w in weights]
        s = sum(weights)
        weights = [w / s for w in weights]
    else:
        weights = [1.0 / n] * n

    # ---- 持仓明细 ----
    holdings = []
    for h, w in zip(holdings_in, weights):
        amount = capital * w
        px = h["price"]
        shares = int(math.floor(amount / px / 100.0) * 100)
        invested = round(shares * px, 2)
        sus = max(h["sustainable"], 0.0)
        cons_rate = min(h["payout_observed"], sus) if h.get("payout_observed") else sus
        holdings.append({
            "code": h["code"],
            "name": h["name"],
            "index_name": h["index_name"],
            "index_code": h["index_code"],
            "market": h["market"],
            "price": px,
            "weight": round(w, 4),
            "amount": round(amount, 2),
            "shares": shares,
            "invested": invested,
            "yld": h["yld"],
            "yld_after_tax": h["yld_after_tax"],
            "fee": h["fee"],
            "size": h.get("size"),
            "div_count": h.get("div_count"),
            "div_per_unit": h.get("div_per_unit"),
            "sustainable": round(sus, 4),
            "payout_observed": h["payout_observed"],
            "realize": h["realize"],
            "div_annual_theory": round(invested * sus / 100, 2),
            "div_month_theory": round(invested * sus / 100 / 12, 2),
            "div_annual_cons": round(invested * cons_rate / 100, 2),
            "div_month_cons": round(invested * cons_rate / 100 / 12, 2),
        })

    invested_total = round(sum(h["invested"] for h in holdings), 2)
    cash_left = round(capital - invested_total, 2)

    agg = {
        "weighted_y": round(sum(h["weight"] * h["yld"] for h in holdings), 4),
        "weighted_y_after_tax": round(sum(h["weight"] * h["yld_after_tax"] for h in holdings), 4),
        "weighted_fee": round(sum(h["weight"] * h["fee"] for h in holdings), 4),
        "weighted_sustainable": round(sum(h["weight"] * h["sustainable"] for h in holdings), 4),
        "invested": invested_total,
        "cash_left": cash_left,
        "div_annual_theory": round(sum(h["div_annual_theory"] for h in holdings), 2),
        "div_month_theory": round(sum(h["div_month_theory"] for h in holdings), 2),
        "div_annual_cons": round(sum(h["div_annual_cons"] for h in holdings), 2),
        "div_month_cons": round(sum(h["div_month_cons"] for h in holdings), 2),
    }

    # ---- 三情景：三年逐年 ----
    sc = []
    for s in cfg["scenarios"]:
        r, g = s["price_return"], s["div_growth"]
        rows, cum = [], 0.0
        for y in range(1, years + 1):
            mv = invested_total * (1 + r) ** y
            div = invested_total * agg["weighted_sustainable"] / 100 * (1 + g) ** (y - 1)
            cum += div
            total_ret = (mv - invested_total + cum) / invested_total
            rows.append({
                "year": y,
                "market_value": round(mv, 2),
                "year_div": round(div, 2),
                "month_div": round(div / 12, 2),
                "cum_div": round(cum, 2),
                "total_return": round(total_ret, 4),
                "annualized": round((1 + total_ret) ** (1.0 / y) - 1, 4),
            })
        end = rows[-1]
        sc.append({
            "key": s["key"],
            "label": s["label"],
            "desc": s["desc"],
            "anchor": s.get("anchor", ""),
            "price_return": r,
            "div_growth": g,
            "years": rows,
            "end_value": end["market_value"],
            "cum_div": end["cum_div"],
            "total_return": end["total_return"],
            "annualized": end["annualized"],
            "total_profit": round(end["market_value"] - invested_total + end["cum_div"], 2),
        })

    # ---- 行情锚点：给三情景假设找现实依据 ----
    market_context = None
    if args.perf and os.path.exists(args.perf):
        codes = {h["code"] for h in holdings}
        vals = [r for r in load(args.perf).get("rows", []) if r[0] in codes and r[1] is not None]
        if vals:
            n = len(vals)
            market_context = {
                "n": n,
                "avg_ret_1y": round(sum(r[1] for r in vals) / n, 4),
                "avg_vol_1y": round(sum(r[2] for r in vals) / n, 4),
                "avg_mdd_1y": round(sum(r[3] for r in vals) / n, 4),
                "max_ret_1y": round(max(r[1] for r in vals), 4),
            }

    # ---- 月度现金流（按月均摊，实际派息日分散在各月）----
    months = []
    for m in range(1, 13):
        months.append({
            "month": m,
            "theory": round(agg["div_month_theory"], 2),
            "cons": round(agg["div_month_cons"], 2),
        })

    payload = {
        "as_of": uni["as_of"],
        "capital": capital,
        "years": years,
        "rules": rules,
        "portfolio": agg,
        "holdings": holdings,
        "months": months,
        "scenarios": sc,
        "market_context": market_context,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print("组合：%d 只，投入 %.2f 元，剩余现金 %.2f 元" % (len(holdings), invested_total, cash_left))
    print("加权税后股息率 %.2f%% ｜ 加权费率 %.2f%% ｜ 可持续派息率 %.2f%%" % (
        agg["weighted_y_after_tax"], agg["weighted_fee"], agg["weighted_sustainable"]))
    print("月分红：理论 %.0f 元 / 保守 %.0f 元；年分红：理论 %.0f 元 / 保守 %.0f 元" % (
        agg["div_month_theory"], agg["div_month_cons"],
        agg["div_annual_theory"], agg["div_annual_cons"]))
    if market_context:
        print("行情锚点（%d 只）：近1年涨幅均值 %+.2f%% ｜ 平均波动率 %.2f%% ｜ 平均最大回撤 %.2f%%" % (
            market_context["n"], market_context["avg_ret_1y"],
            market_context["avg_vol_1y"], market_context["avg_mdd_1y"]))
    for x in sc:
        print("%s情景（价格年化 %+.0f%%，分红年增 %.0f%%）：三年累计分红 %.0f 元，期末市值 %.0f 元，"
              "总收益 %+.2f%%，年化 %+.2f%%" % (
                  x["label"], x["price_return"] * 100, x["div_growth"] * 100,
                  x["cum_div"], x["end_value"], x["total_return"] * 100, x["annualized"] * 100))


if __name__ == "__main__":
    main()
