import sqlite3
import json
from datetime import datetime


class Database:
    def __init__(self, db_file="history.db"):
        self.db_file = db_file
        self.conn = sqlite3.connect(self.db_file)
        self.create_tables()

    def create_tables(self):
        cur = self.conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            createdAt TEXT,
            tableId INTEGER,
            tableName TEXT,
            shoeId INTEGER,
            gameNo TEXT,
            playId INTEGER,
            roadLen INTEGER,
            resultRaw TEXT,
            resultCode TEXT,
            side TEXT,
            poker TEXT,
            winPoint INTEGER,
            stateId INTEGER,
            dealerName TEXT,
            latestRoad TEXT,
            onlineCount INTEGER,
            totalAmount REAL
        )
        """)

        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_results_table_shoe
        ON results(tableName, shoeId, playId)
        """)

        self.conn.commit()

    def insert_result(self, table, shoe_id, result_code, side):
        latest = table.get("latest")
        latest_road = ""

        if isinstance(latest, dict):
            latest_road = json.dumps(latest.get("road", ""), ensure_ascii=False)

        cur = self.conn.cursor()

        cur.execute("""
        INSERT INTO results (
            createdAt,
            tableId,
            tableName,
            shoeId,
            gameNo,
            playId,
            roadLen,
            resultRaw,
            resultCode,
            side,
            poker,
            winPoint,
            stateId,
            dealerName,
            latestRoad,
            onlineCount,
            totalAmount
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            table.get("tableId", 0),
            table.get("tableName", ""),
            shoe_id,
            table.get("gameNo", ""),
            table.get("playId", 0),
            table.get("roadLen", 0),
            table.get("result", ""),
            result_code,
            side,
            table.get("poker", ""),
            table.get("winPoint", 0),
            table.get("stateId", 0),
            table.get("dealerName", ""),
            latest_road,
            table.get("onlineCount", 0),
            table.get("totalAmount", 0)
        ))

        self.conn.commit()

    def close(self):
        self.conn.close()