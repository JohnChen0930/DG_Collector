from database import Database


def main() -> None:
    print("DG Collector 啟動中...")

    database = Database("data/history.db")

    try:
        database.initialize()
        print("資料庫初始化成功")
        print(f"資料庫位置：{database.db_path.resolve()}")

    except Exception as error:
        print(f"資料庫初始化失敗：{error}")
        raise

    finally:
        database.close()


if __name__ == "__main__":
    main()