"""Generates a Power BI Project (PBIP): TMDL semantic model + PBIR report. Open AR_Control_Tower.pbip in Power BI Desktop
(enable: File > Options > Preview features > 'Power BI Project (.pbip) save option' and 'TMDL / PBIR' if prompted)."""
import json, shutil
import pandas as pd
from pathlib import Path
R = Path(__file__).resolve().parent.parent
DATA = R / "powerbi" / "data"
OUT = R / "powerbi" / "AR_Control_Tower"
if OUT.exists(): shutil.rmtree(OUT)
SM, RP = OUT / "AR_Control_Tower.SemanticModel", OUT / "AR_Control_Tower.Report"
(SM / "definition" / "tables").mkdir(parents=True); (RP / "definition" / "pages").mkdir(parents=True)

TABLES = ["dim_client", "v_invoice_status", "r_ar_ageing", "r_monthly_kpi", "r_credit_util", "c_unbilled", "c_unapplied",
          "c_duplicate_invoices", "c_gst_mismatch", "c_credit_note_exceptions", "c_completeness", "ml_open_invoice_scores", "ai_insights"]
DATECOLS = {"invoice_date", "due_date", "last_pay", "checkout", "pay_date", "credit_note_date", "mth", "checkin"}
J = lambda p, o: (p.parent.mkdir(parents=True, exist_ok=True), p.write_text(json.dumps(o, indent=2)))

def q(n): return f"'{n}'" if not n.replace("_", "").isalnum() else n
cols = {}
for t in TABLES:
    df = pd.read_csv(DATA / f"{t}.csv", nrows=2000)
    c = []
    for name, dt in df.dtypes.items():
        if name in DATECOLS: k = ("dateTime", "type datetime", "none")
        elif str(dt).startswith("int"): k = ("int64", "Int64.Type", "none")
        elif str(dt).startswith("float"): k = ("double", "type number", "none")
        else: k = ("string", "type text", "none")
        c.append((name, *k))
    cols[t] = c
    L = [f"table {t}", ""]
    for name, dtp, _, sb in c:
        L += [f"\tcolumn {q(name)}", f"\t\tdataType: {dtp}", f"\t\tsourceColumn: {name}", f"\t\tsummarizeBy: {sb}", ""]
    typed = ",".join(f'{{"{n}", {m}}}' for n, _, m, _ in c)
    L += [f"\tpartition {t} = m", "\t\tmode: import", "\t\tsource =", "\t\t\t\tlet",
          f'\t\t\t\t\tSource = Csv.Document(File.Contents(DataFolder & "\\{t}.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
          "\t\t\t\t\tHdr = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
          f"\t\t\t\t\tTyped = Table.TransformColumnTypes(Hdr, {{{typed}}}, \"en-US\")",
          "\t\t\t\tin", "\t\t\t\t\tTyped", ""]
    (SM / "definition" / "tables" / f"{t}.tmdl").write_text("\n".join(L))

M = [("Total Billed", "SUM(v_invoice_status[total])", "#,0"),
     ("Total Outstanding", "SUM(v_invoice_status[outstanding])", "#,0"),
     ("Overdue AR", "CALCULATE([Total Outstanding], v_invoice_status[days_past_due] > 0)", "#,0"),
     ("Overdue %", "DIVIDE([Overdue AR], [Total Outstanding])", "0.0%"),
     ("AR 90+", "CALCULATE([Total Outstanding], v_invoice_status[days_past_due] > 90)", "#,0"),
     ("Collected", "SUM(r_monthly_kpi[collected])", "#,0"),
     ("Collection Eff %", "DIVIDE(SUM(r_monthly_kpi[collected]), SUM(r_monthly_kpi[billed]))", "0.0%"),
     ("DSO (days)", "AVERAGE(r_monthly_kpi[dso_days])", "0.0"),
     ("Unbilled Revenue", "SUM(c_unbilled[est_total])", "#,0"),
     ("Unapplied Cash", "SUM(c_unapplied[amount])", "#,0"),
     ("Net AR after unapplied", "[Total Outstanding] - [Unapplied Cash]", "#,0"),
     ("Credit Breach Clients", 'CALCULATE(DISTINCTCOUNT(r_credit_util[client_id]), r_credit_util[status] = "BREACH")', "0"),
     ("Duplicate Overbilled", "SUM(c_duplicate_invoices[overbilled])", "#,0"),
     ("Duplicate Bookings", "COUNTROWS(c_duplicate_invoices)", "#,0"),
     ("GST Exceptions", "COUNTROWS(c_gst_mismatch)", "#,0"),
     ("CN Exceptions", "COUNTROWS(c_credit_note_exceptions)", "#,0"),
     ("Expected 30d Loss", "SUM(ml_open_invoice_scores[expected_loss_30d])", "#,0"),
     ("Control Score", "100 - 100 * DIVIDE([GST Exceptions] + [CN Exceptions] + [Duplicate Bookings], DISTINCTCOUNT(v_invoice_status[invoice_id])) * 10", "0.0")]
