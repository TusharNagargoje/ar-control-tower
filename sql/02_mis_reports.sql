-- R1 AR ageing by client
CREATE OR REPLACE VIEW r_ar_ageing AS
SELECT client_id, client_name, industry, relationship_manager,
  SUM(outstanding) FILTER (WHERE days_past_due <= 0)               AS current_bucket,
  SUM(outstanding) FILTER (WHERE days_past_due BETWEEN 1 AND 30)   AS d1_30,
  SUM(outstanding) FILTER (WHERE days_past_due BETWEEN 31 AND 60)  AS d31_60,
  SUM(outstanding) FILTER (WHERE days_past_due BETWEEN 61 AND 90)  AS d61_90,
  SUM(outstanding) FILTER (WHERE days_past_due > 90)               AS d90_plus,
  SUM(outstanding) total_outstanding
FROM v_invoice_status WHERE outstanding > 1 GROUP BY 1,2,3,4;

-- R2 DSO / collection efficiency by month (count-back DSO)
CREATE OR REPLACE VIEW r_monthly_kpi AS
WITH m AS (
  SELECT DATE_TRUNC('month', invoice_date)::DATE mth, SUM(total) billed FROM invoices WHERE invoice_date <= DATE '2026-10-31' GROUP BY 1),
 c AS (SELECT DATE_TRUNC('month', pay_date)::DATE mth, SUM(amount) collected FROM payments GROUP BY 1),
 ar AS (SELECT m.mth, (SELECT SUM(i.total) FROM invoices i WHERE i.invoice_date <= LAST_DAY(m.mth))
                    - (SELECT COALESCE(SUM(p.amount),0) FROM payments p WHERE p.pay_date <= LAST_DAY(m.mth)) closing_ar
        FROM m)
SELECT m.mth, m.billed, COALESCE(c.collected,0) collected, ar.closing_ar,
       ROUND(COALESCE(c.collected,0)/NULLIF(m.billed,0),3) collection_efficiency,
       ROUND(ar.closing_ar/NULLIF(m.billed,0)*DAY(LAST_DAY(m.mth)),1) dso_days
FROM m LEFT JOIN c USING(mth) JOIN ar USING(mth) ORDER BY 1;

-- R3 Unbilled revenue: completed bookings with no invoice
CREATE OR REPLACE VIEW c_unbilled AS
SELECT b.booking_id, b.client_id, b.checkout, b.amount, ROUND(b.amount*(1+b.gst_rate),2) est_total,
       DATE '2026-10-31' - b.checkout::DATE days_unbilled
FROM bookings b LEFT JOIN invoices i USING(booking_id)
WHERE b.status='completed' AND i.invoice_id IS NULL;

-- R4 Unapplied receipts
CREATE OR REPLACE VIEW c_unapplied AS
SELECT payment_id, client_id, pay_date, amount, DATE '2026-10-31' - pay_date::DATE days_unapplied
FROM payments WHERE applied_invoice_id IS NULL;

-- R5 Credit limit utilisation
CREATE OR REPLACE VIEW r_credit_util AS
SELECT c.client_id, c.client_name, c.credit_limit, COALESCE(SUM(v.outstanding),0) exposure,
       ROUND(COALESCE(SUM(v.outstanding),0)/c.credit_limit,3) utilisation,
       CASE WHEN COALESCE(SUM(v.outstanding),0) > c.credit_limit THEN 'BREACH'
            WHEN COALESCE(SUM(v.outstanding),0) > .85*c.credit_limit THEN 'WARN' ELSE 'OK' END status
FROM clients c LEFT JOIN v_invoice_status v USING(client_id) GROUP BY 1,2,3;
