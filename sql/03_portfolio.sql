-- Portfolio loss ratio is the premium-weighted average of the product ratios.
-- Unexplained is zero when the product rows add back to the claim table.
WITH product AS (
  SELECT
    SUM(earned_premium_eur) AS earned_premium_eur,
    SUM(paid_eur) AS paid_eur,
    SUM(policies) AS policies,
    SUM(claim_count) AS claim_count,
    SUM(loss_ratio_bps * earned_premium_eur) AS weighted_bps_num
  FROM v_product_scorecard
),
claims AS (
  SELECT COALESCE(SUM(paid_eur), 0) AS paid_eur, COUNT(*) AS claim_count
  FROM fact_claim
)
SELECT
  product.policies,
  product.earned_premium_eur,
  product.paid_eur,
  product.claim_count,
  product.paid_eur * 10000 / product.earned_premium_eur AS loss_ratio_bps,
  product.weighted_bps_num / product.earned_premium_eur AS weighted_loss_ratio_bps,
  product.paid_eur - claims.paid_eur AS unexplained_eur,
  product.claim_count - claims.claim_count AS claim_count_tie,
  product.paid_eur * 10000 / product.earned_premium_eur
    - product.weighted_bps_num / product.earned_premium_eur AS weight_tie
FROM product, claims;
