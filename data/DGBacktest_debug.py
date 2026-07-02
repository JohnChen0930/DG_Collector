# -*- coding: utf-8 -*-
print("DGBacktest_debug 啟動中...")

import argparse, csv, os, sqlite3
from collections import defaultdict, Counter
from dataclasses import dataclass

BP = {"B", "P"}

@dataclass
class ResultRow:
    id: int
    tableName: str
    shoeId: int
    gameNo: str
    playId: object
    roadLen: object
    side: str
    createdAt: str

def safe_rate(n, d):
    return (n / d) if d else 0.0

def write_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not rows:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            f.write("")
        return
    fields = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

def load_rows(db_path):
    print(f"讀取 DB: {db_path}")
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"DB 不存在：{db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    print("資料表:", tables)
    if "results" not in tables:
        raise RuntimeError("找不到 results 資料表")
    cnt = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    print("results 總筆數:", cnt)
    sql = """
        SELECT id, tableName, shoeId, gameNo, playId, roadLen, side, createdAt
        FROM results
        WHERE side IS NOT NULL
        ORDER BY datetime(createdAt), id
    """
    rows = []
    for r in conn.execute(sql):
        side = str(r["side"]).strip().upper()
        if side not in {"B", "P", "T"}:
            continue
        rows.append(ResultRow(
            id=int(r["id"]), tableName=str(r["tableName"]),
            shoeId=int(r["shoeId"]), gameNo=str(r["gameNo"]),
            playId=r["playId"], roadLen=r["roadLen"],
            side=side, createdAt=str(r["createdAt"])
        ))
    conn.close()
    print("可用 B/P/T 筆數:", len(rows))
    return rows

def clean_keep_last_by_game_no(rows):
    by_game = {}
    side_sets = defaultdict(set)
    for r in rows:
        side_sets[r.gameNo].add(r.side)
        by_game[r.gameNo] = r
    changed = sum(1 for s in side_sets.values() if len(s) > 1)
    clean_rows = sorted(by_game.values(), key=lambda x: (x.createdAt, x.id))
    quality = [{
        "raw_rows": len(rows),
        "unique_gameNo": len(by_game),
        "removed_duplicate_rows": len(rows) - len(clean_rows),
        "gameNo_with_side_changed": changed,
        "clean_rows": len(clean_rows),
    }]
    return clean_rows, quality

def table_counts(rows):
    d = defaultdict(Counter)
    for r in rows:
        d[r.tableName][r.side] += 1
        d[r.tableName]["TOTAL"] += 1
    out = []
    for table, c in sorted(d.items()):
        total = c["TOTAL"]
        bp_total = c["B"] + c["P"]
        out.append({
            "tableName": table, "total": total,
            "B": c["B"], "P": c["P"], "T": c["T"],
            "B_rate_all": round(safe_rate(c["B"], total) * 100, 4),
            "P_rate_all": round(safe_rate(c["P"], total) * 100, 4),
            "T_rate_all": round(safe_rate(c["T"], total) * 100, 4),
            "B_rate_no_tie": round(safe_rate(c["B"], bp_total) * 100, 4),
            "P_rate_no_tie": round(safe_rate(c["P"], bp_total) * 100, 4),
        })
    return out

