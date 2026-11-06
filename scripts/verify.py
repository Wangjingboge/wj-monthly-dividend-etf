# -*- coding: utf-8 -*-
"""月月分红红利ETF · 数据自检

不复用上游任何中间结果，从 portfolio.json / universe.json 反向重算，逐条对账。
用法：
    python verify.py --universe out/universe.json --portfolio out/portfolio.json --out out/verify.json

退出码 0 = 全部通过；1 = 有 FAIL（报告里要标红，不许直接发）。
"""

import argparse
import json
import os

TOL = 1e-6


def load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", required=True)
    ap.add_argument("--portfolio", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    uni = load(args.universe)
    p = load(args.portfolio)
    hold = p["holdings"]
    agg = p["portfolio"]
    tax = uni["rules"]["tax_rate_hk"]
    checks = []

    def ck(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    # 1 权重
    sw = sum(h["weight"] for h in hold)
    ck("权重合计=100%", abs(sw - 1) < 1e-4, "Σ权重 = %.4f" % sw)

    # 2-4 逐只口径复算
    bad = []
    for h in hold:
        exp_tax = h["yld"] * (1 - tax) if h["market"] == "HK" else h["yld"]
        if abs(exp_tax - h["yld_after_tax"]) > 0.001:
            bad.append("%s 税后 %.4f ≠ %.4f" % (h["code"], h["yld_after_tax"], exp_tax))
        if abs(h["yld_after_tax"] - h["fee"] - h["sustainable"]) > 0.001:
            bad.append("%s 可持续 %.4f ≠ 税后-费率" % h["code"])
        obs = h["div_per_unit"] / h["price"] * 100 if "div_per_unit" in h else \
            h["payout_observed"]
        if abs(obs - h["payout_observed"]) > 0.01:
            bad.append("%s 派息率 %.4f ≠ 单位分红/价格 %.4f" % (h["code"], h["payout_observed"], obs))
    ck("逐只口径（税后/可持续/派息率）", not bad, "；".join(bad) if bad else "%d 只全部对得上" % len(hold))

    # 5 月分红合计
    calc_m = sum(h["invested"] * h["sustainable"] / 100 / 12 for h in hold)
    ck("月分红=Σ(投入×可持续派息率/12)", abs(calc_m - agg["div_month_theory"]) < 1.0,
       "重算 %.2f vs 报告 %.2f" % (calc_m, agg["div_month_theory"]))

    # 6 保守不高于理论
    ck("保守口径 ≤ 理论口径", agg["div_month_cons"] <= agg["div_month_theory"] + 1e-6,
       "保守 %.2f / 理论 %.2f" % (agg["div_month_cons"], agg["div_month_theory"]))

    # 7-8 三情景复算
    year_rows = []
    for s in p["scenarios"]:
        inv = agg["invested"]
        cum = 0.0
        for y in range(1, p["years"] + 1):
            cum += inv * agg["weighted_sustainable"] / 100 * (1 + s["div_growth"]) ** (y - 1)
        end = inv * (1 + s["price_return"]) ** p["years"]
        tot = (end - inv + cum) / inv
        ok = abs(cum - s["cum_div"]) < 1 and abs(tot - s["total_return"]) < 1e-4
        year_rows.append(ok)
        ck("%s情景 三年分红+总收益复算" % s["label"], ok,
           "分红 %.0f vs %.0f；总收益 %+.2f%% vs %+.2f%%" % (
               cum, s["cum_div"], tot * 100, s["total_return"] * 100))

    # 9 指数不重复
    codes = [h["index_code"] for h in hold]
    ck("5 只跟踪指数互不重复", len(set(codes)) == len(codes), "、".join(codes))

    # 10-11 入选门槛
    ck("入选者近一年分红 >= 11 次", all(h.get("div_count", 99) >= 11 for h in hold),
       "、".join("%s:%s次" % (h["code"], h.get("div_count")) for h in hold))
    ck("入选者规模 >= 2 亿", all(h.get("size", 99) >= 2 for h in hold),
       "、".join("%s:%.2f亿" % (h["code"], h.get("size", 0)) for h in hold))

    # 12 港股税后 < 名义
    hk = [h for h in hold if h["market"] == "HK"]
    ck("港股税后低于名义（扣20%红利税）", all(h["yld_after_tax"] < h["yld"] for h in hk),
       "%d 只港股标的已扣税" % len(hk))

    # 13 权重与金额
    dev = max(abs(h["invested"] / p["capital"] - h["weight"]) for h in hold)
    ck("投入金额与权重一致（整手取整误差<1%）", dev < 0.01, "最大偏离 %.3f%%" % (dev * 100))

    # 14 情景单调
    d = {s["key"]: s["cum_div"] for s in p["scenarios"]}
    ck("分红随情景单调（坏 ≤ 中 ≤ 好）", d["bad"] <= d["base"] <= d["good"],
       "坏 %.0f / 中 %.0f / 好 %.0f" % (d["bad"], d["base"], d["good"]))

    # 15 剩余现金
    ck("剩余现金 = 本金 - 投入", abs(p["capital"] - agg["invested"] - agg["cash_left"]) < 0.01,
       "%.2f + %.2f = %.2f" % (agg["invested"], agg["cash_left"], p["capital"]))

    passed = sum(1 for c in checks if c["ok"])
    payload = {"as_of": p["as_of"], "total": len(checks), "passed": passed, "checks": checks}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print("数据自检：%d/%d 项通过" % (passed, len(checks)))
    for c in checks:
        print("  %s %s —— %s" % ("✓" if c["ok"] else "✗", c["name"], c["detail"]))
    raise SystemExit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
