from config import (
    URL,
    ACCOUNT,
    PASSWORD,
    CHROME_PROFILE,
    DB_FILE,
    EXCLUDE_TABLES,
    POLL_INTERVAL,
)

from collector.browser import DGBrowser
from collector.collector import DGCollector
from database.database import Database


def main():
    browser = DGBrowser(
        url=URL,
        account=ACCOUNT,
        password=PASSWORD,
        chrome_profile=CHROME_PROFILE,
    )

    db = Database(DB_FILE)

    collector = DGCollector(
        browser=browser,
        database=db,
        exclude_tables=EXCLUDE_TABLES,
        poll_interval=POLL_INTERVAL,
    )

    try:
        collector.start()

    finally:
        db.close()
        browser.quit()


if __name__ == "__main__":
    main()