L = ["table _Measures", ""]
for n, e, f in M: L += [f"\tmeasure {q(n)} = {e}", f"\t\tformatString: {f}", ""]
L += ["\tcolumn Value", "\t\tisHidden", "\t\tdataType: int64", "\t\tsourceColumn: [Value]", "\t\tsummarizeBy: none", "",
      "\tpartition _Measures = calculated", "\t\tmode: import", "\t\tsource = {1}", ""]
(SM / "definition" / "tables" / "_Measures.tmdl").write_text("\n".join(L))

rel = []
for i, t in enumerate(["v_invoice_status", "r_ar_ageing", "r_credit_util", "c_unbilled", "c_unapplied", "c_duplicate_invoices",
                       "c_gst_mismatch", "c_credit_note_exceptions", "ml_open_invoice_scores"]):
    rel += [f"relationship rel_{i}", f"\tfromColumn: {t}.client_id", "\ttoColumn: dim_client.client_id", ""]
(SM / "definition" / "relationships.tmdl").write_text("\n".join(rel))
(SM / "definition" / "expressions.tmdl").write_text(
    'expression DataFolder = "C:\\ar-control-tower\\powerbi\\data" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n')
(SM / "definition" / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1600\n")
refs = "\n".join(f"ref table {q(t)}" for t in ["_Measures"] + TABLES)
(SM / "definition" / "model.tmdl").write_text(
    "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tdiscourageImplicitMeasures\n\n"
    + refs + "\nref expression DataFolder\n")
J(SM / "definition.pbism", {"version": "4.0", "settings": {}})
J(RP / "definition.pbir", {"version": "4.0", "datasetReference": {"byPath": {"path": "../AR_Control_Tower.SemanticModel"}}})
J(OUT / "AR_Control_Tower.pbip", {"version": "1.0", "artifacts": [{"report": {"path": "AR_Control_Tower.Report"}}],
                                  "settings": {"enableAutoRecovery": True}})
S = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
D = RP / "definition"
J(D / "version.json", {"$schema": f"{S}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
J(D / "report.json", {"$schema": f"{S}/report/1.0.0/schema.json",
   "themeCollection": {"baseTheme": {"name": "CY24SU10", "reportVersionAtImport": "5.59", "type": "SharedResources"}},
   "layoutOptimization": "None"})

lit = lambda v: {"expr": {"Literal": {"Value": v}}}
def ref(kind, tbl, prop, agg=None):
    if kind == "m": f = {"Measure": {"Expression": {"SourceRef": {"Entity": tbl}}, "Property": prop}}
    else:
        f = {"Column": {"Expression": {"SourceRef": {"Entity": tbl}}, "Property": prop}}
        if agg is not None: f = {"Aggregation": {"Expression": f, "Function": agg}}
    return {"field": f, "queryRef": f"{tbl}.{prop}"}
CARD_STYLE = {"background": [{"properties": {"color": {"solid": {"color": lit("'#131A2E'")}}}}]}
PAGES, vcount = [], [0]
def visual(page, vtype, x, y, w, h, roles, title=None):
    vcount[0] += 1; vid = f"v{vcount[0]:03d}"
    qs = {r: {"projections": ps} for r, ps in roles.items()}
    v = {"visualType": vtype, "query": {"queryState": qs}, "drillFilterOtherVisuals": True}
    if title: v["visualContainerObjects"] = {"title": [{"properties": {"show": lit("true"), "text": lit(f"'{title}'"),
                                              "fontColor": {"solid": {"color": lit("'#E5E7EB'")}}}}]}
    J(D / "pages" / page / "visuals" / vid / "visual.json",
      {"$schema": f"{S}/visualContainer/1.0.0/schema.json", "name": vid,
       "position": {"x": x, "y": y, "width": w, "height": h, "z": vcount[0]}, "visual": v})
def new_page(pid, name):
    PAGES.append(pid)
    J(D / "pages" / pid / "page.json", {"$schema": f"{S}/page/1.0.0/schema.json", "name": pid, "displayName": name,
      "displayOption": "FitToPage", "height": 720, "width": 1280,
      "objects": {"background": [{"properties": {"color": {"solid": {"color": lit("'#0B1020'")}}, "transparency": lit("0D")}}]}})
m = lambda n: ref("m", "_Measures", n)
c = lambda t, p, a=None: ref("c", t, p, a)
def cards(page, names, y=20):
    w = 1240 // len(names)
    for i, n in enumerate(names): visual(page, "card", 20 + i * w, y, w - 12, 90, {"Values": [m(n)]})

new_page("p1", "Executive cockpit")
cards("p1", ["Total Outstanding", "Overdue %", "DSO (days)", "Collection Eff %", "Expected 30d Loss", "Control Score"])
visual("p1", "clusteredColumnChart", 20, 130, 620, 280, {"Category": [c("r_monthly_kpi", "mth")],
       "Y": [c("r_monthly_kpi", "billed", 0), c("r_monthly_kpi", "collected", 0)]}, "Billed vs collected")
visual("p1", "lineChart", 660, 130, 600, 280, {"Category": [c("r_monthly_kpi", "mth")], "Y": [m("DSO (days)")]}, "DSO trend")
visual("p1", "barChart", 20, 430, 620, 270, {"Category": [c("dim_client", "industry")], "Y": [m("Overdue AR")]}, "Overdue AR by industry")
visual("p1", "slicer", 660, 430, 290, 270, {"Values": [c("dim_client", "industry")]}, "Industry")
visual("p1", "slicer", 970, 430, 290, 270, {"Values": [c("dim_client", "relationship_manager")]}, "Relationship manager")

new_page("p2", "AR ageing")
cards("p2", ["Total Outstanding", "Overdue AR", "AR 90+", "Net AR after unapplied"])
visual("p2", "stackedColumnChart", 20, 130, 620, 300, {"Category": [c("r_ar_ageing", "relationship_manager")],
       "Y": [c("r_ar_ageing", k, 0) for k in ["current_bucket", "d1_30", "d31_60", "d61_90", "d90_plus"]]}, "Ageing by RM")
visual("p2", "barChart", 660, 130, 600, 300, {"Category": [c("r_ar_ageing", "client_name")], "Y": [c("r_ar_ageing", "d90_plus", 0)]}, "Top 90+ clients")
visual("p2", "tableEx", 20, 450, 1240, 250, {"Values": [c("r_ar_ageing", k) for k in ["client_name", "industry", "relationship_manager", "total_outstanding", "d1_30", "d31_60", "d61_90", "d90_plus"]]}, "Client ageing")

new_page("p3", "Collections worklist (ML)")
cards("p3", ["Expected 30d Loss", "Total Outstanding"])
visual("p3", "scatterChart", 20, 130, 620, 570, {"Category": [c("ml_open_invoice_scores", "invoice_id")],
       "X": [c("ml_open_invoice_scores", "outstanding", 0)], "Y": [c("ml_open_invoice_scores", "p_late30", 1)]}, "Outstanding vs P(late>30d)")
visual("p3", "slicer", 660, 130, 600, 90, {"Values": [c("ml_open_invoice_scores", "priority")]}, "Priority")
visual("p3", "tableEx", 660, 230, 600, 470, {"Values": [c("ml_open_invoice_scores", k) for k in ["invoice_id", "client_id", "outstanding", "p_late30", "expected_loss_30d", "priority"]]}, "Call list")

new_page("p4", "Control exceptions")
cards("p4", ["Duplicate Bookings", "Duplicate Overbilled", "GST Exceptions", "CN Exceptions", "Unbilled Revenue", "Unapplied Cash"])
visual("p4", "lineChart", 20, 130, 620, 270, {"Category": [c("c_completeness", "mth")], "Y": [c("c_completeness", "completeness", 1)]}, "Booking-to-invoice completeness")
visual("p4", "tableEx", 660, 130, 600, 270, {"Values": [c("c_duplicate_invoices", k) for k in ["booking_id", "client_id", "n_invoices", "overbilled"]]}, "Duplicate invoices")
visual("p4", "tableEx", 20, 420, 620, 280, {"Values": [c("c_gst_mismatch", k) for k in ["invoice_id", "books_gst", "gstr2b_gst", "diff", "issue"]]}, "GST mismatches")
visual("p4", "tableEx", 660, 420, 600, 280, {"Values": [c("c_credit_note_exceptions", k) for k in ["cn_id", "cn_amount", "pct_of_invoice", "approver", "reasons"]]}, "Credit-note exceptions")

new_page("p5", "Credit limits & AI notes")
cards("p5", ["Credit Breach Clients", "Total Outstanding"])
visual("p5", "tableEx", 20, 130, 740, 570, {"Values": [c("r_credit_util", k) for k in ["client_name", "credit_limit", "exposure", "utilisation", "status"]]}, "Credit utilisation")
visual("p5", "slicer", 780, 130, 480, 100, {"Values": [c("r_credit_util", "status")]}, "Status")
visual("p5", "tableEx", 780, 240, 480, 460, {"Values": [c("ai_insights", "text")]}, "AI insights")
J(D / "pages" / "pages.json", {"$schema": f"{S}/pagesMetadata/1.0.0/schema.json", "pageOrder": PAGES, "activePageName": "p1"})
shutil.copy(R / "powerbi" / "theme.json", OUT / "theme.json")
print("pages", len(PAGES), "visuals", vcount[0])
