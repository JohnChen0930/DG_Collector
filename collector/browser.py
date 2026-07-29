import json
import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException


class DGBrowser:
    def __init__(
        self,
        url: str,
        account: str,
        password: str,
        chrome_profile: str | None = None,
    ) -> None:
        self.url = url
        self.account = account
        self.password = password
        self.chrome_profile = chrome_profile

        self.driver: webdriver.Chrome | None = None
        self.wait: WebDriverWait | None = None

    def start(self) -> None:
        """啟動 Chrome。"""
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")

        if self.chrome_profile:
            options.add_argument(
                f"--user-data-dir={self.chrome_profile}"
            )

        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 20)

        print("[Browser] Chrome 啟動成功")

    def open_homepage(self) -> None:
        """開啟網站首頁。"""
        if self.driver is None:
            raise RuntimeError("瀏覽器尚未啟動")

        self.driver.get(self.url)
        print("[Browser] 首頁已開啟")

    def click_dg_button(self) -> None:
        """點擊 DG 遊戲入口。"""
        if self.driver is None or self.wait is None:
            raise RuntimeError("瀏覽器尚未啟動")

        dg_button = self.wait.until(
            EC.visibility_of_element_located(
                (
                    By.XPATH,
                    "//img[contains(@src,'FaviconUpcasino_dg')]",
                )
            )
        )

        time.sleep(2)

        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            dg_button,
        )

        time.sleep(1)

        self.driver.execute_script(
            "arguments[0].click();",
            dg_button,
        )

        print("[Browser] 已點擊 DG 按鈕")

    def login(self) -> None:
        """輸入帳號密碼並登入。"""
        if self.driver is None or self.wait is None:
            raise RuntimeError("瀏覽器尚未啟動")

        account_input = self.wait.until(
            EC.visibility_of_element_located(
                (
                    By.XPATH,
                    "//input[@placeholder='請填寫8-20位的字母或數字']",
                )
            )
        )

        password_input = self.wait.until(
            EC.visibility_of_element_located(
                (
                    By.XPATH,
                    "//input[contains(@class,'password-input')]",
                )
            )
        )

        login_button = self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//button[contains(@class,'base-btn') and contains(@class,'type1')]",
                )
            )
        )

        account_input.clear()
        account_input.send_keys(self.account)
        print("[Browser] 已輸入帳號")

        password_input.clear()
        password_input.send_keys(self.password)
        print("[Browser] 已輸入密碼")

        self.driver.execute_script(
            "arguments[0].click();",
            login_button,
        )

        print("[Browser] 已點擊登入")

    def confirm_login(self) -> None:
        """登入後點擊確定按鈕；沒有彈窗時直接略過。"""
        if self.driver is None:
            raise RuntimeError("瀏覽器尚未啟動")

        try:
            confirm_wait = WebDriverWait(self.driver, 8)

            confirm_button = confirm_wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//p[normalize-space()='確定']",
                    )
                )
            )

            self.driver.execute_script(
                "arguments[0].click();",
                confirm_button,
            )

            print("[Browser] 已點擊確定")

        except TimeoutException:
            print("[Browser] 沒有登入確認視窗，略過")

    def enter_dg(self) -> None:
        """完成登入並進入 DG。"""
        if self.driver is None or self.wait is None:
            raise RuntimeError("瀏覽器尚未啟動")

        self.click_dg_button()

        self.wait.until(
            EC.visibility_of_element_located(
                (
                    By.XPATH,
                    "//input[@placeholder='請填寫8-20位的字母或數字']",
                )
            )
        )

        print("[Browser] 登入視窗已開啟")

        self.login()
        self.confirm_login()

        # 等首頁登入狀態更新
        time.sleep(3)

        old_handles = set(self.driver.window_handles)

        self.click_dg_button()

        print("[Browser] 已再次點擊 DG，等待遊戲頁面")

        # 等待網站建立新分頁或載入 iframe
        time.sleep(8)

        handles = self.driver.window_handles
        new_handles = set(handles) - old_handles

        if new_handles:
            new_handle = next(iter(new_handles))
            self.driver.switch_to.window(new_handle)
            print("[Browser] 已切換到 DG 新視窗")
        else:
            print("[Browser] DG 沒有開新視窗，繼續使用目前視窗")

        print(f"[Browser] 目前視窗數量：{len(handles)}")
        print(f"[Browser] 目前網址：{self.driver.current_url}")

    def login_and_open_dg(self) -> None:
        """啟動瀏覽器、開啟首頁並進入 DG。"""
        self.start()
        self.open_homepage()
        self.enter_dg()

    def switch_to_laya_frame(self, timeout: int = 60) -> int:
        """在所有瀏覽器視窗中尋找包含 Laya 的頁面或 iframe。"""
        if self.driver is None:
            raise RuntimeError("瀏覽器尚未啟動")

        end_time = time.time() + timeout
        last_status_time = 0

        while time.time() < end_time:
            handles = self.driver.window_handles

            for window_index, handle in enumerate(handles):
                try:
                    self.driver.switch_to.window(handle)
                    self.driver.switch_to.default_content()

                    current_url = self.driver.current_url

                    # 先檢查最外層頁面是否已有 Laya
                    has_laya_main = self.driver.execute_script(
                        "return typeof Laya !== 'undefined';"
                    )

                    if has_laya_main:
                        print(
                            f"[Browser] 在主頁面找到 Laya，"
                            f"視窗={window_index}，網址={current_url}"
                        )
                        return -1

                    iframes = self.driver.find_elements(By.TAG_NAME, "iframe")

                    if time.time() - last_status_time >= 5:
                        print(
                            f"[Browser] 檢查視窗 {window_index}："
                            f"iframe={len(iframes)}，網址={current_url}"
                        )

                    for iframe_index in range(len(iframes)):
                        try:
                            self.driver.switch_to.default_content()

                            # DOM 可能更新，因此每次重新取得 iframe
                            current_iframes = self.driver.find_elements(
                                By.TAG_NAME,
                                "iframe",
                            )

                            if iframe_index >= len(current_iframes):
                                continue

                            self.driver.switch_to.frame(
                                current_iframes[iframe_index]
                            )

                            has_laya = self.driver.execute_script(
                                "return typeof Laya !== 'undefined';"
                            )

                            if has_laya:
                                frame_url = self.driver.execute_script(
                                    "return window.location.href;"
                                )

                                print(
                                    f"[Browser] 找到 Laya："
                                    f"視窗={window_index}，"
                                    f"iframe={iframe_index}，"
                                    f"網址={frame_url}"
                                )

                                return iframe_index

                        except Exception as error:
                            print(
                                f"[Browser] iframe {iframe_index} "
                                f"檢查失敗：{error}"
                            )

                    self.driver.switch_to.default_content()

                except Exception as error:
                    print(
                        f"[Browser] 視窗 {window_index} 檢查失敗：{error}"
                    )

            if time.time() - last_status_time >= 5:
                print("[Browser] 尚未找到 Laya，繼續等待...")
                last_status_time = time.time()

            time.sleep(1)

        # 最後印出所有視窗網址，方便判斷停在哪
        print("[Browser] 搜尋 Laya 逾時，現有視窗：")

        for index, handle in enumerate(self.driver.window_handles):
            try:
                self.driver.switch_to.window(handle)
                print(f"  視窗 {index}：{self.driver.current_url}")
            except Exception as error:
                print(f"  視窗 {index}：無法讀取，{error}")

        raise RuntimeError("找不到包含 Laya 的頁面或 iframe")

    def wait_laya_ready(self, timeout: int = 60) -> bool:
        """等待 Laya 和 gameDataMan.dataInfo 準備完成。"""
        if self.driver is None:
            raise RuntimeError("瀏覽器尚未啟動")

        end_time = time.time() + timeout

        while time.time() < end_time:
            try:
                ready = self.driver.execute_script(
                    """
                    try {
                        if (typeof Laya === 'undefined') {
                            return false;
                        }

                        const root = Laya.stage.getChildAt(0);

                        if (!root || !root.gameDataMan) {
                            return false;
                        }

                        return Array.isArray(
                            root.gameDataMan.dataInfo
                        );
                    } catch (error) {
                        return false;
                    }
                    """
                )

                if ready:
                    print("[Browser] Laya 資料已準備完成")
                    return True

            except Exception:
                pass

            time.sleep(1)

        return False

    def execute_js(self, file_name: str):
        """執行 js 目錄內的 JavaScript 檔案。"""
        if self.driver is None:
            raise RuntimeError("瀏覽器尚未啟動")

        project_root = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )

        js_path = os.path.join(
            project_root,
            "js",
            file_name,
        )

        if not os.path.exists(js_path):
            raise FileNotFoundError(
                f"找不到 JavaScript 檔案：{js_path}"
            )

        with open(js_path, "r", encoding="utf-8") as file:
            script = file.read()

        return self.driver.execute_script(script)

    def get_tables(self) -> list[dict]:
        """取得 DG 多桌資料。"""
        result = self.execute_js("get_tables.js")

        if result is None:
            raise RuntimeError("get_tables.js 沒有回傳資料")

        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError as error:
                raise RuntimeError(
                    f"get_tables.js 回傳格式錯誤：{error}"
                ) from error

        if not isinstance(result, list):
            raise RuntimeError(
                f"桌台資料格式不是 list：{type(result).__name__}"
            )

        return result

    def quit(self) -> None:
        """關閉瀏覽器。"""
        if self.driver is not None:
            self.driver.quit()
            self.driver = None
            self.wait = None

            print("[Browser] Chrome 已關閉")

    def close(self) -> None:
        """保留舊名稱相容性。"""
        self.quit()