import time
from models.round import Round
from collector.parser import is_baccarat_table, result_to_side
from utils.logger import logger


class DGCollector:
    def __init__(
        self,
        browser,
        database,
        exclude_tables=None,
        poll_interval=1,
    ):
        self.browser = browser
        self.database = database
        self.exclude_tables = exclude_tables or []
        self.poll_interval = poll_interval
        self.last_state = {}

    def start(self):
        """啟動 DG 資料收集器。"""
        self.browser.login_and_open_dg()

        self.browser.switch_to_laya_frame()

        if not self.browser.wait_laya_ready(60):
            raise RuntimeError("Laya 資料沒有載入完成")

        logger.info("DG Collector 開始收集資料")

        try:
            while True:
                self.collect_once()
                time.sleep(self.poll_interval)

        except KeyboardInterrupt:
            logger.info("使用者停止 Collector")

        finally:
            self.browser.quit()

    def collect_once(self):
        """取得一次所有桌台資料並逐桌處理。"""
        tables = self.browser.get_tables()

        for table in tables:
            try:
                self.handle_table(table)
            except Exception:
                logger.exception(
                    "處理桌台失敗："
                    f"{table.get('tableName', 'UNKNOWN')}"
                )

    def handle_table(self, table):
        """處理單一桌台。"""
        table_id = str(table.get("tableId", ""))
        table_name = table.get("tableName", "")
        game_no = str(table.get("gameNo", ""))
        play_id = int(table.get("playId", 0) or 0)
        road_len = int(table.get("roadLen", 0) or 0)
        result = table.get("result", "")
        latest = table.get("latest")

        if not is_baccarat_table(
            table_name,
            self.exclude_tables,
        ):
            return

        if not table_id:
            return

        if road_len <= 0 or latest is None:
            return

        current_state = {
            "roadLen": road_len,
            "playId": play_id,
            "gameNo": game_no,
        }

        # 第一次看到桌台時，只建立狀態，不把現有最後一局重複寫入
        if table_id not in self.last_state:
            self.last_state[table_id] = current_state

            logger.info(
                f"INIT {table_name} "
                f"roadLen={road_len} "
                f"playId={play_id} "
                f"gameNo={game_no}"
            )
            return

        old_state = self.last_state[table_id]

        old_road_len = old_state["roadLen"]
        old_play_id = old_state["playId"]
        old_game_no = old_state["gameNo"]

        # 新鞋：路單長度或局號回退
        if road_len < old_road_len or play_id < old_play_id:
            logger.info(
                f"NEW_SHOE {table_name} "
                f"roadLen={old_road_len}->{road_len} "
                f"playId={old_play_id}->{play_id}"
            )

            self.last_state[table_id] = current_state
            return

        is_new_result = (
            road_len > old_road_len
            or (
                game_no
                and old_game_no
                and game_no != old_game_no
            )
        )

        if not is_new_result:
            return

        # 已看到新局，但 result 還沒更新，下輪再讀
        if not result:
            logger.info(
                f"WAIT_RESULT {table_name} "
                f"roadLen={road_len} "
                f"playId={play_id}"
            )
            return

        winner = result_to_side(result)

        if not winner or winner.startswith("UNKNOWN"):
            logger.warning(
                f"UNKNOWN_RESULT {table_name} "
                f"result={result} "
                f"playId={play_id} "
                f"gameNo={game_no}"
            )
            return

        round_data = self.create_round(
            table=table,
            winner=winner,
        )

        inserted = self.database.insert_round(round_data)

        if inserted:
            logger.info(
                f"INSERT {table_name} "
                f"gameNo={game_no} "
                f"roundNo={play_id} "
                f"winner={winner} "
                f"result={result}"
            )
        else:
            logger.info(
                f"SKIP_DUPLICATE {table_name} "
                f"gameNo={game_no}"
            )

        # 寫入成功或資料庫判定重複後都更新狀態
        self.last_state[table_id] = current_state

    def create_round(self, table, winner):
        """將 DG 桌台資料轉成 Round。"""
        poker = table.get("poker", "")
        win_point = table.get("winPoint", "")

        banker_cards, player_cards = self.parse_poker(poker)
        banker_point, player_point = self.parse_win_point(win_point)

        return Round(
            shoe_id=self.build_shoe_id(table),
            game_no=str(table.get("gameNo", "")),
            table_name=table.get("tableName", ""),
            round_no=int(table.get("playId", 0) or 0),
            winner=winner,
            banker_point=banker_point,
            player_point=player_point,
            banker_cards=banker_cards,
            player_cards=player_cards,
        )

    @staticmethod
    def build_shoe_id(table):
        """
        暫時用桌名加 gameNo 前段組成 shoe_id。

        後續確認 DG 真正鞋號後，再替換這裡。
        """
        table_name = table.get("tableName", "")
        game_no = str(table.get("gameNo", ""))

        if game_no:
            return f"{table_name}-{game_no[:12]}"

        return f"{table_name}-UNKNOWN"

    @staticmethod
    def parse_poker(poker):
        """
        支援可能的 poker 格式：

        dict:
        {
            "banker": "51-35-0",
            "player": "21-6-0"
        }

        其他格式暫時原樣保存。
        """
        if isinstance(poker, dict):
            banker_cards = str(poker.get("banker", ""))
            player_cards = str(poker.get("player", ""))

            return banker_cards, player_cards

        poker_text = str(poker or "")
        return poker_text, ""

    @staticmethod
    def parse_win_point(win_point):
        """
        支援 dict 或字串形式的點數。

        無法解析時回傳 None。
        """
        banker_point = None
        player_point = None

        if isinstance(win_point, dict):
            banker_point = DGCollector.to_int_or_none(
                win_point.get("banker")
            )
            player_point = DGCollector.to_int_or_none(
                win_point.get("player")
            )

        elif isinstance(win_point, str) and "," in win_point:
            parts = win_point.split(",")

            if len(parts) >= 2:
                banker_point = DGCollector.to_int_or_none(parts[0])
                player_point = DGCollector.to_int_or_none(parts[1])

        return banker_point, player_point

    @staticmethod
    def to_int_or_none(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None