-- Redshift-compatible SQL (runs unchanged on DuckDB). :asof = 2026-10-31
CREATE OR REPLACE VIEW v_invoice_status AS
WITH paid AS (SELECT applied_invoice_id invoice_id, SUM(amount) paid_amt, MAX(pay_date) last_pay
              FROM payments WHERE applied_invoice_id IS NOT NULL GROUP BY 1),
     cn AS (SELECT invoice_id, SUM(cn_amount) cn_amt FROM credit_notes GROUP BY 1)
SELECT i.*, c.client_name, c.industry, c.relationship_manager, c.payment_terms_days,
       COALESCE(p.paid_amt,0) paid_amt, COALESCE(n.cn_amt,0) cn_amt, p.last_pay,
       GREATEST(i.total - COALESCE(p.paid_amt,0) - COALESCE(n.cn_amt,0), 0) outstanding,
       DATE '2026-10-31' - i.due_date::DATE days_past_due
FROM invoices i JOIN clients c USING(client_id)
LEFT JOIN paid p USING(invoice_id) LEFT JOIN cn n USING(invoice_id);
