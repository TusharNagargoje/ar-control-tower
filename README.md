# Collections & Credit-Risk Control Tower
End-to-end finance analytics for a corporate-travel business: Python -> DuckDB/SQL (Redshift-compatible) -> ML -> LLM -> Power BI.

```bash
pip install pandas numpy scikit-learn duckdb anthropic   # anthropic optional
python src/generate_data.py   # synthetic bookings/invoices/payments/credit notes/GSTR-2B (control failures injected)
python src/build_marts.py     # SQL layer + CSV marts -> powerbi/data
python src/predict_delay.py   # P(paid >30d late) for open invoices (holdout AUC ~0.83)
python src/ai_insights.py     # CFO narrative + client notes (Claude if ANTHROPIC_API_KEY set)
```
Then in Power BI Desktop: Get Data > Folder/CSV for `powerbi/data/*.csv`, View > Themes > `theme.json`, paste `measures.dax`.
Swap the CSV loads for Redshift (`Get Data > Amazon Redshift`) — the SQL in `sql/` runs unchanged.

## Report pages (see docs/DASHBOARD_LAYOUT.md)
1 Executive cockpit - 2 AR ageing & DSO - 3 Collections worklist (ML) - 4 Control exceptions - 5 Credit limits - 6 AI insights

## Open the ready-made Power BI project
1. Unzip to `C:\ar-control-tower`. 2. Power BI Desktop > File > Options > Preview features: enable
"Power BI Project (.pbip) save option" and "Store semantic model using TMDL format" and "Store reports using enhanced metadata format (PBIR)"; restart.
3. Open `powerbi/AR_Control_Tower/AR_Control_Tower.pbip`. 4. If prompted for the `DataFolder` parameter (or on refresh errors):
Home > Transform data > Manage parameters > set `DataFolder` to your `...\powerbi\data` path. 5. Refresh. 5 pages / 38 visuals; dark theme via View > Themes > Browse (`theme.json`).
Regenerate the project with `python src/make_pbip.py`.
