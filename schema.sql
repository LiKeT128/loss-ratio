PRAGMA foreign_keys = ON;

-- One month of a fictional insurer.
-- Grain: one exposure row per product, one claim row per claim.
-- That is the model a Power BI dataset would sit on.

CREATE TABLE dim_product (
  product_id INTEGER PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE fact_exposure (
  product_id INTEGER PRIMARY KEY REFERENCES dim_product(product_id),
  policies INTEGER NOT NULL,
  earned_premium_eur INTEGER NOT NULL
);

CREATE TABLE fact_claim (
  claim_id INTEGER PRIMARY KEY,
  product_id INTEGER NOT NULL REFERENCES dim_product(product_id),
  paid_eur INTEGER NOT NULL
);

-- The large-claim cut is an assumption, not a number hidden in the query.
CREATE TABLE assumption (
  name TEXT PRIMARY KEY,
  value_eur INTEGER NOT NULL
);

CREATE VIEW v_claim AS
SELECT
  c.claim_id,
  c.product_id,
  c.paid_eur,
  CASE
    WHEN c.paid_eur >= (SELECT value_eur FROM assumption WHERE name = 'large_claim_eur')
    THEN 1 ELSE 0
  END AS is_large
FROM fact_claim c;

CREATE VIEW v_product_scorecard AS
SELECT
  p.product_id,
  p.name,
  e.policies,
  e.earned_premium_eur,
  COUNT(c.claim_id) AS claim_count,
  COALESCE(SUM(c.paid_eur), 0) AS paid_eur,
  COALESCE(SUM(c.is_large), 0) AS large_count,
  COALESCE(SUM(CASE WHEN c.is_large = 1 THEN c.paid_eur ELSE 0 END), 0) AS large_paid_eur,
  COUNT(c.claim_id) * 10000 / e.policies AS frequency_bps,
  COALESCE(SUM(c.paid_eur), 0) / COUNT(c.claim_id) AS severity_eur,
  COALESCE(SUM(c.paid_eur), 0) * 10000 / e.earned_premium_eur AS loss_ratio_bps,
  (
    COALESCE(SUM(c.paid_eur), 0)
    - COALESCE(SUM(CASE WHEN c.is_large = 1 THEN c.paid_eur ELSE 0 END), 0)
  ) * 10000 / e.earned_premium_eur AS loss_ratio_ex_large_bps
FROM dim_product p
JOIN fact_exposure e ON e.product_id = p.product_id
LEFT JOIN v_claim c ON c.product_id = p.product_id
GROUP BY p.product_id, p.name, e.policies, e.earned_premium_eur;
