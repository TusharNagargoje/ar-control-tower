"""Load CSVs into DuckDB, run the SQL layer, export Power BI marts (star schema) to powerbi/data/."""
import duckdb, pandas as pd
from pathlib import Path
R = Path(__file__).resolve().parent.parent
con = duckdb.connect(str(R / "data" / "ar.duckdb"))
for t in ["clients","bookings","invoices","payments","credit_notes","gstr2b"]:
    con.execute(f"CREATE OR REPLACE TABLE {t} AS SELECT * FROM read_csv_auto('{R}/data/{t}.csv')")
for f in sorted((R/"sql").glob("0[123]*.sql")):
    con.execute(f.read_text())
out = R / "powerbi" / "data"; out.mkdir(exist_ok=True)
for v in ["v_invoice_status","r_ar_ageing","r_monthly_kpi","c_unbilled","c_unapplied","r_credit_util",
          "c_duplicate_invoices","c_gst_mismatch","c_credit_note_exceptions","c_completeness"]:
    df = con.execute(f"SELECT * FROM {v}").df()
    if "invoice_ids" in df: df["invoice_ids"] = df.invoice_ids.astype(str)
    df.to_csv(out / f"{v}.csv", index=False); print(f"{v:26s}{len(df):>8,}")
con.execute(f"COPY (SELECT * FROM clients) TO '{out}/dim_client.csv' (HEADER)")
print(con.execute("SELECT mth,billed,collected,collection_efficiency,dso_days FROM r_monthly_kpi ORDER BY mth DESC LIMIT 4").df())
print(con.execute("SELECT SUM(total_outstanding) ar, SUM(d90_plus) d90 FROM r_ar_ageing").df())
