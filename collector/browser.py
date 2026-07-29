import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from pathlib import Path
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException



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

        wait = WebDriverWait(self.driver, 20)

        dg_xpath = "//img[contains(@src,'FaviconUpcasino_dg')]"
        account_xpath = "//input[@placeholder='請填寫8-20位的字母或數字']"
        password_xpath = "//input[contains(@class,'password-input')]"
        login_button_xpath = "//button[contains(@class,'base-btn')]"
        confirm_xpath = "//p[text()='確定']"

        # 先檢查是否已經直接進入 DG
        time.sleep(3)

        self.driver.switch_to.default_content()
        frames = self.driver.find_elements(By.TAG_NAME, "iframe")

        for frame in frames:
            try:
                self.driver.switch_to.default_content()
                self.driver.switch_to.frame(frame)

                has_laya = self.driver.execute_script(
                    "return typeof Laya !== 'undefined';"
                )

                if has_laya:
                    print("[Browser] 已經在 DG 頁面，不需要重新登入")
                    return

            except Exception:
                continue

        self.driver.switch_to.default_content()

        # 嘗試找 DG 圖示
        try:
            dg_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, dg_xpath))
            )
        except TimeoutException:
            print("[Browser] 找不到 DG 圖示")
            print("[Browser] 目前網址：", self.driver.current_url)
            print("[Browser] 頁面標題：", self.driver.title)

            raise RuntimeError(
                "首頁找不到 DG 圖示，可能是網站版面改變、尚未載入，"
                "或目前停留在其他頁面"
            )

        self.driver.execute_script("arguments[0].click();", dg_button)

        # 點 DG 後，判斷是否出現登入欄位
        try:
            account_input = WebDriverWait(self.driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, account_xpath))
            )

            print("[Browser] 偵測到登入畫面")

            account_input.clear()
            account_input.send_keys(self.account)

            password_input = wait.until(
                EC.visibility_of_element_located((By.XPATH, password_xpath))
            )
            password_input.clear()
            password_input.send_keys(self.password)

            login_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, login_button_xpath))
            )
            self.driver.execute_script(
                "arguments[0].click();",
                login_button,
            )

            # 登入後可能有確定提示
            try:
                confirm_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, confirm_xpath))
                )
                self.driver.execute_script(
                    "arguments[0].click();",
                    confirm_button,
                )
            except TimeoutException:
                pass

            print("[Browser] 登入完成")

            # 登入後再次點擊 DG
            self.driver.switch_to.default_content()

            dg_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, dg_xpath))
            )
            self.driver.execute_script("arguments[0].click();", dg_button)

        except TimeoutException:
            # 沒出現登入欄位，通常代表 Chrome Profile 已登入
            print("[Browser] 沒有登入畫面，推測目前已登入")

        # 等待 DG iframe 出現
        WebDriverWait(self.driver, 30).until(
            lambda driver: len(
                driver.find_elements(By.TAG_NAME, "iframe")
            ) > 0
        )

        print("[Browser] DG 頁面已開啟")

    def switch_to_laya_frame(self) -> int:
        """切換到包含 Laya 的 DG iframe，回傳 iframe 索引。"""
        if self.driver is None:
            raise RuntimeError("瀏覽器尚未啟動")

        self.driver.switch_to.default_content()

        frames = self.driver.find_elements(By.TAG_NAME, "iframe")

        for index in range(len(frames)):
            try:
                self.driver.switch_to.default_content()

                # 每次重新取得，避免 iframe 物件失效
                current_frames = self.driver.find_elements(By.TAG_NAME, "iframe")
                self.driver.switch_to.frame(current_frames[index])

                has_laya = self.driver.execute_script(
                    "return typeof Laya !== 'undefined';"
                )

                if has_laya:
                    print(f"[Browser] 找到 Laya iframe：{index}")
                    return index

            except Exception as error:
                print(f"[Browser] iframe {index} 檢查失敗：{error}")

        self.driver.switch_to.default_content()
        raise RuntimeError("找不到包含 Laya 的 iframe")

    def wait_laya_ready(self, timeout: int = 30) -> bool:
        """等待 DG 的桌台資料載入完成。"""
        if self.driver is None:
            raise RuntimeError("瀏覽器尚未啟動")

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                ready = self.driver.execute_script(
                    """
                    return typeof Laya !== 'undefined'
                        && Laya.stage
                        && Laya.stage.numChildren > 0
                        && Laya.stage.getChildAt(0)
                        && Laya.stage.getChildAt(0).gameDataMan
                        && Laya.stage.getChildAt(0).gameDataMan.dataInfo
                        && Laya.stage.getChildAt(0).gameDataMan.dataInfo.length > 0;
                    """
                )

                if ready:
                    print("[Browser] DG 桌台資料已載入")
                    return True

            except Exception:
                pass

            time.sleep(1)

        return False

    def execute_js(self, file_name: str):
        """執行 js 資料夾內的 JavaScript 檔案。"""
        if self.driver is None:
            raise RuntimeError("瀏覽器尚未啟動")

        project_root = Path(__file__).resolve().parent.parent
        script_path = project_root / "js" / file_name

        if not script_path.exists():
            raise FileNotFoundError(f"找不到 JavaScript 檔案：{script_path}")

        script = script_path.read_text(encoding="utf-8")

        return self.driver.execute_script(script)


    def get_tables(self) -> list[dict]:
        """取得 DG 所有桌台資料。"""
        return self.execute_js("get_tables.js")

    def quit(self):
        self.driver.quit()