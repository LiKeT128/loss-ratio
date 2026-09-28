-- Frequency, severity, and loss ratio by product.
-- Ties must be zero: severity times claim count equals paid,
-- frequency times policies equals claim count,
-- loss ratio times premium equals paid.
SELECT
  product_id,
  name,
  policies,
  earned_premium_eur,
  claim_count,
  paid_eur,
  large_count,
  large_paid_eur,
  frequency_bps,
  severity_eur,
  loss_ratio_bps,
  loss_ratio_ex_large_bps,
  paid_eur - severity_eur * claim_count AS severity_tie_eur,
  claim_count * 10000 - frequency_bps * policies AS frequency_tie,
  paid_eur * 10000 - loss_ratio_bps * earned_premium_eur AS loss_ratio_tie
FROM v_product_scorecard
ORDER BY product_id;
