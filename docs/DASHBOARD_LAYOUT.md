# Power BI layout (16:9, dark theme, 24px grid)
Global: slicers synced across pages (Date, Industry, RM, Client). Page navigator buttons top-left. Bookmarks for "Overdue only" / "Breach only".

**1. Executive cockpit** - KPI cards (Total Outstanding, Overdue %, DSO, Collection Eff %, Expected 30d Loss, Control Score) with
sparklines; combo chart billed vs collected + DSO line; field-parameter bar (switch metric by industry); decomposition tree on Overdue AR;
Smart narrative bound to ai_insights summary.
**2. AR ageing** - stacked column by bucket per RM; ageing matrix with conditional-format heatmap; drill-through to client page; top-10 client bar.
**3. Collections worklist** - table from ml_open_invoice_scores sorted by expected_loss_30d, priority icons (P1-P4), scatter outstanding vs p_late30,
tooltip page showing client payment history; "Call today" bookmark = P1 only.
**4. Control exceptions** - four tiles (Duplicates, GST mismatch, CN exceptions, Unbilled) each drill-through to the exception list; trend of
completeness % by month (c_completeness); waterfall of over-billed + unbilled + unapplied cash impact.
**5. Credit limits** - gauge per selected client, utilisation histogram, breach/warn table, what-if parameter "limit increase %" recomputing breaches.
**6. AI insights** - ai_insights narrative + client notes list; Q&A visual enabled with synonyms (DSO, AR, overdue).
Aesthetics: one accent per KPI state (cyan ok, amber warn, red breach), 10px rounded cards, no gridlines, consistent number format Rs L/Cr.
