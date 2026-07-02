import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


class DGBrowser:
    def __init__(self, url, account, password, chrome_profile):
        self.url = url
        self.account = account
        self.password = password

        chrome_options = Options()
        chrome_options.add_argument(f"--user-data-dir={chrome_profile}")
        chrome_options.add_argument("--start-maximized")

        self.driver = webdriver.Chrome(options=chrome_options)

    def click_by_xpath(self, xpath, wait=1):
        el = self.driver.find_element(By.XPATH, xpath)
        self.driver.execute_script("arguments[0].click();", el)
        time.sleep(wait)
        return el

    def login_and_open_dg(self):
        self.driver.get(self.url)
        time.sleep(2)

        self.click_by_xpath("//img[contains(@src,'FaviconUpcasino_dg')]", 1)

        account_input = self.driver.find_element(
            By.XPATH,
            "//input[@placeholder='請填寫8-20位的字母或數字']"
        )
        account_input.clear()
        account_input.send_keys(self.account)

        pw_input = self.driver.find_element(
            By.XPATH,
            "//input[contains(@class,'password-input')]"
        )
        pw_input.clear()
        pw_input.send_keys(self.password)

        self.click_by_xpath("//button[contains(@class,'base-btn')]", 1)

        try:
            self.click_by_xpath("//p[text()='確定']", 2)
        except Exception:
            pass

        self.click_by_xpath("//img[contains(@src,'FaviconUpcasino_dg')]", 10)

    def switch_to_laya_frame(self):
        self.driver.switch_to.default_content()

        frames = self.driver.find_elements(By.TAG_NAME, "iframe")
        print("iframe 數量:", len(frames))

        for i, frame in enumerate(frames):
            self.driver.switch_to.default_content()
            self.driver.switch_to.frame(frame)

            has_laya = self.driver.execute_script("return typeof Laya !== 'undefined';")
            print("iframe", i, "has Laya:", has_laya)

            if has_laya:
                print("找到 Laya iframe:", i)
                return True

        self.driver.switch_to.default_content()
        return False

    def wait_laya_ready(self, timeout=60):
        start = time.time()

        while time.time() - start < timeout:
            try:
                status = self.driver.execute_script("""
                    return {
                        hasLaya: typeof Laya !== 'undefined',
                        hasStage: typeof Laya !== 'undefined' && !!Laya.stage,
                        childCount: typeof Laya !== 'undefined' && Laya.stage ? Laya.stage.numChildren : -1,
                        hasRoot: typeof Laya !== 'undefined' && Laya.stage && Laya.stage.numChildren > 0 && !!Laya.stage.getChildAt(0),
                        hasGameDataMan: typeof Laya !== 'undefined' && Laya.stage && Laya.stage.numChildren > 0 && !!Laya.stage.getChildAt(0).gameDataMan,
                        hasDataInfo: typeof Laya !== 'undefined' && Laya.stage && Laya.stage.numChildren > 0 && Laya.stage.getChildAt(0).gameDataMan ? !!Laya.stage.getChildAt(0).gameDataMan.dataInfo : false,
                        dataLen: typeof Laya !== 'undefined' && Laya.stage && Laya.stage.numChildren > 0 && Laya.stage.getChildAt(0).gameDataMan && Laya.stage.getChildAt(0).gameDataMan.dataInfo ? Laya.stage.getChildAt(0).gameDataMan.dataInfo.length : 0
                    };
                """)

                print("Laya狀態:", status)

                if status.get("hasLaya") and status.get("hasStage") and status.get("childCount", 0) > 0:
                    root_ready = self.driver.execute_script("""
                        const root = Laya.stage.getChildAt(0);
                        return !!root && !!root.gameDataMan && !!root.gameDataMan.dataInfo;
                    """)

                    if root_ready:
                        print("Laya 資料已就緒")
                        return True

            except Exception as e:
                print("等待 Laya 錯誤:", e)

            time.sleep(2)

        return False

    def get_tables(self):
        js = """
        const data = Laya.stage.getChildAt(0).gameDataMan.dataInfo;

        return JSON.parse(JSON.stringify(data.map(t => ({
            tableId: t.tableId,
            tableName: t.tableName || "",
            gameName: t.gameName || "",
            gameNo: t.gameNo || "",
            playId: t.playId || 0,
            result: t.result || "",
            poker: t.poker || "",
            winPoint: t.winPoint || 0,
            stateId: t.stateId || 0,
            countDown: t.countDown || 0,
            roadLen: t.roadArray ? t.roadArray.length : 0,
            latest: (t.roadArray && t.roadArray.length > 0)
                ? t.roadArray[t.roadArray.length - 1]
                : null,
            dealerName: t.dealerInfo && t.dealerInfo.name ? t.dealerInfo.name : "",
            onlineCount: t.onlineCount || 0,
            totalAmount: t.totalAmount || 0
        }))));
        """
        return self.driver.execute_script(js)

    def quit(self):
        self.driver.quit()