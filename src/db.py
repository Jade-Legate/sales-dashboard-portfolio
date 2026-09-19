"""SQL 파일에서 이름 붙은 쿼리를 읽어 실행하는 헬퍼. SQL은 코드가 아니라 .sql 파일에 둔다."""
import re
import sqlite3

import pandas as pd

from etl import DB_PATH, ROOT

_QUERY_FILE = ROOT / "sql" / "03_sales_analysis.sql"


def load_queries() -> dict[str, str]:
    text = _QUERY_FILE.read_text(encoding="utf-8")
    parts = re.split(r"^-- name:\s*(\w+)\s*$", text, flags=re.M)
    return {name: sql.strip() for name, sql in zip(parts[1::2], parts[2::2])}


def run(name: str, **params) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql_query(load_queries()[name], con, params=params)
