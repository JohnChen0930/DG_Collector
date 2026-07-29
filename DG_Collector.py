import time
import csv
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


URL = "https://laicai777.com/"
ACCOUNT = "dda017"
PASSWORD = "john0930"

CSV_FILE = "dg_history.csv"

RESULT_MAP = {
    "1": "莊",  #莊贏
    "2": "莊",  #莊贏 莊對
    "3": "莊",  #莊贏 閒對
    "5": "閒",  #閒贏
    "6": "閒",  #閒贏 莊對
    "7": "閒",  #閒贏 閒對
    "9": "和",  #和
    # ?? 和
    "11": "和"  
}

last_state = {}


chrome_options = Options()
chrome_options.add_argument(r"--user-data-dir=C:\DGChromeProfile")
chrome_options.add_argument("--start-maximized")

driver = webdriver.Chrome(options=chrome_options)


def click_by_xpath(xpath, wait=1):
    el = driver.find_element(By.XPATH, xpath)
    driver.execute_script("arguments[0].click();", el)
    time.sleep(wait)


def login_and_open_dg():
    driver.get(URL)
    time.sleep(2)

    click_by_xpath("//img[contains(@src,'FaviconUpcasino_dg')]", 1)

    account_input = driver.find_element(By.XPATH, "//input[@placeholder='請填寫8-20位的字母或數字']")
    account_input.clear()
    account_input.send_keys(ACCOUNT)

    pw_input = driver.find_element(By.XPATH, "//input[contains(@class,'password-input')]")
    pw_input.clear()
    pw_input.send_keys(PASSWORD)

    click_by_xpath("//button[contains(@class,'base-btn')]", 1)

    try:
        click_by_xpath("//p[text()='確定']", 2)
    except Exception:
        pass

    click_by_xpath("//img[contains(@src,'FaviconUpcasino_dg')]", 10)


def switch_to_laya_frame():
    driver.switch_to.default_content()

    frames = driver.find_elements(By.TAG_NAME, "iframe")

    for i, frame in enumerate(frames):
        driver.switch_to.default_content()
        driver.switch_to.frame(frame)

        has_laya = driver.execute_script("return typeof Laya !== 'undefined';")

        if has_laya:
            print("找到 Laya iframe:", i)
            return True

    return False


def wait_laya_ready(timeout=30):
    start = time.time()

    while time.time() - start < timeout:
        try:
            ready = driver.execute_script("""
                return typeof Laya !== 'undefined'
                    && Laya.stage
                    && Laya.stage.numChildren > 0
                    && Laya.stage.getChildAt(0)
                    && Laya.stage.getChildAt(0).gameDataMan
                    && Laya.stage.getChildAt(0).gameDataMan.dataInfo
                    && Laya.stage.getChildAt(0).gameDataMan.dataInfo.length > 0;
            """)
            if ready:
                return True
        except Exception:
            pass

        time.sleep(1)

    return False


def get_tables():
    js = """
    const data = Laya.stage.getChildAt(0).gameDataMan.dataInfo;

    return JSON.parse(JSON.stringify(data.map(t => ({
        tableId: t.tableId,
        tableName: t.tableName || "",
        gameName: t.gameName || "",
        gameNo: t.gameNo || "",
        playId: t.playId || 0,
        result: t.result || "",
        roadLen: t.roadArray ? t.roadArray.length : 0,
        latest: (t.roadArray && t.roadArray.length > 0)
            ? t.roadArray[t.roadArray.length - 1]
            : null
    }))));
    """
    return driver.execute_script(js)


def is_baccarat_table(name):
    if not name:
        return False

    if name in ["S08"]:
        return False

    return name.startswith("RB") or name.startswith("S")


def parse_result_code(result):
    if not result:
        return ""

    return str(result).split(",")[0]


def result_to_side(result):
    code = parse_result_code(result)
    return code, RESULT_MAP.get(code, f"未知({code})")


def ensure_csv():
    if os.path.exists(CSV_FILE):
        return

    with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "time",
            "tableId",
            "tableName",
            "gameNo",
            "playId",
            "roadLen",
            "resultRaw",
            "resultCode",
            "side"
        ])


def save_result(table, side):
    result = table.get("result", "")
    code = parse_result_code(result)

    with open(CSV_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            table.get("tableId", ""),
            table.get("tableName", ""),
            table.get("gameNo", ""),
            table.get("playId", 0),
            table.get("roadLen", 0),
            result,
            code,
            side
        ])


def main():
    ensure_csv()

    login_and_open_dg()

    self.browser.switch_to_laya_frame()

    if not wait_laya_ready():
        raise Exception("Laya 資料沒有載入完成")

    print("DGCollector 開始收集資料...")

    while True:
        try:
            tables = get_tables()

            for table in tables:
                table_id = table.get("tableId")
                table_name = table.get("tableName", "")
                play_id = table.get("playId", 0)
                road_len = table.get("roadLen", 0)
                result = table.get("result", "")
                latest = table.get("latest")

                if not is_baccarat_table(table_name):
                    continue

                if road_len == 0 or latest is None:
                    continue

                key = str(table_id)

                if key not in last_state:
                    last_state[key] = {
                        "roadLen": road_len,
                        "playId": play_id
                    }
                    continue

                old = last_state[key]
                old_len = old["roadLen"]
                old_play_id = old["playId"]

                # 洗牌 / 新鞋
                if road_len < old_len or play_id < old_play_id:
                    print("========== 新鞋 ==========")
                    print(table_name, "old:", old_len, "new:", road_len)

                    last_state[key] = {
                        "roadLen": road_len,
                        "playId": play_id
                    }
                    continue

                # 新結果
                if road_len > old_len:
                    code, side = result_to_side(result)

                    print("================")
                    print("桌:", table_name)
                    print("局:", play_id)
                    print(code, " - result:", result)
                    print("判斷:", side)

                    save_result(table, side)

                    last_state[key] = {
                        "roadLen": road_len,
                        "playId": play_id
                    }

            time.sleep(1)

        except Exception as e:
            print("錯誤:", e)
            time.sleep(2)

            try:
                switch_to_laya_frame()
                wait_laya_ready()
            except Exception:
                pass


main()