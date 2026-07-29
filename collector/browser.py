from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config import DG_PASSWORD, DG_URL, DG_USERNAME
import time


class DGBrowser:
    def __init__(self) -> None:
        self.driver: webdriver.Chrome | None = None
        self.wait: WebDriverWait | None = None

    def start(self) -> None:
        """啟動 Chrome。"""
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")

        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 20)

        print("[Browser] Chrome 啟動成功")

    def open_homepage(self) -> None:
        """開啟網站首頁。"""
        if self.driver is None:
            raise RuntimeError("瀏覽器尚未啟動")

        self.driver.get(DG_URL)
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

        # 網站圖片出現後，內部事件可能還沒綁定完成
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
        account_input.send_keys(DG_USERNAME)
        print("[Browser] 已輸入帳號")

        password_input.clear()
        password_input.send_keys(DG_PASSWORD)
        print("[Browser] 已輸入密碼")

        self.driver.execute_script(
            "arguments[0].click();",
            login_button,
        )

        print("[Browser] 已點擊登入")

    def confirm_login(self) -> None:
        """登入後點擊確定按鈕。"""
        if self.driver is None or self.wait is None:
            raise RuntimeError("瀏覽器尚未啟動")

        confirm_button = self.wait.until(
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

    def enter_dg(self) -> None:
        """完成登入並進入 DG。"""
        self.click_dg_button()

        if self.wait is None:
            raise RuntimeError("瀏覽器尚未啟動")

        # 確認登入視窗真的已開啟
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

        # 登入完成後讓首頁狀態更新
        time.sleep(2)

        self.click_dg_button()

        print("[Browser] 已進入 DG")



    def get_game_data(self):
        """尋找包含 Laya 的 iframe，並讀取 gameDataMan。"""
        if self.driver is None:
            raise RuntimeError("瀏覽器尚未啟動")

        driver = self.driver

        # 先回到最外層頁面
        driver.switch_to.default_content()

        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        print(f"[Browser] 找到 iframe 數量：{len(iframes)}")

        # 先測試主頁面
        main_result = driver.execute_script(
            """
            return {
                hasLaya: typeof Laya !== 'undefined',
                url: window.location.href
            };
            """
        )

        print(f"[Browser] 主頁面：{main_result}")

        # 逐個 iframe 測試
        for index, iframe in enumerate(iframes):
            try:
                driver.switch_to.default_content()

                # iframe 清單可能因頁面變動而失效，所以重新取得
                current_iframes = driver.find_elements(By.TAG_NAME, "iframe")

                if index >= len(current_iframes):
                    continue

                driver.switch_to.frame(current_iframes[index])

                result = driver.execute_script(
                    """
                    return {
                        hasLaya: typeof Laya !== 'undefined',
                        url: window.location.href,
                        title: document.title
                    };
                    """
                )

                print(f"[Browser] iframe {index}：{result}")

                if result.get("hasLaya"):
                    game_data_result = driver.execute_script(
                        """
                        try {
                            const root = Laya.stage.getChildAt(0);

                            if (!root) {
                                return {
                                    ok: false,
                                    error: 'Laya root not found'
                                };
                            }

                            if (!root.gameDataMan) {
                                return {
                                    ok: false,
                                    error: 'gameDataMan not found',
                                    rootKeys: Object.keys(root)
                                };
                            }

                            return {
                                ok: true,
                                iframeIndex: arguments[0],
                                keys: Object.keys(root.gameDataMan)
                            };
                        } catch (error) {
                            return {
                                ok: false,
                                error: error.toString()
                            };
                        }
                        """,
                        index,
                    )

                    print(f"[Browser] 找到 Laya，iframe={index}")
                    return game_data_result

            except Exception as error:
                print(f"[Browser] iframe {index} 檢查失敗：{error}")

        driver.switch_to.default_content()

        return {
            "ok": False,
            "error": "所有 iframe 都找不到 Laya",
            "iframe_count": len(iframes),
        }

    def close(self) -> None:
        """關閉瀏覽器。"""
        if self.driver is not None:
            self.driver.quit()
            self.driver = None
            self.wait = None

            print("[Browser] Chrome 已關閉")