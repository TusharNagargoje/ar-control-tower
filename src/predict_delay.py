"""Payment-delay model: P(invoice paid >30 days after due date). Point-in-time features (expanding client history,
no look-ahead). Scores open invoices -> collections worklist."""
import duckdb, numpy as np, pandas as pd
from pathlib import Path
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score
R = Path(__file__).resolve().parent.parent
con = duckdb.connect(str(R/"data"/"ar.duckdb"))
df = con.execute("""SELECT invoice_id, client_id, invoice_date, due_date, total, payment_terms_days, industry,
                    last_pay, outstanding, paid_amt FROM v_invoice_status""").df()
df["delay"] = (pd.to_datetime(df.last_pay) - pd.to_datetime(df.due_date)).dt.days
df["settled"] = df.paid_amt > 0.99 * df.total
df = df.sort_values("invoice_date")
# expanding client history using only invoices already SETTLED before this invoice date
hist = df[df.settled][["client_id", "last_pay", "delay"]].sort_values("last_pay")
def asof_mean(row_df):
    out = []
    for cid, g in row_df.groupby("client_id"):
        h = hist[hist.client_id == cid]
        cum = h.delay.expanding().mean().values; t = pd.to_datetime(h.last_pay).values
        idx = np.searchsorted(t, pd.to_datetime(g.invoice_date).values) - 1
        out.append(pd.Series(np.where(idx >= 0, cum[np.clip(idx, 0, None)] if len(cum) else np.nan, np.nan), index=g.index))
    return pd.concat(out)
df["client_avg_delay"] = asof_mean(df)
df["log_total"] = np.log1p(df.total); df["dow"] = pd.to_datetime(df.invoice_date).dt.dayofweek
X = pd.get_dummies(df[["client_avg_delay", "log_total", "payment_terms_days", "dow", "industry"]], columns=["industry"])
y = (df.delay > 30).astype(int)
train = df.settled & (pd.to_datetime(df.invoice_date) < "2026-06-01")
test = df.settled & (pd.to_datetime(df.invoice_date) >= "2026-06-01") & (pd.to_datetime(df.invoice_date) < "2026-08-01")
m = HistGradientBoostingClassifier(max_depth=4, learning_rate=.08, max_iter=200, random_state=0).fit(X[train], y[train])
p = m.predict_proba(X[test])[:, 1]
print(f"holdout AUC {roc_auc_score(y[test], p):.3f}  PR-AUC {average_precision_score(y[test], p):.3f}  base rate {y[test].mean():.3f}")
open_ = df[df.outstanding > 1].copy()
open_["p_late30"] = m.predict_proba(X.loc[open_.index])[:, 1].round(4)
open_["expected_loss_30d"] = (open_.p_late30 * open_.outstanding).round(0)
open_["priority"] = pd.qcut(open_.expected_loss_30d.rank(method="first"), 4, labels=["P4", "P3", "P2", "P1"])
out = R/"powerbi"/"data"
open_[["invoice_id","client_id","due_date","outstanding","client_avg_delay","p_late30","expected_loss_30d","priority"]].to_csv(out/"ml_open_invoice_scores.csv", index=False)
print(open_.groupby("priority", observed=True).agg(n=("invoice_id","count"), out=("outstanding","sum")).round(0))
