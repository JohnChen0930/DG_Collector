RESULT_MAP = {
    "1": "B",
    "2": "B",
    "3": "B",
    "5": "P",
    "6": "P",
    "7": "P",
    "9": "T",
    "10": "T",
    "11": "T",
}


def parse_result_code(result):
    if not result:
        return ""
    return str(result).split(",")[0]


def result_to_side(result):
    code = parse_result_code(result)
    return RESULT_MAP.get(code, f"UNKNOWN_{code}")


def is_baccarat_table(table_name, exclude_tables=None):
    if not table_name:
        return False

    exclude_tables = exclude_tables or []

    if table_name in exclude_tables:
        return False

    return table_name.startswith("RB") or table_name.startswith("S")