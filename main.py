import json

from collector.browser import DGBrowser
from config import URL, ACCOUNT, PASSWORD, CHROME_PROFILE


def main():
    browser = DGBrowser(
        url=URL,
        account=ACCOUNT,
        password=PASSWORD,
        chrome_profile=CHROME_PROFILE,
    )

    try:
        # 登入網站並進入 DG
        browser.login_and_open_dg()

        # 切換到包含 Laya 的 iframe
        browser.switch_to_laya_frame()

        # 等待桌台資料載入
        if not browser.wait_laya_ready():
            raise RuntimeError("DG 桌台資料載入逾時")

        # 取得所有桌台
        tables = browser.get_tables()

        print(f"取得桌台數量：{len(tables)}")

        print(
            json.dumps(
                tables,
                ensure_ascii=False,
                indent=2,
            )
        )

        input("按 Enter 關閉瀏覽器...")

    except Exception as error:
        print("程式發生錯誤：", error)
        input("按 Enter 關閉瀏覽器...")

    finally:
        browser.quit()


if __name__ == "__main__":
    main()