from collector.browser import DGBrowser


def main() -> None:
    browser = DGBrowser()

    try:
        browser.start()
        browser.open_homepage()
        browser.enter_dg()

        input("確認 DG 大廳載入完成後，按 Enter 讀取資料...")

        result = browser.get_game_data()
        print(result)

        input("按 Enter 關閉瀏覽器...")

    except Exception as error:
        print(f"[Main] 執行失敗：{error}")
        raise

    finally:
        browser.close()


if __name__ == "__main__":
    main()