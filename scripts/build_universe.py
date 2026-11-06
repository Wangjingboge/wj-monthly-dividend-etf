# -*- coding: utf-8 -*-
"""月月分红红利ETF · 候选池筛选

输入 Wind 原始 JSON（ETF分红明细 / 指数股息率 / 价格快照），输出带「入选/剔除原因」的候选池。

用法：
    python build_universe.py \
        --dividend raw/etf_dividend.json \
        --yield raw/index_yield_a.json raw/index_yield_hk.json \
        --price raw/price.json \
        --out out/universe.json

规则（顺序固定，不可调换）：
    R1 近一年分红次数 >= min_div_count         —— 月月分红的定义
    R2 只留场内ETF（剔除 .OF 联接/场外）
    R3 同一跟踪指数只留综合费率最低的一只        —— 去重，避免组合重复暴露
    R4 规模 >= min_size 亿元                   —— 规避清盘与流动性风险
    R5 派息兑现率 >= min_realize_ratio          —— 剔除「指数高股息、基金不分红」
    R6 按税后股息率降序取 top_n
"""

import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def rows_of(obj, columns=None):
    """兼容两种存法：list-of-list + columns 表头，或 list-of-dict"""
    out = []
    cols = obj.get("columns") or columns
    for r in obj.get("rows", []):
        if isinstance(r, dict):
            out.append(dict(r))
        else:
            out.append(dict(zip(cols, r)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dividend", required=True, help="ETF 分红明细 JSON")
    ap.add_argument("--yield", dest="yield_files", nargs="+", required=True, help="指数股息率 JSON（可多个）")
    ap.add_argument("--price", required=True, help="ETF 价格/规模快照 JSON")
    ap.add_argument("--aliases", default=os.path.join(HERE, "..", "references", "index-aliases.json"))
    ap.add_argument("--assumptions", default=os.path.join(HERE, "..", "references", "assumptions.json"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rules = load(args.assumptions)["rules"]
    tax = rules["tax_rate_hk"]

    # 指数代码 -> (简称, 股息率, 市场)
    idx = {}
    for path in args.yield_files:
        obj = load(path)
        for r in rows_of(obj):
            code, name, y = r.get("code"), r.get("name"), r.get("yld")
            if code and y is not None:
                idx[code] = {"name": name, "yld": float(y)}

    alias = {a["key"]: a for a in load(args.aliases)["indices"]}
    prices = {r["code"]: r for r in rows_of(load(args.price))}

    pool = []
    for r in rows_of(load(args.dividend)):
        code = r["code"]
        if code.endswith(".OF"):
            continue  # R2
        a = alias.get(r["index_name"])
        px = prices.get(code)
        row = {
            "code": code,
            "name": r["name"],
            "index_name": r["index_name"],
            "div_count": r.get("div_count"),
            "div_per_unit": r.get("div_per_unit"),
            "fee": round((r.get("manage") or 0) + (r.get("custody") or 0), 2),
            "size": r.get("size"),
            "price": px["px"] if px else None,
            "market": None,
            "index_code": None,
            "yld": None,
            "yld_after_tax": None,
            "sustainable": None,
            "payout_observed": None,
            "realize": None,
            "status": "pass",
            "step": 0,
            "reason": "",
        }

        if a is None:
            row["status"] = "reject"
            row["reason"] = "跟踪指数未收录，需先补 index-aliases.json"
        elif not a.get("dividend"):
            row["status"] = "reject"
            row["reason"] = a.get("reason", "非红利策略指数")
        else:
            row["market"] = a["market"]
            row["index_code"] = a["code"]
            hit = idx.get(a["code"])
            if not hit:
                row["status"] = "reject"
                row["reason"] = "未取到该指数股息率"
            else:
                y = hit["yld"]
                row["yld"] = round(y, 4)
                row["yld_after_tax"] = round(y * (1 - tax), 4) if a["market"] == "HK" else round(y, 4)
                # 可持续派息率 = 税后股息率 - 综合费率（分红要先付管理费托管费）
                row["sustainable"] = round(row["yld_after_tax"] - row["fee"], 4)
                if row["price"]:
                    row["payout_observed"] = round(row["div_per_unit"] / row["price"] * 100, 4)
                    if row["sustainable"] and row["sustainable"] > 0:
                        row["realize"] = round(row["payout_observed"] / row["sustainable"], 4)

        # R1
        if row["status"] == "pass" and (row["div_count"] or 0) < rules["min_div_count"]:
            row["status"] = "reject"
            row["step"] = 1
            row["reason"] = "近一年分红 %d 次，不足 %d 次" % (row["div_count"], rules["min_div_count"])

        pool.append(row)

    # R4 规模门槛：先筛「能不能买」，再谈「选哪只」
    # 顺序很关键：如果先去重（费率优先），低费率但规模几千万的迷你ETF会把整条指数挤掉。
    for row in pool:
        if row["status"] == "pass" and (row["size"] or 0) < rules["min_size"]:
            row["status"] = "reject"
            row["step"] = 2
            row["reason"] = "规模 %.2f 亿，低于 %.1f 亿门槛" % (row["size"], rules["min_size"])

    # R3 指数去重：同一 index_code 只留 (费率最低, 规模最大) 的代表
    groups = {}
    for row in pool:
        if row["status"] == "pass" and row["index_code"]:
            groups.setdefault(row["index_code"], []).append(row)
    for code, group in groups.items():
        group.sort(key=lambda x: (x["fee"], -(x["size"] or 0)))
        keeper = group[0]
        for other in group[1:]:
            other["status"] = "reject"
            other["step"] = 3
            if other["fee"] > keeper["fee"]:
                why = "综合费率 %.2f%%，低于本只的 %.2f%%" % (keeper["fee"], other["fee"])
            else:
                why = "综合费率相同（%.2f%%），但本只规模 %.1f 亿小于其 %.1f 亿" % (
                    other["fee"], other["size"], keeper["size"])
            other["reason"] = "与 %s 跟踪同一指数（%s），%s" % (keeper["code"], keeper["index_name"], why)

    # R5 派息兑现率
    for row in pool:
        if row["status"] != "pass":
            continue
        if row["realize"] is not None and row["realize"] < rules["min_realize_ratio"]:
            row["status"] = "reject"
            row["step"] = 4
            row["reason"] = "派息兑现率仅 %.0f%%（近12月实际派息 %.2f%% vs 可持续 %.2f%%），高股息没落到口袋里" % (
                row["realize"] * 100, row["payout_observed"], row["sustainable"])

    passed = [r for r in pool if r["status"] == "pass"]
    passed.sort(key=lambda x: -(x["yld_after_tax"] or 0))

    # R6 取前 N（指数已去重，天然不重复）
    selected = passed[: rules["top_n"]]
    for row in passed[rules["top_n"]:]:
        row["status"] = "reserve"
        row["step"] = 5
        row["reason"] = "税后股息率排名第 %d，未进前 %d" % (passed.index(row) + 1, rules["top_n"])

    market_avg = {}
    for m in ("A", "HK"):
        vals = [r["yld_after_tax"] for r in passed if r["market"] == m]
        market_avg[m] = round(sum(vals) / len(vals), 4) if vals else None

    funnel = {"input": len(pool)}
    for st, label in ((0, "非红利策略/指数未收录"), (1, "分红次数不足"),
                      (2, "规模不足"), (3, "同指数去重"), (4, "派息兑现率不足")):
        funnel["step%d" % st] = sum(1 for r in pool if r["step"] == st and r["status"] == "reject")
    funnel["pass"] = len(passed)
    funnel["selected"] = len(selected)

    payload = {
        "as_of": load(args.dividend).get("as_of"),
        "funnel": funnel,
        "rules": rules,
        "market_avg": market_avg,
        "counts": {
            "input": len(pool),
            "pass": len(passed),
            "selected": len(selected),
        },
        "selected": selected,
        "pool": pool,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print("候选 %d 只 → 通过 %d 只 → 入选 %d 只" % (len(pool), len(passed), len(selected)))
    print("%-10s %-26s %-14s %6s %6s %6s %6s" % ("代码", "简称", "跟踪指数", "名义", "税后", "费率", "兑现率"))
    for r in selected:
        print("%-10s %-26s %-14s %6.2f %6.2f %6.2f %6.0f%%" % (
            r["code"], r["name"][:12], r["index_name"][:12],
            r["yld"], r["yld_after_tax"], r["fee"], (r["realize"] or 0) * 100))
    print("A股均值 %.4f%% / 港股税后均值 %.4f%%" % (market_avg["A"] or 0, market_avg["HK"] or 0))
    if len(passed) < rules["top_n"]:
        print("⚠ 通过筛选的只有 %d 只，不足 %d 只；报告按实际数量呈现，不要硬凑" % (len(passed), rules["top_n"]))
    print("剔除明细：")
    for r in pool:
        if r["status"] == "reject":
            print("  · %s %s —— %s" % (r["code"], r["name"][:14], r["reason"]))


if __name__ == "__main__":
    main()
