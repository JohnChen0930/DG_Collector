#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DGAnalyzer fixed single-file version
- No package imports
- Groups by tableName + shoeId (shoeId is not globally unique)
- Tie (T) is ignored for patterns and does not break a sequence
- Uses sliding windows correctly
"""
from __future__ import annotations

import argparse
import csv
import os
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple, Any, Optional

VALID_SIDES = {"B", "P", "T"}
BP_SIDES = {"B", "P"}

@dataclass
class ResultRow:
    id: int
    tableName: str
    shoeId: int
    tableId: int
    gameNo: str
    playId: int
    roadLen: int
    side: str
    createdAt: str
    onlineCount: int = 0
    totalAmount: float = 0.0


def safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or v == "":
            return default
        return int(v)
    except Exception:
        return default


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


def load_results(db_path: str) -> List[ResultRow]:
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"找不到 DB：{db_path}")

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT id, tableName, shoeId, tableId, gameNo, playId, roadLen,
                   side, createdAt, onlineCount, totalAmount
            FROM results
            WHERE side IS NOT NULL AND side != ''
            ORDER BY tableName, shoeId, COALESCE(playId, roadLen, id), id
            """
        ).fetchall()
    finally:
        con.close()

    results: List[ResultRow] = []
    for r in rows:
        side = str(r["side"] or "").strip().upper()
        if side not in VALID_SIDES:
            continue
        results.append(ResultRow(
            id=safe_int(r["id"]),
            tableName=str(r["tableName"] or "").strip(),
            shoeId=safe_int(r["shoeId"]),
            tableId=safe_int(r["tableId"]),
            gameNo=str(r["gameNo"] or ""),
            playId=safe_int(r["playId"]),
            roadLen=safe_int(r["roadLen"]),
            side=side,
            createdAt=str(r["createdAt"] or ""),
            onlineCount=safe_int(r["onlineCount"]),
            totalAmount=safe_float(r["totalAmount"]),
        ))
    return results


def group_by_shoe(rows: List[ResultRow]) -> Dict[Tuple[str, int], List[ResultRow]]:
    grouped: Dict[Tuple[str, int], List[ResultRow]] = defaultdict(list)
    for r in rows:
        grouped[(r.tableName, r.shoeId)].append(r)
    for k in grouped:
        grouped[k].sort(key=lambda x: (x.playId if x.playId else x.roadLen, x.id))
    return grouped


def build_pattern_stats(rows: List[ResultRow], max_len: int = 10):
    """Return patterns[length][pattern] = {sample,next_B,next_P,...} using sliding windows."""
    patterns: Dict[int, Dict[str, Dict[str, Any]]] = {L: {} for L in range(1, max_len + 1)}
    grouped = group_by_shoe(rows)

    for (table, shoe), shoe_rows in grouped.items():
        # Tie is ignored and does not break the shoe sequence.
        seq = [r.side for r in shoe_rows if r.side in BP_SIDES]
        if len(seq) < 2:
            continue
        for L in range(1, max_len + 1):
            if len(seq) <= L:
                continue
            for i in range(0, len(seq) - L):
                pat = "".join(seq[i:i+L])
                nxt = seq[i+L]
                bucket = patterns[L].setdefault(pat, {
                    "length": L,
                    "pattern": pat,
                    "sample": 0,
                    "next_B": 0,
                    "next_P": 0,
                })
                bucket["sample"] += 1
                if nxt == "B":
                    bucket["next_B"] += 1
                elif nxt == "P":
                    bucket["next_P"] += 1

    # decorate rates
    for L in patterns:
        for rec in patterns[L].values():
            sample = rec["sample"]
            b = rec["next_B"]
            p = rec["next_P"]
            rec["next_B_rate"] = round(b / sample * 100, 4) if sample else 0.0
            rec["next_P_rate"] = round(p / sample * 100, 4) if sample else 0.0
            if b >= p:
                rec["best_side"] = "B"
                rec["best_rate"] = rec["next_B_rate"]
            else:
                rec["best_side"] = "P"
                rec["best_rate"] = rec["next_P_rate"]
            rec["edge"] = round(abs(b - p) / sample * 100, 4) if sample else 0.0
    return patterns


