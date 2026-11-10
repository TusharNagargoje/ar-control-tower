"""AI layer: turns the control-report numbers into a CFO-style narrative + per-client collection notes.
Uses the Anthropic API if ANTHROPIC_API_KEY is set; otherwise a deterministic template (so the pipeline always runs).
Output: powerbi/data/ai_insights.csv  (load into Power BI; show in a card / smart-narrative visual)."""
import os, duckdb, pandas as pd
from pathlib import Path
R = Path(__file__).resolve().parent.parent
con = duckdb.connect(str(R/"data"/"ar.duckdb"), read_only=True)
top = con.execute("""SELECT a.client_name, a.total_outstanding, a.d90_plus, u.utilisation, u.status
                     FROM r_ar_ageing a JOIN r_credit_util u USING(client_id)
                     ORDER BY a.d90_plus DESC LIMIT 10""").df()
ctrl = con.execute("""SELECT (SELECT COUNT(*) FROM c_duplicate_invoices) dups,
  (SELECT SUM(overbilled) FROM c_duplicate_invoices) overbilled,(SELECT COUNT(*) FROM c_gst_mismatch) gst,
  (SELECT SUM(est_total) FROM c_unbilled) unbilled,(SELECT SUM(amount) FROM c_unapplied) unapplied""").df().iloc[0]
def template(r):
    return (f"{r.client_name}: Rs {r.total_outstanding/1e5:.1f}L outstanding, Rs {r.d90_plus/1e5:.1f}L over 90 days, "
            f"credit utilisation {r.utilisation:.0%} ({r.status}). Escalate to RM and hold new bookings if BREACH.")
notes = [template(r) for r in top.itertuples()]
if os.getenv("ANTHROPIC_API_KEY"):
    import anthropic
    cl = anthropic.Anthropic()
    prompt = ("You are a finance controller. In 5 bullets, summarise risks and actions.\nControl totals: "
              f"{ctrl.to_dict()}\nTop exposures:\n{top.to_string(index=False)}")
    summary = cl.messages.create(model="claude-sonnet-5-5", max_tokens=500,
                                 messages=[{"role": "user", "content": prompt}]).content[0].text
else:
    summary = (f"{int(ctrl.dups)} bookings invoiced more than once (Rs {ctrl.overbilled/1e5:.1f}L over-billed); "
               f"{int(ctrl.gst)} GST mismatches vs GSTR-2B; Rs {ctrl.unbilled/1e5:.1f}L unbilled; "
               f"Rs {ctrl.unapplied/1e5:.1f}L unapplied cash inflating AR.")
pd.DataFrame({"kind": ["summary"] + ["client_note"] * len(notes), "text": [summary] + notes}) \
  .to_csv(R/"powerbi"/"data"/"ai_insights.csv", index=False)
print(summary)
