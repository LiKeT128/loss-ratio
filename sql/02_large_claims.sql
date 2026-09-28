-- Claims at or above the assumption. The page lists these rows, it does not paraphrase them.
SELECT
  c.claim_id,
  p.name,
  c.paid_eur
FROM v_claim c
JOIN dim_product p ON p.product_id = c.product_id
WHERE c.is_large = 1
ORDER BY c.paid_eur DESC, c.claim_id;
