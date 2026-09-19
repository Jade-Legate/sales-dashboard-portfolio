-- Layer 1: raw_sales  = 원본 그대로 (감사·재처리용, 수정 금지)
-- Layer 2: sales     = 정제·표준화 결과 (분석/대시보드는 여기만 조회)
-- 이유: 정제 로직이 틀렸을 때 원본에서 다시 만들 수 있어야 한다.

DROP TABLE IF EXISTS raw_sales;
CREATE TABLE raw_sales (
    tanggal       TEXT,      -- DD/MM/YYYY 문자열 그대로
    jenis_produk  TEXT,
    jumlah_order  TEXT,
    harga         TEXT,
    total         TEXT
);

DROP TABLE IF EXISTS sales;
CREATE TABLE sales (
    sale_id         INTEGER PRIMARY KEY,   -- 원본 행 순서 (원본에 주문번호가 없어 부여)
    sale_date       TEXT NOT NULL,         -- ISO 8601 (YYYY-MM-DD)
    product_raw     TEXT NOT NULL,         -- 원본 제품명 (추적용)
    product_family  TEXT NOT NULL,         -- 표준화된 제품군
    spec_gsm        INTEGER,               -- 제품명에서 추출한 평량(g/m2), 없으면 NULL
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    unit_price      INTEGER NOT NULL CHECK (unit_price > 0),
    sales_amount    INTEGER NOT NULL CHECK (sales_amount > 0),  -- IDR
    is_dup_candidate INTEGER NOT NULL DEFAULT 0   -- 동일 행 2회째 이후 = 1 (삭제하지 않고 표시)
);

-- 대시보드의 주 조회 패턴(기간 필터, 제품군 집계)에 맞춘 인덱스
CREATE INDEX idx_sales_date    ON sales(sale_date);
CREATE INDEX idx_sales_family  ON sales(product_family, sale_date);
