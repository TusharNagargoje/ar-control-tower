"""Synthetic corporate-travel finance data (clients, bookings, invoices, payments, credit notes, GSTR-2B).
Control-failure patterns are deliberately injected so the control reports have something real to catch."""
import numpy as np, pandas as pd
from pathlib import Path

rng = np.random.default_rng(42)
OUT = Path(__file__).resolve().parent.parent / "data"
N_CLIENTS, END = 120, pd.Timestamp("2026-10-31")
START = END - pd.Timedelta(days=365)

states = ["MH", "DL", "KA", "TN", "HR", "GJ", "UP", "WB", "TG"]
inds = ["IT Services", "BFSI", "Pharma", "Manufacturing", "Consulting", "E-commerce"]
clients = pd.DataFrame({
    "client_id": [f"C{i:04d}" for i in range(N_CLIENTS)],
    "client_name": [f"Client {i:03d} Pvt Ltd" for i in range(N_CLIENTS)],
    "industry": rng.choice(inds, N_CLIENTS),
    "state": rng.choice(states, N_CLIENTS),
    "payment_terms_days": rng.choice([15, 30, 45, 60], N_CLIENTS, p=[.15, .45, .25, .15]),
    "relationship_manager": rng.choice(["Asha", "Rohit", "Meera", "Karan", "Sneha"], N_CLIENTS),
    "reliability": rng.beta(5, 2, N_CLIENTS),      # hidden: drives payment delay
})
size = rng.lognormal(0, .7, N_CLIENTS)
clients["monthly_bookings"] = np.clip((size * 40).astype(int), 8, 400)
clients["credit_limit"] = (clients.monthly_bookings * 4200 * rng.uniform(1.0, 2.2, N_CLIENTS)).round(-3)
clients["gstin"] = [f"{rng.integers(10,38)}AAAC{i:04d}A1Z{rng.integers(1,9)}" for i in range(N_CLIENTS)]

rows = []
for c in clients.itertuples():
    n = int(c.monthly_bookings * 12)
    d = START + pd.to_timedelta(rng.integers(0, 365, n), unit="D")
    stay = rng.integers(1, 6, n)
    amt = (rng.lognormal(8.3, .45, n) * stay).round(2)
    rows.append(pd.DataFrame({"client_id": c.client_id, "checkin": d, "nights": stay, "amount": amt}))
b = pd.concat(rows, ignore_index=True).sort_values("checkin").reset_index(drop=True)
b["booking_id"] = [f"B{i:07d}" for i in range(len(b))]
b["checkout"] = b.checkin + pd.to_timedelta(b.nights, unit="D")
b["hotel_brand"] = rng.choice(["FabHotels", "Via"], len(b), p=[.8, .2])
b["status"] = rng.choice(["completed", "cancelled"], len(b), p=[.93, .07])
b.loc[b.checkout > END, "status"] = "upcoming"
b["gst_rate"] = np.where(b.amount / b.nights > 7500, .18, .12)
b = b[["booking_id", "client_id", "hotel_brand", "checkin", "checkout", "nights", "amount", "gst_rate", "status"]]

# invoices: completed bookings, with ~2.5% missing invoice (control failure) and ~1% duplicated
done = b[b.status == "completed"].copy()
inv = done.sample(frac=.975, random_state=1).copy()
inv["invoice_id"] = [f"INV{i:07d}" for i in range(len(inv))]
inv["invoice_date"] = inv.checkout + pd.to_timedelta(rng.integers(1, 6, len(inv)), unit="D")
inv = inv.merge(clients[["client_id", "payment_terms_days", "gstin"]], on="client_id")
inv["due_date"] = inv.invoice_date + pd.to_timedelta(inv.payment_terms_days, unit="D")
inv["taxable"] = inv.amount
inv["gst"] = (inv.amount * inv.gst_rate).round(2)
inv["total"] = inv.taxable + inv.gst
inv = inv[inv.invoice_date <= END]
dups = inv.sample(frac=.01, random_state=2).copy()
dups["invoice_id"] = [f"INV{i:07d}" for i in range(len(inv), len(inv) + len(dups))]
dups["invoice_date"] += pd.Timedelta(days=1)
inv = pd.concat([inv, dups], ignore_index=True)
inv = inv[["invoice_id", "booking_id", "client_id", "invoice_date", "due_date", "taxable", "gst", "total", "gstin"]]

# payments: delay depends on client reliability + invoice size; ~12% of cash lands unapplied
pay_rows = []
cl = clients.set_index("client_id")
for r in inv.itertuples():
    rel = cl.at[r.client_id, "reliability"]
    p_unpaid_yet = 0.0
    delay = rng.normal((1 - rel) * 55 - 8, 12) + (r.total > 60000) * 6
    pdate = r.due_date + pd.Timedelta(days=int(delay))
    if pdate > END or rng.random() < .015:        # still open / written-off-ish
        continue
    pay_rows.append((r.client_id, pdate, r.total, r.invoice_id if rng.random() > .12 else None))
pay = pd.DataFrame(pay_rows, columns=["client_id", "pay_date", "amount", "applied_invoice_id"])
pay.insert(0, "payment_id", [f"PAY{i:07d}" for i in range(len(pay))])

# credit notes: ~4%, a few unusually large (exception report fodder)
cn = inv.sample(frac=.04, random_state=3)[["invoice_id", "client_id", "invoice_date", "total"]].copy()
cn["credit_note_date"] = cn.invoice_date + pd.to_timedelta(rng.integers(3, 40, len(cn)), unit="D")
cn["cn_amount"] = (cn.total * rng.choice([.05, .1, .3, .6, 1.0], len(cn), p=[.4, .3, .15, .1, .05])).round(2)
cn["approver"] = rng.choice(["Asha", "Rohit", "Meera", None], len(cn), p=[.3, .3, .3, .1])
cn = cn[cn.credit_note_date <= END][["invoice_id", "client_id", "credit_note_date", "cn_amount", "approver"]]
cn.insert(0, "cn_id", [f"CN{i:06d}" for i in range(len(cn))])

# GSTR-2B (what the client reports): ~3% GST mismatch, ~2% invoices absent
g = inv.sample(frac=.98, random_state=4)[["invoice_id", "gstin", "gst"]].rename(columns={"gst": "gstr2b_gst"}).copy()
bad = g.sample(frac=.03, random_state=5).index
g.loc[bad, "gstr2b_gst"] = (g.loc[bad, "gstr2b_gst"] * rng.choice([.5, .9, 1.1], len(bad))).round(2)

for name, df in dict(clients=clients.drop(columns="reliability"), bookings=b, invoices=inv, payments=pay,
                     credit_notes=cn, gstr2b=g).items():
    df.to_csv(OUT / f"{name}.csv", index=False)
    print(f"{name:13s}{len(df):>9,}")
