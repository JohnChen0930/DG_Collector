import time

from collector.parser import (
    is_baccarat_table,
    parse_result_code,
    result_to_side,
)

from utils.logger import logger


class DGCollector:
    def __init__(self, browser, database, exclude_tables=None, poll_interval=1):
        self.browser = browser
        self.database = database
        self.exclude_tables = exclude_tables or []
        self.poll_interval = poll_interval
        self.last_state = {}

    def start(self):
        self.browser.login_and_open_dg()

        if not self.browser.switch_to_laya_frame():
            raise Exception("找不到 Laya iframe")

        if not self.browser.wait_laya_ready(60):
            raise Exception("Laya 資料沒有載入完成")

        logger.info("DG Collector 開始收集資料")

        while True:
            try:
                self.collect_once()
                time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                logger.info("手動停止")
                break

            except Exception as e:
                logger.exception(f"Collector 錯誤: {e}")

                try:
                    if self.browser.switch_to_laya_frame():
                        self.browser.wait_laya_ready(60)
                except Exception as e2:
                    logger.exception(f"重新切 iframe 失敗: {e2}")

                time.sleep(2)

    def collect_once(self):
        tables = self.browser.get_tables()

        for table in tables:
            self.handle_table(table)

    def get_table_by_id(self, table_id):
        tables = self.browser.get_tables()

        for t in tables:
            if str(t.get("tableId")) == str(table_id):
                return t

        return None

    def wait_complete_table(self, table_id, timeout=2.0):
        start = time.time()
        last_table = None

        while time.time() - start < timeout:
            table = self.get_table_by_id(table_id)

            if table is not None:
                last_table = table

                result = table.get("result", "")
                poker = table.get("poker", "")

                # result 一定要有；poker 有最好，沒有也不阻擋
                if result:
                    if poker:
                        return table

                    # 先等一下 poker
                    time.sleep(0.1)
                    continue

            time.sleep(0.1)

        return last_table

    def handle_table(self, table):
        table_id = table.get("tableId")
        table_name = table.get("tableName", "")
        play_id = table.get("playId", 0)
        road_len = table.get("roadLen", 0)
        game_no = table.get("gameNo", "")
        latest = table.get("latest")

        if not is_baccarat_table(table_name, self.exclude_tables):
            return

        if road_len == 0 or latest is None:
            return

        key = str(table_id)

        if key not in self.last_state:
            state = self.database.restore_table_state(table)

            self.last_state[key] = state

            logger.info(
                f"恢復/初始化 {table_name} "
                f"shoeNo={state['shoeNo']} "
                f"shoeDbId={state['shoeDbId']} "
                f"roadLen={state['roadLen']} "
                f"playId={state['playId']}"
            )
            return

        old = self.last_state[key]

        old_len = old["roadLen"]
        old_play_id = old["playId"]
        old_game_no = old.get("gameNo", "")
        old_shoe_no = old["shoeNo"]
        old_shoe_db_id = old["shoeDbId"]

        # 洗牌 / 新鞋
        if road_len < old_len or play_id < old_play_id:
            self.handle_new_shoe(
                table=table,
                old_shoe_db_id=old_shoe_db_id,
                old_shoe_no=old_shoe_no,
                old_len=old_len,
                old_play_id=old_play_id,
            )
            return

        is_new_result = road_len > old_len or (
            game_no and game_no != old_game_no
        )

        if is_new_result:
            self.handle_new_result(
                table=table,
                old_shoe_db_id=old_shoe_db_id,
                old_shoe_no=old_shoe_no,
            )

    def handle_new_shoe(
        self,
        table,
        old_shoe_db_id,
        old_shoe_no,
        old_len,
        old_play_id,
    ):
        table_id = table.get("tableId")
        table_name = table.get("tableName", "")
        play_id = table.get("playId", 0)
        road_len = table.get("roadLen", 0)
        game_no = table.get("gameNo", "")

        self.database.close_shoe(old_shoe_db_id, table)

        new_shoe_no = old_shoe_no + 1
        new_shoe_db_id = self.database.create_shoe(table, new_shoe_no)

        logger.info(
            f"NEW_SHOE {table_name} "
            f"shoeNo {old_shoe_no}->{new_shoe_no} "
            f"shoeDbId {old_shoe_db_id}->{new_shoe_db_id} "
            f"roadLen {old_len}->{road_len} "
            f"playId {old_play_id}->{play_id}"
        )

        self.last_state[str(table_id)] = {
            "roadLen": road_len,
            "playId": play_id,
            "gameNo": game_no,
            "shoeNo": new_shoe_no,
            "shoeDbId": new_shoe_db_id,
        }

    def handle_new_result(self, table, old_shoe_db_id, old_shoe_no):
        table_id = table.get("tableId")
        table_name = table.get("tableName", "")

        fresh_table = self.wait_complete_table(table_id, timeout=2.0)

        if fresh_table is not None:
            table = fresh_table

        play_id = table.get("playId", 0)
        road_len = table.get("roadLen", 0)
        game_no = table.get("gameNo", "")
        result = table.get("result", "")
        poker = table.get("poker", "")

        code = parse_result_code(result)
        side = result_to_side(result)

        # result 還沒完整：不寫 DB、不更新 last_state，下輪補抓
        if not result:
            logger.info(
                f"WAIT_RESULT {table_name} "
                f"playId={play_id} "
                f"gameNo={game_no}"
            )
            return

        # 代碼未知：不寫 DB、不更新 last_state，下輪補抓或等你補 RESULT_MAP
        if side.startswith("UNKNOWN"):
            logger.warning(
                f"UNKNOWN_RESULT {table_name} "
                f"result={result} "
                f"code={code} "
                f"playId={play_id} "
                f"gameNo={game_no}"
            )
            return

        result_id = self.database.insert_result(
            table=table,
            shoe_db_id=old_shoe_db_id,
            result_code=code,
            side=side,
        )

        logger.info(
            f"RESULT {table_name} "
            f"shoeNo={old_shoe_no} "
            f"shoeDbId={old_shoe_db_id} "
            f"resultId={result_id} "
            f"playId={play_id} "
            f"gameNo={game_no} "
            f"result={result} "
            f"code={code} "
            f"side={side} "
            f"poker={poker}"
        )

        self.last_state[str(table_id)] = {
            "roadLen": road_len,
            "playId": play_id,
            "gameNo": game_no,
            "shoeNo": old_shoe_no,
            "shoeDbId": old_shoe_db_id,
        }