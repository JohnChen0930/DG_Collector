from pathlib import Path
import sqlite3
from typing import Optional


class Database:
    def __init__(self, db_path: str = "data/history.db") -> None:
        self.db_path = Path(db_path)

        # 確保 data 資料夾存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.connection: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """連接 SQLite 資料庫。"""
        if self.connection is not None:
            return

        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row

        # 開啟外鍵約束
        self.connection.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        """關閉資料庫連線。"""
        if self.connection is None:
            return

        self.connection.close()
        self.connection = None

    def initialize(self) -> None:
        """建立目前需要的資料表。"""
        self.connect()

        if self.connection is None:
            raise RuntimeError("資料庫連線建立失敗")

        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS shoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                shoe_no TEXT NOT NULL,
                start_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                end_time TEXT,

                UNIQUE(table_name, shoe_no)
            );

            CREATE TABLE IF NOT EXISTS rounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shoe_id INTEGER,
                game_no TEXT NOT NULL UNIQUE,
                table_name TEXT NOT NULL,
                round_no INTEGER,
                winner TEXT NOT NULL CHECK(winner IN ('B', 'P', 'T')),

                banker_point INTEGER,
                player_point INTEGER,

                banker_cards TEXT,
                player_cards TEXT,

                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(shoe_id)
                    REFERENCES shoes(id)
                    ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_rounds_table_name
                ON rounds(table_name);

            CREATE INDEX IF NOT EXISTS idx_rounds_shoe_id
                ON rounds(shoe_id);

            CREATE INDEX IF NOT EXISTS idx_rounds_created_at
                ON rounds(created_at);
            """
        )

        self.connection.commit()

    def __enter__(self) -> "Database":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()