def write_csv(path: str, rows: Iterable[Dict[str, Any]], fieldnames: List[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def write_summary(rows: List[ResultRow], out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    side_counts = Counter(r.side for r in rows)
    total = sum(side_counts.values())
    tables = sorted(set(r.tableName for r in rows))
    shoes = set((r.tableName, r.shoeId) for r in rows)
    def pct(n): return n / total * 100 if total else 0
    with open(os.path.join(out_dir, "summary.txt"), "w", encoding="utf-8") as f:
        f.write("========== DG Analyzer Fixed ==========" + "\n")
        f.write(f"Total rows: {total}\n")
        f.write(f"Tables: {len(tables)}\n")
        f.write(f"Shoes(tableName+shoeId): {len(shoes)}\n\n")
        for s in ["B", "P", "T"]:
            f.write(f"{s}: {side_counts.get(s,0)} ({pct(side_counts.get(s,0)):.2f}%)\n")


def build_table_report(rows: List[ResultRow]) -> List[Dict[str, Any]]:
    by_table: Dict[str, List[ResultRow]] = defaultdict(list)
    for r in rows:
        by_table[r.tableName].append(r)
    output = []
    for table, rs in sorted(by_table.items()):
        c = Counter(r.side for r in rs)
        total = len(rs)
        bp = c.get("B",0)+c.get("P",0)
        output.append({
            "tableName": table,
            "total": total,
            "B": c.get("B",0),
            "P": c.get("P",0),
            "T": c.get("T",0),
            "B_rate_all": round(c.get("B",0)/total*100,4) if total else 0,
            "P_rate_all": round(c.get("P",0)/total*100,4) if total else 0,
            "T_rate_all": round(c.get("T",0)/total*100,4) if total else 0,
            "B_rate_no_tie": round(c.get("B",0)/bp*100,4) if bp else 0,
            "P_rate_no_tie": round(c.get("P",0)/bp*100,4) if bp else 0,
            "shoe_count": len(set(r.shoeId for r in rs)),
        })
    return output


def build_streak(rows: List[ResultRow]) -> List[Dict[str, Any]]:
    streaks = {"B": Counter(), "P": Counter()}
    for key, rs in group_by_shoe(rows).items():
        seq = [r.side for r in rs if r.side in BP_SIDES]
        if not seq:
            continue
        cur = seq[0]
        length = 1
        for s in seq[1:]:
            if s == cur:
                length += 1
            else:
                streaks[cur][length] += 1
                cur = s
                length = 1
        streaks[cur][length] += 1
    max_len = max([0] + list(streaks["B"].keys()) + list(streaks["P"].keys()))
    return [{"streak_len": L, "B_count": streaks["B"].get(L,0), "P_count": streaks["P"].get(L,0)} for L in range(1, max_len+1)]


def build_transition(patterns: Dict[int, Dict[str, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    rows = []
    for rec in patterns.get(2, {}).values():
        rows.append(rec.copy())
    rows.sort(key=lambda r: (-r.get("sample",0), r.get("pattern","")))
    return rows


def build_pattern_length_summary(patterns: Dict[int, Dict[str, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    out = []
    for L, d in sorted(patterns.items()):
        samples = [r["sample"] for r in d.values()]
        out.append({
            "length": L,
            "pattern_kinds_all": len(d),
            "total_samples": sum(samples),
            "max_sample": max(samples) if samples else 0,
            "avg_sample": round(sum(samples)/len(samples),4) if samples else 0,
            "patterns_sample_ge_10": sum(1 for x in samples if x >= 10),
            "patterns_sample_ge_30": sum(1 for x in samples if x >= 30),
            "patterns_sample_ge_100": sum(1 for x in samples if x >= 100),
        })
    return out


def latest_pattern_by_table(rows: List[ResultRow], patterns, max_len: int = 10) -> List[Dict[str, Any]]:
    by_table: Dict[str, List[ResultRow]] = defaultdict(list)
    for r in rows:
        by_table[r.tableName].append(r)
    out = []
    for table, rs in sorted(by_table.items()):
        rs.sort(key=lambda r: (r.createdAt, r.id))
        latest_shoe = rs[-1].shoeId
        shoe_rows = [r for r in rs if r.shoeId == latest_shoe]
        shoe_rows.sort(key=lambda r: (r.playId if r.playId else r.roadLen, r.id))
        seq = [r.side for r in shoe_rows if r.side in BP_SIDES]
        latest_seq = "".join(seq[-max_len:])
        row = {"tableName": table, "latest_shoeId": latest_shoe, "bp_len_in_latest_shoe": len(seq), "latest_pattern_max10": latest_seq}
        # add best available suffix info
        best = recommend_from_sequence(seq, patterns, max_len=max_len)
        row.update(best)
        out.append(row)
    return out


def query_pattern(patterns, pattern: str) -> Optional[Dict[str, Any]]:
    pat = "".join([c for c in pattern.strip().upper() if c in BP_SIDES])
    if not pat:
        return None
    return patterns.get(len(pat), {}).get(pat)


def recommend_from_sequence(seq: List[str], patterns, min_sample: int = 10, max_len: int = 10) -> Dict[str, Any]:
    seq = [s for s in seq if s in BP_SIDES]
    candidates = []
    for L in range(1, min(max_len, len(seq)) + 1):
        pat = "".join(seq[-L:])
        rec = patterns.get(L, {}).get(pat)
        if not rec or rec["sample"] < min_sample:
            continue
        # A simple score: sample-adjusted edge. Conservative for small samples.
        score = rec["edge"] * min(1.0, rec["sample"] / 100.0)
        candidates.append((score, L, rec))
    if not candidates:
        return {
            "recommend_pattern": "",
            "recommend_length": 0,
            "recommend_sample": 0,
            "recommend_side": "PASS",
            "recommend_rate": 0,
            "recommend_edge": 0,
            "recommend_score": 0,
        }
    score, L, rec = sorted(candidates, key=lambda x: (x[0], x[1], x[2]["sample"]), reverse=True)[0]
    return {
        "recommend_pattern": rec["pattern"],
        "recommend_length": L,
        "recommend_sample": rec["sample"],
        "recommend_side": rec["best_side"],
        "recommend_rate": rec["best_rate"],
        "recommend_edge": rec["edge"],
        "recommend_score": round(score,4),
    }


def recommend_table(rows: List[ResultRow], patterns, table: str) -> Dict[str, Any]:
    rs = [r for r in rows if r.tableName.upper() == table.upper()]
    if not rs:
        return {"error": f"找不到桌號：{table}"}
    rs.sort(key=lambda r: (r.createdAt, r.id))
    latest_shoe = rs[-1].shoeId
    shoe_rows = [r for r in rs if r.shoeId == latest_shoe]
    shoe_rows.sort(key=lambda r: (r.playId if r.playId else r.roadLen, r.id))
    seq = [r.side for r in shoe_rows if r.side in BP_SIDES]
    ans = {
        "tableName": rs[-1].tableName,
        "latest_shoeId": latest_shoe,
        "latest_pattern_max10": "".join(seq[-10:]),
        "bp_len_in_latest_shoe": len(seq),
    }
    ans.update(recommend_from_sequence(seq, patterns))
    return ans


def export_reports(rows: List[ResultRow], patterns, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    write_summary(rows, out_dir)

    write_csv(os.path.join(out_dir, "table_report.csv"), build_table_report(rows), [
        "tableName","total","B","P","T","B_rate_all","P_rate_all","T_rate_all","B_rate_no_tie","P_rate_no_tie","shoe_count"
    ])

    write_csv(os.path.join(out_dir, "streak.csv"), build_streak(rows), ["streak_len","B_count","P_count"])
    write_csv(os.path.join(out_dir, "transition.csv"), build_transition(patterns), [
        "length","pattern","sample","next_B","next_P","next_B_rate","next_P_rate","best_side","best_rate","edge"
    ])
    write_csv(os.path.join(out_dir, "pattern_length_summary.csv"), build_pattern_length_summary(patterns), [
        "length","pattern_kinds_all","total_samples","max_sample","avg_sample","patterns_sample_ge_10","patterns_sample_ge_30","patterns_sample_ge_100"
    ])

    all_patterns = []
    for L, d in patterns.items():
        rows_l = sorted(d.values(), key=lambda r: (-r["sample"], -r["edge"], r["pattern"]))
        write_csv(os.path.join(out_dir, f"pattern_len_{L}.csv"), rows_l, [
            "length","pattern","sample","next_B","next_P","next_B_rate","next_P_rate","best_side","best_rate","edge"
        ])
        all_patterns.extend(rows_l)
    all_patterns.sort(key=lambda r: (-r["sample"], -r["edge"], r["length"], r["pattern"]))
    write_csv(os.path.join(out_dir, "pattern_all.csv"), all_patterns, [
        "length","pattern","sample","next_B","next_P","next_B_rate","next_P_rate","best_side","best_rate","edge"
    ])
    write_csv(os.path.join(out_dir, "latest_pattern_by_table.csv"), latest_pattern_by_table(rows, patterns), [
        "tableName","latest_shoeId","bp_len_in_latest_shoe","latest_pattern_max10",
        "recommend_pattern","recommend_length","recommend_sample","recommend_side","recommend_rate","recommend_edge","recommend_score"
    ])


def main():
    ap = argparse.ArgumentParser(description="DG Analyzer fixed single-file")
    ap.add_argument("--db", default="history.db", help="SQLite DB path")
    ap.add_argument("--out", default="reports_fixed", help="Output folder")
    ap.add_argument("--max-len", type=int, default=10, help="Max pattern length")
    ap.add_argument("--query", default="", help="Query pattern, e.g. BBBP")
    ap.add_argument("--recommend", default="", help="Recommend table, e.g. RB01")
    args = ap.parse_args()

    print(f"Loading database: {args.db}")
    rows = load_results(args.db)
    print(f"Rows loaded: {len(rows)}")
    print("Building pattern engine...")
    patterns = build_pattern_stats(rows, max_len=args.max_len)

    # sanity print
    print("Pattern sanity check:")
    for L in range(1, min(3, args.max_len) + 1):
        d = patterns.get(L, {})
        top = sorted(d.values(), key=lambda r: -r["sample"])[:8]
        print(f"  length={L}, kinds={len(d)}, top=" + ", ".join(f"{r['pattern']}:{r['sample']}" for r in top))

    if args.query:
        rec = query_pattern(patterns, args.query)
        if not rec:
            print(f"Pattern {args.query} 沒有資料")
        else:
            print(f"Pattern {rec['pattern']} | sample={rec['sample']} | B={rec['next_B']} ({rec['next_B_rate']}%) | P={rec['next_P']} ({rec['next_P_rate']}%) | best={rec['best_side']} {rec['best_rate']}%")

    if args.recommend:
        ans = recommend_table(rows, patterns, args.recommend)
        print("Recommend:")
        for k, v in ans.items():
            print(f"  {k}: {v}")

    print(f"Writing reports: {args.out}")
    export_reports(rows, patterns, args.out)
    print("Done.")

if __name__ == "__main__":
    main()
