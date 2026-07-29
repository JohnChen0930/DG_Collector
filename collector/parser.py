RESULT_MAP = {
    "1": "莊",
    "2": "莊",
    "3": "莊",
    "5": "閒",
    "6": "閒",
    "7": "閒",
    "9": "和",
    "11": "和",
}


def is_baccarat_table(table_name, exclude_tables=None):
    exclude_tables = exclude_tables or []

    if not table_name:
        return False

    if table_name in exclude_tables:
        return False

    return table_name.startswith("RB") or table_name.startswith("S")


def parse_result_code(result):
    if not result:
        return ""

    return str(result).split(",")[0]


def result_to_side(result):
    code = parse_result_code(result)
    return RESULT_MAP.get(code, f"UNKNOWN({code})")