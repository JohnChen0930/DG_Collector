from datetime import datetime
import json
from pathlib import Path


STATUS_FILE = Path("data/status.json")
WARNING_SECONDS = 300


def format_age(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} 秒"

    minutes, remaining_seconds = divmod(seconds, 60)

    if minutes < 60:
        return f"{minutes} 分 {remaining_seconds} 秒"

    hours, remaining_minutes = divmod(minutes, 60)
    return f"{hours} 小時 {remaining_minutes} 分"


def main() -> None:
    print("=" * 70)
    print("DG Collector 狀態檢查")
    print("=" * 70)

    if not STATUS_FILE.exists():
        print("[UNKNOWN] 找不到 data/status.json")
        print("Collector 可能尚未成功寫入新資料。")
        return

    try:
        status = json.loads(
            STATUS_FILE.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        print(f"[ERROR] 無法讀取狀態檔：{error}")
        return

    last_update_text = status.get("last_update")

    if not last_update_text:
        print("[ERROR] status.json 缺少 last_update")
        return

    try:
        last_update = datetime.strptime(
            last_update_text,
            "%Y-%m-%d %H:%M:%S",
        )
    except ValueError:
        print(f"[ERROR] 時間格式錯誤：{last_update_text}")
        return

    now = datetime.now()
    age_seconds = max(
        0,
        int((now - last_update).total_seconds()),
    )

    if age_seconds <= WARNING_SECONDS:
        state = "RUNNING"
        label = "[PASS]"
    else:
        state = "可能停止或卡住"
        label = "[WARNING]"

    print(f"{label} Collector：{state}")
    print(f"目前時間：{now:%Y-%m-%d %H:%M:%S}")
    print(f"最後更新：{last_update_text}")
    print(f"距離現在：{format_age(age_seconds)}")
    print()
    print(f"最後桌台：{status.get('table_name', 'UNKNOWN')}")
    print(f"最後局號：{status.get('game_no', 'UNKNOWN')}")
    print(f"最後結果：{status.get('winner', 'UNKNOWN')}")
    print("=" * 70)


if __name__ == "__main__":
    main()