class OnlinePatternBacktester:
    def __init__(self, lengths, min_samples, min_rates, scope="global"):
        self.lengths = lengths
        self.min_samples = min_samples
        self.min_rates = min_rates
        self.scope = scope
        self.seq = defaultdict(list)
        self.stats = defaultdict(Counter)
        self.grid = defaultdict(Counter)
        self.prediction_details = []

    def stat_key(self, table, length, pattern):
        return (table, length, pattern) if self.scope == "table" else (length, pattern)

    def get_counter(self, table, length, pattern):
        return self.stats[self.stat_key(table, length, pattern)]

    def evaluate(self, r, length, pattern, actual):
        c = self.get_counter(r.tableName, length, pattern)
        b, p = c["B"], c["P"]
        sample = b + p
        if sample <= 0:
            return
        best_side = "B" if b >= p else "P"
        best_rate = max(b, p) / sample
        for ms in self.min_samples:
            if sample < ms:
                continue
            for mr in self.min_rates:
                g = self.grid[(length, ms, mr)]
                if best_rate >= mr:
                    g["bet"] += 1
                    if best_side == actual:
                        g["win"] += 1
                    else:
                        g["loss"] += 1
                else:
                    g["pass"] += 1
        if sample >= min(self.min_samples) and best_rate >= min(self.min_rates):
            self.prediction_details.append({
                "id": r.id, "createdAt": r.createdAt, "tableName": r.tableName,
                "shoeId": r.shoeId, "gameNo": r.gameNo,
                "length": length, "pattern": pattern,
                "sample": sample, "next_B": b, "next_P": p,
                "best_side": best_side, "best_rate": round(best_rate * 100, 4),
                "actual": actual, "is_win": 1 if best_side == actual else 0,
            })

    def update_stats(self, r, actual):
        s = self.seq[(r.tableName, r.shoeId)]
        for L in self.lengths:
            if len(s) >= L:
                pattern = "".join(s[-L:])
                self.get_counter(r.tableName, L, pattern)[actual] += 1
        s.append(actual)

    def run(self, rows):
        print("開始回測...")
        processed = 0
        for r in rows:
            if r.side not in BP:
                continue
            s = self.seq[(r.tableName, r.shoeId)]
            for L in self.lengths:
                if len(s) >= L:
                    pattern = "".join(s[-L:])
                    self.evaluate(r, L, pattern, r.side)
            self.update_stats(r, r.side)
            processed += 1
        print("回測 B/P 局數:", processed)
        print("Pattern 統計數:", len(self.stats))
        for L in self.lengths:
            for ms in self.min_samples:
                for mr in self.min_rates:
                    self.grid[(L, ms, mr)] += Counter()

    def grid_rows(self):
        out = []
        for (L, ms, mr), c in sorted(self.grid.items()):
            bet, win, loss = c["bet"], c["win"], c["loss"]
            out.append({
                "length": L, "min_sample": ms, "min_rate": round(mr * 100, 2),
                "bet_count": bet, "win": win, "loss": loss,
                "hit_rate": round(safe_rate(win, bet) * 100, 4),
                "pass_count": c["pass"],
            })
        return out

    def top_rows(self, min_bets=100):
        rows = [r for r in self.grid_rows() if r["bet_count"] >= min_bets]
        rows.sort(key=lambda x: (x["hit_rate"], x["bet_count"]), reverse=True)
        return rows

    def pattern_summary_rows(self):
        out = []
        for key, c in self.stats.items():
            if self.scope == "table":
                table, L, pattern = key
            else:
                table = "ALL"
                L, pattern = key
            b, p = c["B"], c["P"]
            sample = b + p
            if sample <= 0:
                continue
            best_side = "B" if b >= p else "P"
            best_rate = max(b, p) / sample
            out.append({
                "scope": self.scope, "tableName": table,
                "length": L, "pattern": pattern, "sample": sample,
                "next_B": b, "next_P": p,
                "B_rate": round(safe_rate(b, sample) * 100, 4),
                "P_rate": round(safe_rate(p, sample) * 100, 4),
                "best_side": best_side,
                "best_rate": round(best_rate * 100, 4),
            })
        out.sort(key=lambda x: (x["length"], -x["sample"], x["pattern"]))
        return out

def parse_ints(s):
    return [int(x.strip()) for x in s.split(",") if x.strip()]

def parse_rates(s):
    out = []
    for x in s.split(","):
        x = x.strip()
        if x:
            v = float(x)
            if v > 1:
                v /= 100.0
            out.append(v)
    return out

def main():
    print("進入 main()")
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="history.db")
    ap.add_argument("--out", default="reports_backtest_debug")
    ap.add_argument("--scope", choices=["global", "table"], default="global")
    ap.add_argument("--lengths", default="2,3,4,5,6,7,8")
    ap.add_argument("--min-samples", default="30,50,100,200,300")
    ap.add_argument("--min-rates", default="55,56,57,58,59,60")
    ap.add_argument("--detail-limit", type=int, default=50000)
    args = ap.parse_args()

    rows_raw = load_rows(args.db)
    rows_clean, quality = clean_keep_last_by_game_no(rows_raw)
    lengths = parse_ints(args.lengths)
    min_samples = parse_ints(args.min_samples)
    min_rates = parse_rates(args.min_rates)
    os.makedirs(args.out, exist_ok=True)

    write_csv(os.path.join(args.out, "data_quality.csv"), quality)
    write_csv(os.path.join(args.out, "table_counts_raw.csv"), table_counts(rows_raw))
    write_csv(os.path.join(args.out, "table_counts_clean.csv"), table_counts(rows_clean))

    print(f"Raw rows: {len(rows_raw)}")
    print(f"Clean rows: {len(rows_clean)}")
    print(f"Removed duplicates: {len(rows_raw) - len(rows_clean)}")
    print(f"Scope: {args.scope}")

    bt = OnlinePatternBacktester(lengths, min_samples, min_rates, args.scope)
    bt.run(rows_clean)

    grid = bt.grid_rows()
    top = bt.top_rows(min_bets=100)

    write_csv(os.path.join(args.out, "backtest_grid.csv"), grid)
    write_csv(os.path.join(args.out, "backtest_top.csv"), top[:200])
    write_csv(os.path.join(args.out, "pattern_summary.csv"), bt.pattern_summary_rows())
    write_csv(os.path.join(args.out, "prediction_details.csv"), bt.prediction_details[:args.detail_limit])

    print("\nTop strategies (bet_count >= 100):")
    for r in top[:20]:
        print(f"L={r['length']} sample>={r['min_sample']} rate>={r['min_rate']}% | bets={r['bet_count']} hit={r['hit_rate']}%")
    print(f"\nDone. Reports written to: {args.out}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("發生錯誤：", repr(e))
        raise
