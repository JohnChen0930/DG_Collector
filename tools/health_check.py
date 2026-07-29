import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


# 專案根目錄：
# DG_Collector/tools/health_check.py
# parents[1] 就是 DG_Collector
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "history.db"

VALID_WINNERS = {"B", "P", "T"}


def print_title(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def print_section(title: str) -> None:
    print()
    print("-" * 70)
    print(title)
    print("-" * 70)


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def get_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    rows = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return {row[1] for row in rows}


def check_total_rows(connection: sqlite3.Connection) -> int:
    return connection.execute(
        "SELECT COUNT(*) FROM rounds"
    ).fetchone()[0]


def check_unique_game_no(connection: sqlite3.Connection) -> int:
    return connection.execute(
        """
        SELECT COUNT(DISTINCT game_no)
        FROM rounds
        """
    ).fetchone()[0]


def check_duplicate_game_no(
    connection: sqlite3.Connection,
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            game_no,
            COUNT(*) AS duplicate_count
        FROM rounds
        GROUP BY game_no
        HAVING COUNT(*) > 1
        ORDER BY duplicate_count DESC, game_no
        """
    ).fetchall()


def check_missing_critical_fields(
    connection: sqlite3.Connection,
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            id,
            table_name,
            game_no,
            winner
        FROM rounds
        WHERE game_no IS NULL
           OR TRIM(game_no) = ''
           OR table_name IS NULL
           OR TRIM(table_name) = ''
           OR winner IS NULL
           OR TRIM(winner) = ''
        ORDER BY id
        """
    ).fetchall()


def check_invalid_winners(
    connection: sqlite3.Connection,
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            id,
            table_name,
            game_no,
            winner
        FROM rounds
        WHERE winner IS NOT NULL
          AND winner NOT IN ('B', 'P', 'T')
        ORDER BY id
        """
    ).fetchall()


def get_winner_counts(
    connection: sqlite3.Connection,
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            winner,
            COUNT(*) AS total
        FROM rounds
        GROUP BY winner
        ORDER BY winner
        """
    ).fetchall()


def get_table_statistics(
    connection: sqlite3.Connection,
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            table_name,
            COUNT(*) AS total,
            SUM(CASE WHEN winner = 'B' THEN 1 ELSE 0 END) AS banker_count,
            SUM(CASE WHEN winner = 'P' THEN 1 ELSE 0 END) AS player_count,
            SUM(CASE WHEN winner = 'T' THEN 1 ELSE 0 END) AS tie_count,
            MAX(id) AS latest_id
        FROM rounds
        GROUP BY table_name
        ORDER BY table_name
        """
    ).fetchall()


def get_latest_rounds(
    connection: sqlite3.Connection,
    limit: int = 10,
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            id,
            table_name,
            game_no,
            round_no,
            winner
        FROM rounds
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def get_optional_missing_counts(
    connection: sqlite3.Connection,
    columns: set[str],
) -> dict[str, int]:
    optional_fields = [
        "round_no",
        "banker_point",
        "player_point",
        "banker_cards",
        "player_cards",
    ]

    result: dict[str, int] = {}

    for field_name in optional_fields:
        if field_name not in columns:
            continue

        count = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM rounds
            WHERE {field_name} IS NULL
               OR CAST({field_name} AS TEXT) = ''
            """
        ).fetchone()[0]

        result[field_name] = count

    return result


def print_winner_statistics(
    winner_rows: list[sqlite3.Row],
    total_rows: int,
) -> None:
    winner_counts = Counter()

    for row in winner_rows:
        winner_counts[row["winner"]] = row["total"]

    winner_names = {
        "B": "莊",
        "P": "閒",
        "T": "和",
    }

    for winner in ("B", "P", "T"):
        count = winner_counts.get(winner, 0)

        if total_rows > 0:
            percentage = count / total_rows * 100
        else:
            percentage = 0

        print(
            f"{winner_names[winner]} ({winner})："
            f"{count:,} 局 "
            f"({percentage:.2f}%)"
        )


def main() -> int:
    print_title("DG Collector 資料庫健康檢查")

    print(f"檢查時間：{datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"資料庫：{DB_PATH}")

    if not DB_PATH.exists():
        print()
        print("[FAIL] 找不到資料庫")
        print(f"預期位置：{DB_PATH}")
        return 1

    try:
        connection = sqlite3.connect(DB_PATH)
        connection.row_factory = sqlite3.Row
    except sqlite3.Error as error:
        print()
        print(f"[FAIL] 無法開啟資料庫：{error}")
        return 1

    try:
        if not table_exists(connection, "rounds"):
            print()
            print("[FAIL] 資料庫中找不到 rounds 資料表")
            return 1

        columns = get_columns(connection, "rounds")

        required_columns = {
            "id",
            "game_no",
            "table_name",
            "winner",
        }

        missing_columns = required_columns - columns

        if missing_columns:
            print()
            print(
                "[FAIL] rounds 缺少必要欄位："
                + ", ".join(sorted(missing_columns))
            )
            return 1

        total_rows = check_total_rows(connection)
        unique_game_no = check_unique_game_no(connection)
        duplicate_rows = check_duplicate_game_no(connection)
        missing_critical_rows = check_missing_critical_fields(connection)
        invalid_winner_rows = check_invalid_winners(connection)
        winner_rows = get_winner_counts(connection)
        table_rows = get_table_statistics(connection)
        latest_rows = get_latest_rounds(connection)
        optional_missing = get_optional_missing_counts(
            connection,
            columns,
        )

        print_section("基本資料")

        print(f"總局數：{total_rows:,}")
        print(f"唯一 game_no：{unique_game_no:,}")
        print(f"資料桌數：{len(table_rows):,}")
        print(f"資料庫大小：{DB_PATH.stat().st_size / 1024 / 1024:.2f} MB")

        print_section("莊、閒、和統計")
        print_winner_statistics(winner_rows, total_rows)

        print_section("各桌資料量")

        if not table_rows:
            print("目前沒有任何資料")
        else:
            for row in table_rows:
                print(
                    f"{row['table_name'] or '(空桌名)':<8} "
                    f"總局數={row['total']:>7,}  "
                    f"莊={row['banker_count']:>7,}  "
                    f"閒={row['player_count']:>7,}  "
                    f"和={row['tie_count']:>6,}"
                )

        print_section("重複 game_no")

        if duplicate_rows:
            print(f"[FAIL] 發現 {len(duplicate_rows):,} 組重複 game_no")

            for row in duplicate_rows[:20]:
                print(
                    f"game_no={row['game_no']} "
                    f"出現次數={row['duplicate_count']}"
                )

            if len(duplicate_rows) > 20:
                print(f"...另外還有 {len(duplicate_rows) - 20:,} 組")
        else:
            print("[PASS] 沒有重複 game_no")

        print_section("必要欄位檢查")

        if missing_critical_rows:
            print(
                f"[FAIL] 發現 {len(missing_critical_rows):,} 筆"
                "必要欄位為空"
            )

            for row in missing_critical_rows[:20]:
                print(
                    f"id={row['id']} "
                    f"table={row['table_name']} "
                    f"game_no={row['game_no']} "
                    f"winner={row['winner']}"
                )
        else:
            print("[PASS] game_no、table_name、winner 都有資料")

        print_section("winner 格式檢查")

        if invalid_winner_rows:
            print(
                f"[FAIL] 發現 {len(invalid_winner_rows):,} 筆"
                " winner 不是 B、P、T"
            )

            for row in invalid_winner_rows[:20]:
                print(
                    f"id={row['id']} "
                    f"table={row['table_name']} "
                    f"game_no={row['game_no']} "
                    f"winner={row['winner']}"
                )
        else:
            print("[PASS] 所有 winner 都是 B、P、T")

        print_section("其他欄位缺漏")

        if optional_missing:
            for field_name, missing_count in optional_missing.items():
                status = "PASS" if missing_count == 0 else "WARNING"

                print(
                    f"[{status}] "
                    f"{field_name} 空值：{missing_count:,}"
                )
        else:
            print("目前資料表沒有可檢查的其他欄位")

        print_section("最近寫入的 10 局")

        if latest_rows:
            for row in latest_rows:
                print(
                    f"id={row['id']:<7} "
                    f"table={row['table_name']:<7} "
                    f"round={str(row['round_no']):<6} "
                    f"winner={row['winner']} "
                    f"game_no={row['game_no']}"
                )
        else:
            print("目前沒有資料")

        has_failure = bool(
            duplicate_rows
            or missing_critical_rows
            or invalid_winner_rows
        )

        print_title("檢查結果")

        if total_rows == 0:
            print("[WARNING] rounds 目前是空的，尚未收集到資料")
            return 2

        if has_failure:
            print("[FAIL] 發現資料品質問題，請先檢查上方內容")
            return 1

        print("[PASS] 目前沒有發現重大資料品質問題")
        print("可以繼續蒐集資料")
        return 0

    except sqlite3.Error as error:
        print()
        print(f"[FAIL] SQLite 檢查失敗：{error}")
        return 1

    finally:
        connection.close()


if __name__ == "__main__":
    sys.exit(main())