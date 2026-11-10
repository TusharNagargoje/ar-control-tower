-- C1 Duplicate invoicing: same booking invoiced more than once
CREATE OR REPLACE VIEW c_duplicate_invoices AS
SELECT booking_id, client_id, COUNT(*) n_invoices, SUM(total) total_billed, SUM(total)-MIN(total) overbilled,
       LIST(invoice_id ORDER BY invoice_date) invoice_ids
FROM invoices GROUP BY 1,2 HAVING COUNT(*) > 1;

-- C2 GST mismatch: books vs GSTR-2B (tolerance Rs 1), plus invoices missing from GSTR-2B
CREATE OR REPLACE VIEW c_gst_mismatch AS
SELECT i.invoice_id, i.client_id, i.invoice_date, i.gst books_gst, g.gstr2b_gst,
       ROUND(i.gst - COALESCE(g.gstr2b_gst,0),2) diff,
       CASE WHEN g.invoice_id IS NULL THEN 'MISSING_IN_2B' ELSE 'AMOUNT_MISMATCH' END issue
FROM invoices i LEFT JOIN gstr2b g USING(invoice_id)
WHERE g.invoice_id IS NULL OR ABS(i.gst - g.gstr2b_gst) > 1;

-- C3 Credit-note exceptions: >=30% of invoice, or no approver, or issued >30 days after invoice
CREATE OR REPLACE VIEW c_credit_note_exceptions AS
SELECT n.cn_id, n.invoice_id, n.client_id, n.cn_amount, i.total inv_total,
       ROUND(n.cn_amount/i.total,2) pct_of_invoice, n.approver,
       n.credit_note_date::DATE - i.invoice_date::DATE days_after_invoice,
       CONCAT_WS(', ', CASE WHEN n.cn_amount/i.total >= .3 THEN 'LARGE' END,
                       CASE WHEN n.approver IS NULL THEN 'NO_APPROVER' END,
                       CASE WHEN n.credit_note_date::DATE - i.invoice_date::DATE > 30 THEN 'LATE' END) reasons
FROM credit_notes n JOIN invoices i USING(invoice_id)
WHERE n.cn_amount/i.total >= .3 OR n.approver IS NULL OR n.credit_note_date::DATE - i.invoice_date::DATE > 30;

-- C4 Booking-to-invoice completeness summary
CREATE OR REPLACE VIEW c_completeness AS
SELECT DATE_TRUNC('month', checkout)::DATE mth,
       COUNT(*) FILTER (WHERE status='completed') completed_bookings,
       COUNT(*) FILTER (WHERE status='completed' AND booking_id IN (SELECT booking_id FROM invoices)) invoiced,
       ROUND(1.0*COUNT(*) FILTER (WHERE status='completed' AND booking_id IN (SELECT booking_id FROM invoices))
             / NULLIF(COUNT(*) FILTER (WHERE status='completed'),0),4) completeness
FROM bookings GROUP BY 1 ORDER BY 1;
