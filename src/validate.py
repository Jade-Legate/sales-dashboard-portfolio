"""적재 후 정합성 검증: 원본(raw_sales)과 정제 결과(sales)를 대조한다."""
import sqlite3
import sys

from etl import DB_PATH

CHECKS = {
    "행 수 일치 (raw = sales)":
        "SELECT (SELECT COUNT(*) FROM raw_sales) = (SELECT COUNT(*) FROM sales)",
    "매출 합계 일치 (raw = sales)":
        "SELECT (SELECT SUM(CAST(total AS INTEGER)) FROM raw_sales) = (SELECT SUM(sales_amount) FROM sales)",
    "수량 x 단가 = 매출 (불일치 0건)":
        "SELECT COUNT(*) = 0 FROM sales WHERE quantity * unit_price <> sales_amount",
    "필수값 NULL 0건":
        "SELECT COUNT(*) = 0 FROM sales WHERE sale_date IS NULL OR product_family IS NULL",
    "날짜 범위 정상 (2022-08 ~ 2023-11)":
        "SELECT MIN(sale_date) >= '2022-08-01' AND MAX(sale_date) <= '2023-11-30' FROM sales",
    "sale_id 중복 없음":
        "SELECT COUNT(*) = COUNT(DISTINCT sale_id) FROM sales",
}


def main() -> int:
    failed = 0
    with sqlite3.connect(DB_PATH) as con:
        for label, sql in CHECKS.items():
            ok = bool(con.execute(sql).fetchone()[0])
            failed += not ok
            print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        other, dup = con.execute(
            "SELECT SUM(product_family='Other'), SUM(is_dup_candidate) FROM sales").fetchone()
        print(f"[INFO] 미분류(Other) {other}건 / 중복 후보 {dup}건 (삭제하지 않고 표시)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
