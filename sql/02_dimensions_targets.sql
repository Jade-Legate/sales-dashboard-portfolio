-- 제품군 -> 사업부 매핑 (차원 테이블)
-- 주의: 원본에 사업부 정보가 없어 제품 성격 기준으로 직접 분류한 가정이다. README에 명시.
DROP TABLE IF EXISTS dim_product_family;
CREATE TABLE dim_product_family (
    product_family TEXT PRIMARY KEY,
    business_unit  TEXT NOT NULL
);
INSERT INTO dim_product_family VALUES
    ('Duplex',      'Paperboard'),
    ('Ivory',       'Paperboard'),
    ('Craft',       'Packaging'),
    ('Foodpak',     'Packaging'),
    ('GreaseProof', 'Packaging'),
    ('Cup&Bowl',    'Packaging'),
    ('Unbleached',  'Packaging'),
    ('Kinstruk',    'Printing & Office'),
    ('HVS',         'Printing & Office'),
    ('NCR',         'Printing & Office'),
    ('Sticker',     'Printing & Office'),
    ('Other',       'Other');

-- 분석용 뷰: 정제 테이블 + 사업부 + 월
DROP VIEW IF EXISTS v_sales_enriched;
CREATE VIEW v_sales_enriched AS
SELECT s.*, substr(s.sale_date, 1, 7) AS sale_month, d.business_unit
FROM sales s
JOIN dim_product_family d USING (product_family);

-- 목표 기준선: "해당 월 직전 3개월 평균 매출" (제품군 x 월)
-- 목표 = baseline_avg x (1 + 성장률). 성장률은 조회 시점에 파라미터로 받는다.
-- 실적이 없는 달은 0으로 채워(달력 격자) 평균이 실제 판매 공백을 반영하게 한다.
DROP TABLE IF EXISTS sales_target;
CREATE TABLE sales_target AS
WITH months AS (SELECT DISTINCT sale_month AS target_month FROM v_sales_enriched),
     grid AS (
         SELECT m.target_month, f.product_family
         FROM months m CROSS JOIN dim_product_family f
     ),
     monthly AS (
         SELECT g.target_month, g.product_family,
                COALESCE(SUM(v.sales_amount), 0) AS actual_amount
         FROM grid g
         LEFT JOIN v_sales_enriched v
                ON v.sale_month = g.target_month AND v.product_family = g.product_family
         GROUP BY g.target_month, g.product_family
     )
SELECT target_month, product_family,
       AVG(actual_amount) OVER w AS baseline_avg,   -- 직전 최대 3개월, 첫 달은 NULL
       COUNT(actual_amount) OVER w AS baseline_months
FROM monthly
WINDOW w AS (PARTITION BY product_family ORDER BY target_month
             ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING);
