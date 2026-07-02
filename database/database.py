import os
import json
import sqlite3
from datetime import datetime


class Database:
    def __init__(self, db_file):
        self.db_file = db_file
        db_dir = os.path.dirname(db_file)

        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self.conn = sqlite3.connect(db_file)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.create_tables()

    def now(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def create_tables(self):
        cur = self.conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS tables (
            tableId INTEGER PRIMARY KEY,
            tableName TEXT NOT NULL,
            gameName TEXT,
            createdAt TEXT,
            updatedAt TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS shoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tableId INTEGER NOT NULL,
            tableName TEXT NOT NULL,
            shoeNo INTEGER NOT NULL,
            startTime TEXT,
            endTime TEXT,
            startPlayId INTEGER,
            endPlayId INTEGER,
            startRoadLen INTEGER,
            endRoadLen INTEGER,
            FOREIGN KEY(tableId) REFERENCES tables(tableId)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shoeId INTEGER NOT NULL,
            tableId INTEGER NOT NULL,
            tableName TEXT NOT NULL,
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
            totalAmount REAL,
            createdAt TEXT,
            FOREIGN KEY(shoeId) REFERENCES shoes(id),
            FOREIGN KEY(tableId) REFERENCES tables(tableId)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resultId INTEGER,
            shoeId INTEGER,
            tableId INTEGER,
            tableName TEXT,
            playId INTEGER,
            predictSide TEXT,
            confidence REAL,
            actualSide TEXT,
            isWin INTEGER,
            modelName TEXT,
            createdAt TEXT,
            FOREIGN KEY(resultId) REFERENCES results(id),
            FOREIGN KEY(shoeId) REFERENCES shoes(id)
        )
        """)

        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_results_table_shoe_play
        ON results(tableName, shoeId, playId)
        """)

        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_shoes_table
        ON shoes(tableName, shoeNo)
        """)

        self.conn.commit()

    def upsert_table(self, table):
        cur = self.conn.cursor()

        cur.execute("""
        INSERT INTO tables (
            tableId,
            tableName,
            gameName,
            createdAt,
            updatedAt
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(tableId) DO UPDATE SET
            tableName = excluded.tableName,
            gameName = excluded.gameName,
            updatedAt = excluded.updatedAt
        """, (
            table.get("tableId", 0),
            table.get("tableName", ""),
            table.get("gameName", ""),
            self.now(),
            self.now()
        ))

        self.conn.commit()

    def create_shoe(self, table, shoe_no):
        self.upsert_table(table)

        cur = self.conn.cursor()

        cur.execute("""
        INSERT INTO shoes (
            tableId,
            tableName,
            shoeNo,
            startTime,
            startPlayId,
            startRoadLen
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            table.get("tableId", 0),
            table.get("tableName", ""),
            shoe_no,
            self.now(),
            table.get("playId", 0),
            table.get("roadLen", 0)
        ))

        self.conn.commit()
        return cur.lastrowid

    def close_shoe(self, shoe_id, table):
        cur = self.conn.cursor()

        cur.execute("""
        UPDATE shoes
        SET
            endTime = ?,
            endPlayId = ?,
            endRoadLen = ?
        WHERE id = ?
        """, (
            self.now(),
            table.get("playId", 0),
            table.get("roadLen", 0),
            shoe_id
        ))

        self.conn.commit()

    def insert_result(self, table, shoe_db_id, result_code, side):
        latest = table.get("latest")
        latest_road = ""

        if isinstance(latest, dict):
            latest_road = json.dumps(latest.get("road", ""), ensure_ascii=False)

        cur = self.conn.cursor()

        cur.execute("""
        INSERT INTO results (
            shoeId,
            tableId,
            tableName,
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
            totalAmount,
            createdAt
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            shoe_db_id,
            table.get("tableId", 0),
            table.get("tableName", ""),
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
            table.get("totalAmount", 0),
            self.now()
        ))

        self.conn.commit()
        return cur.lastrowid
    

    def get_latest_shoe_by_table(self, table_id):
        cur = self.conn.cursor()

        row = cur.execute("""
        SELECT id, shoeNo, endTime
        FROM shoes
        WHERE tableId = ?
        ORDER BY id DESC
        LIMIT 1
        """, (table_id,)).fetchone()

        if not row:
            return None

        return {
            "shoeDbId": row[0],
            "shoeNo": row[1],
            "endTime": row[2],
        }

    def get_last_result_by_shoe(self, shoe_db_id):
        cur = self.conn.cursor()

        row = cur.execute("""
        SELECT playId, roadLen, gameNo
        FROM results
        WHERE shoeId = ?
        ORDER BY id DESC
        LIMIT 1
        """, (shoe_db_id,)).fetchone()

        if not row:
            return None

        return {
            "playId": row[0],
            "roadLen": row[1],
            "gameNo": row[2],
        }

    def restore_table_state(self, table):
        table_id = table.get("tableId")
        road_len = table.get("roadLen", 0)
        play_id = table.get("playId", 0)
        game_no = table.get("gameNo", "")

        latest_shoe = self.get_latest_shoe_by_table(table_id)

        if latest_shoe is None or latest_shoe.get("endTime") is not None:
            shoe_no = 1 if latest_shoe is None else latest_shoe["shoeNo"] + 1
            shoe_db_id = self.create_shoe(table, shoe_no)

            return {
                "roadLen": road_len,
                "playId": play_id,
                "gameNo": game_no,
                "shoeNo": shoe_no,
                "shoeDbId": shoe_db_id,
            }

        last_result = self.get_last_result_by_shoe(latest_shoe["shoeDbId"])

        return {
            "roadLen": road_len,
            "playId": play_id,
            "gameNo": game_no,
            "shoeNo": latest_shoe["shoeNo"],
            "shoeDbId": latest_shoe["shoeDbId"],
        }

    def close(self):
        self.conn.close()