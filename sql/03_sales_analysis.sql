-- 대시보드가 사용하는 분석 쿼리 모음. `-- name:` 줄이 쿼리 이름이다 (src/db.py가 로드).
-- 공통 파라미터: :start, :end (YYYY-MM-DD), :include_dup (1=중복 후보 포함, 0=제외), :growth (목표 성장률, 예 0.05)

-- name: kpi
SELECT COALESCE(SUM(sales_amount), 0) AS total_sales,
       COALESCE(SUM(quantity), 0)     AS total_qty,
       COUNT(*)                       AS orders,
       COALESCE(SUM(sales_amount) * 1.0 / NULLIF(COUNT(*), 0), 0) AS avg_order_value
FROM v_sales_enriched
WHERE sale_date BETWEEN :start AND :end
  AND (:include_dup = 1 OR is_dup_candidate = 0);

-- name: monthly_trend
-- 월별 매출과 전월 대비 증감률 (윈도우 함수 LAG)
WITH monthly AS (
    SELECT sale_month, SUM(sales_amount) AS sales
    FROM v_sales_enriched
    WHERE sale_date BETWEEN :start AND :end
      AND (:include_dup = 1 OR is_dup_candidate = 0)
    GROUP BY sale_month
)
SELECT sale_month, sales,
       LAG(sales) OVER (ORDER BY sale_month) AS prev_sales,
       ROUND((sales - LAG(sales) OVER (ORDER BY sale_month)) * 100.0
             / NULLIF(LAG(sales) OVER (ORDER BY sale_month), 0), 1) AS mom_pct
FROM monthly
ORDER BY sale_month;

-- name: family_summary
-- 제품군별 매출·수량·점유율 (점유율은 전체 합계 윈도우로 계산)
SELECT business_unit, product_family,
       SUM(sales_amount) AS sales,
       SUM(quantity)     AS qty,
       COUNT(*)          AS orders,
       ROUND(SUM(sales_amount) * 100.0 / SUM(SUM(sales_amount)) OVER (), 1) AS share_pct
FROM v_sales_enriched
WHERE sale_date BETWEEN :start AND :end
  AND (:include_dup = 1 OR is_dup_candidate = 0)
GROUP BY business_unit, product_family
ORDER BY sales DESC;

-- name: target_vs_actual
-- 사업부 x 월 계획 대비 실적. 목표 = 기준선(직전 3개월 평균) x (1 + 성장률)
WITH act AS (
    SELECT sale_month, business_unit, SUM(sales_amount) AS actual
    FROM v_sales_enriched
    WHERE sale_date BETWEEN :start AND :end
      AND (:include_dup = 1 OR is_dup_candidate = 0)
    GROUP BY sale_month, business_unit
),
tgt AS (
    SELECT t.target_month AS sale_month, d.business_unit,
           SUM(t.baseline_avg) * (1 + :growth) AS target
    FROM sales_target t
    JOIN dim_product_family d USING (product_family)
    WHERE t.baseline_months = 3           -- 직전 3개월이 모두 있는 달만 (초기 달의 불안정한 기준선 제외)
      AND d.business_unit <> 'Other'      -- 회사명 등 판별 불가 값은 목표 대상에서 제외
      AND t.target_month BETWEEN substr(:start, 1, 7) AND substr(:end, 1, 7)
    GROUP BY t.target_month, d.business_unit
)
SELECT tgt.sale_month, tgt.business_unit,
       COALESCE(act.actual, 0) AS actual,
       ROUND(tgt.target)       AS target,
       ROUND(COALESCE(act.actual, 0) * 100.0 / NULLIF(tgt.target, 0), 1) AS achievement_pct
FROM tgt
LEFT JOIN act USING (sale_month, business_unit)
ORDER BY tgt.sale_month, tgt.business_unit;

-- name: top_products
-- 원본 제품명 기준 상위 품목 (표준화 전 세부 규격 확인용)
SELECT product_raw, product_family, SUM(sales_amount) AS sales, SUM(quantity) AS qty
FROM v_sales_enriched
WHERE sale_date BETWEEN :start AND :end
  AND (:include_dup = 1 OR is_dup_candidate = 0)
GROUP BY product_raw, product_family
ORDER BY sales DESC
LIMIT 10;
