from collector.browser import DGBrowser
from collector.collector import DGCollector
from database.database import Database
from config import URL, ACCOUNT, PASSWORD, CHROME_PROFILE


def main():
    browser = DGBrowser(
        url=URL,
        account=ACCOUNT,
        password=PASSWORD,
        chrome_profile=CHROME_PROFILE,
    )

    database = Database("data/history.db")

    collector = DGCollector(
        browser=browser,
        database=database,
        exclude_tables=["S08"],
        poll_interval=1,
    )

    try:
        collector.start()

    finally:
        database.close()


if __name__ == "__main__":
    main()