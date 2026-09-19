"""Extract -> Transform -> Load: Kaggle 판매 CSV -> SQLite (raw_sales, sales)."""
import re
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT / "data" / "raw" / "data_penjualan.csv"
DB_PATH = ROOT / "data" / "sales.db"
SCHEMA = ROOT / "sql" / "01_create_tables.sql"
DIM_TARGETS = ROOT / "sql" / "02_dimensions_targets.sql"

# 제품군 규칙: 위에서부터 먼저 맞는 것을 채택 (순서가 곧 우선순위)
# 'CraftFoodpak290'처럼 두 키워드가 겹치면 소재(Craft)를 우선한다.
FAMILY_RULES = [
    ("Craft",      r"craf"),
    ("Duplex",     r"duple[kx]"),           # Dupleks / Duplex / DUPLEKS
    ("Ivory",      r"ivory"),
    ("GreaseProof", r"grea?s+e?p?ro?o?f"),   # Greaseproof / Greseproof / GRESSPROFF
    ("Foodpak",    r"foodpak"),
    ("Kinstruk",   r"kinstruk"),
    ("HVS",        r"hvs"),
    ("Sticker",    r"stiker|sticker"),
    ("Unbleached", r"unbleach"),
    ("NCR",        r"^ncr$"),
    ("Cup&Bowl",   r"cup|bowl"),
]


def to_family(name: str) -> str:
    key = re.sub(r"[^a-z0-9]", "", name.lower())
    for family, pattern in FAMILY_RULES:
        if re.search(pattern, key):
            return family
    return "Other"  # 회사명·판별 불가 값. 버리지 않고 별도 분류


def extract_gsm(name: str):
    m = re.search(r"(\d{3})", name)
    return int(m.group(1)) if m else None


def extract() -> pd.DataFrame:
    # 구분자가 세미콜론이고, 전부 문자열로 읽어 원본을 손상 없이 보존
    return pd.read_csv(RAW_CSV, sep=";", dtype=str)


def transform(raw: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame({
        "product_raw": raw["Jenis Produk"].str.strip(),
        "quantity": pd.to_numeric(raw["Jumlah Order"]).astype(int),
        "unit_price": pd.to_numeric(raw["Harga"]).astype(int),
        "sales_amount": pd.to_numeric(raw["Total"]).astype(int),
    })
    # 형식을 명시해야 05/08이 5월 8일로 잘못 해석되지 않는다 (DD/MM/YYYY)
    dates = pd.to_datetime(raw["Tanggal"], format="%d/%m/%Y")
    df.insert(0, "sale_date", dates.dt.strftime("%Y-%m-%d"))
    df.insert(0, "sale_id", range(1, len(df) + 1))
    df["product_family"] = df["product_raw"].map(to_family)
    df["spec_gsm"] = df["product_raw"].map(extract_gsm).astype("Int64")
    # 주문번호가 없어 진짜 중복인지 알 수 없다 -> 삭제 대신 표시
    key = ["sale_date", "product_raw", "quantity", "unit_price"]
    df["is_dup_candidate"] = df.duplicated(subset=key, keep="first").astype(int)
    return df[["sale_id", "sale_date", "product_raw", "product_family", "spec_gsm",
               "quantity", "unit_price", "sales_amount", "is_dup_candidate"]]


def load(raw: pd.DataFrame, clean: pd.DataFrame) -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.executescript(SCHEMA.read_text(encoding="utf-8"))
        raw.columns = ["tanggal", "jenis_produk", "jumlah_order", "harga", "total"]
        raw.to_sql("raw_sales", con, if_exists="append", index=False)
        clean.to_sql("sales", con, if_exists="append", index=False)
        con.executescript(DIM_TARGETS.read_text(encoding="utf-8"))  # 차원 테이블·뷰·목표 기준선


if __name__ == "__main__":
    raw = extract()
    clean = transform(raw)
    load(raw, clean)
    print(f"loaded raw={len(raw)} clean={len(clean)} -> {DB_PATH}")
    print(clean["product_family"].value_counts().to_string())
