import json
from datetime import datetime
from pathlib import Path


class StatusManager:
    def __init__(self, status_path: str = "data/status.json") -> None:
        self.status_path = Path(status_path)
        self.status_path.parent.mkdir(parents=True, exist_ok=True)

    def update(
        self,
        table_name: str,
        game_no: str,
        winner: str,
    ) -> None:
        now = datetime.now()

        status_data = {
            "last_update": now.strftime("%Y-%m-%d %H:%M:%S"),
            "table_name": table_name,
            "game_no": game_no,
            "winner": winner,
        }

        temp_path = self.status_path.with_suffix(".tmp")

        temp_path.write_text(
            json.dumps(
                status_data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temp_path.replace(self.status_path)