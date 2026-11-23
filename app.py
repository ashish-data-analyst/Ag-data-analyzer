import io
import json
import re
import zipfile

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

import auth_db as adb

st.set_page_config(
    page_title="AG Data Analyzer | Data Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================
# THEMES
# =========================================================
THEMES = {
    "Light": dict(bg="#F4F6FB", surface="#FFFFFF", ink="#17233D", muted="#64748B", line="#E5EAF3",
                  side="#101B33", side2="#182847", accent="#526BFF", accent2="#354FE0",
                  hero="linear-gradient(115deg,#142747 0%,#2948A7 55%,#536BFF 100%)", plot="plotly_white"),
    "Dark": dict(bg="#0B1220", surface="#131C2F", ink="#E8EEFA", muted="#9AA8C1", line="#24324D",
                 side="#070C18", side2="#101A2E", accent="#6C84FF", accent2="#8A9DFF",
                 hero="linear-gradient(115deg,#0F1A33 0%,#1E3A8A 60%,#4F46E5 100%)", plot="plotly_dark"),
    "Emerald": dict(bg="#F1F7F5", surface="#FFFFFF", ink="#12302A", muted="#5B7A72", line="#DCEBE6",
                    side="#0B2B25", side2="#103B33", accent="#10A37F", accent2="#0B8466",
                    hero="linear-gradient(115deg,#0B2B25 0%,#0F6B55 55%,#19B38C 100%)", plot="plotly_white"),
}

SUPPORTED = ["csv", "tsv", "txt", "xlsx", "xlsm", "xls", "json", "parquet", "zip"]
PAGES = ["🏠 Overview", "🔎 Data Explorer", "📈 Analytics", "🛡️ Data Quality", "🧹 Data Cleaning", "⬇️ Export", "💬 Feedback"]


def inject_css(t):
    css = """
<style>
.stApp, [data-testid="stAppViewContainer"] { background: %bg%; color: %ink%; }
[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 1500px; padding-top: 2rem; padding-bottom: 3rem; }
#MainMenu, footer { visibility: hidden; }
h1,h2,h3,h4,h5,p,label,.stMarkdown,[data-testid="stCaptionContainer"] { color: %ink%; }
h1 { font-weight: 800; letter-spacing: -1px; }
h2,h3,h4 { font-weight: 750; letter-spacing: -.3px; }

[data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child { background: %side%; }

/* Sidebar must always be reachable */
@media (min-width: 900px) {
  [data-testid="stSidebar"], [data-testid="stSidebar"][aria-expanded="false"] {
      transform: none !important; margin-left: 0 !important; visibility: visible !important;
      min-width: 300px !important; width: 300px !important; }
  [data-testid="stSidebarCollapseButton"], [data-testid="stSidebarCollapsedControl"],
  [data-testid="collapsedControl"] { display: none !important; }
}
/* On small screens: big visible MENU button */
[data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] {
    position: fixed; top: 12px; left: 12px; z-index: 999999; background: %accent%; border-radius: 10px;
    padding: 6px 14px; display: flex !important; visibility: visible !important; opacity: 1 !important;
    box-shadow: 0 4px 14px rgba(0,0,0,.25); }
[data-testid="stSidebarCollapsedControl"] *, [data-testid="collapsedControl"] * {
    color: #FFFFFF !important; fill: #FFFFFF !important; }
[data-testid="stSidebarCollapsedControl"]::after, [data-testid="collapsedControl"]::after {
    content: "☰ MENU"; color: #FFFFFF; font-weight: 800; font-size: 13px; margin-left: 8px; align-self: center; }
[data-testid="stSidebar"] { border-right: 1px solid %side2%; }
[data-testid="stSidebar"] * { color: #E8EEFA !important; }
[data-testid="stSidebar"] hr { border-color: #30415F; }
[data-testid="stSidebar"] [data-testid="stFileUploader"] section,
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: %side2%; border: 1px dashed #61749A; border-radius: 12px; }
[data-testid="stSidebar"] [data-testid="stFileUploader"] button { background: %accent%; border: 0; }
[data-testid="stSidebar"] [data-testid="stRadio"] label { padding: 6px 9px; border-radius: 8px; }
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover { background: %side2%; }
.side-label { font-size: 11px; letter-spacing: 1.4px; font-weight: 800; color: #AEBBD1 !important; margin: 4px 0 6px; }

.hero { position: relative; overflow: hidden; background: %hero%; border-radius: 22px;
        padding: 38px 42px; margin: 2px 0 25px; box-shadow: 0 14px 35px rgba(37,67,150,.18); }
.hero:after { content:""; position:absolute; width:240px; height:240px; right:-65px; top:-100px; border-radius:50%;
        border:1px solid rgba(255,255,255,.17);
        box-shadow: 0 0 0 28px rgba(255,255,255,.045), 0 0 0 58px rgba(255,255,255,.035); }
.hero .eyebrow { color:#C9D6FF !important; font-size:12px; font-weight:800; letter-spacing:2px; margin-bottom:12px; }
.hero h1 { color:#FFF !important; font-size:clamp(28px,3vw,42px); line-height:1.12; margin:0 0 13px; }
.hero p { color:#E3EAFE !important; font-size:15px; max-width:720px; margin:0; line-height:1.7; }
.hero-tag { display:inline-block; color:#F4F7FF !important; border:1px solid rgba(255,255,255,.25);
        background:rgba(255,255,255,.10); padding:7px 11px; border-radius:30px; font-size:12px; margin:18px 5px 0 0; }

.feature-card { background:%surface%; border:1px solid %line%; border-radius:17px; padding:22px; min-height:180px;
        box-shadow:0 5px 18px rgba(20,35,70,.06); }
.feature-icon { width:43px; height:43px; display:flex; align-items:center; justify-content:center;
        background:%bg%; border-radius:12px; font-size:22px; margin-bottom:14px; }
.feature-card h3 { font-size:17px; margin:0 0 7px; color:%ink% !important; }
.feature-card p { color:%muted% !important; font-size:13px; line-height:1.6; margin:0; }
.insight { background:%surface%; border:1px solid %line%; border-left:4px solid %accent%; border-radius:10px;
        padding:11px 15px; margin-bottom:9px; font-size:13.5px; color:%ink%; }
.section-kicker { color:%accent% !important; font-size:11px; font-weight:800; letter-spacing:1.7px; margin-bottom:4px; }
.section-title { color:%ink% !important; font-size:24px; font-weight:800; margin-bottom:4px; }
.section-subtitle { color:%muted% !important; font-size:13px; margin-bottom:16px; }

[data-testid="stMetric"] { background:%surface%; border:1px solid %line%; border-radius:15px; padding:16px 19px;
        box-shadow:0 5px 16px rgba(20,35,70,.05); }
[data-testid="stMetricLabel"] p { color:%muted% !important; font-weight:650; }
[data-testid="stMetricValue"] { color:%ink% !important; font-weight:800; }

.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button { background:%accent%; color:#FFF !important; border:0;
        border-radius:10px; padding:9px 17px; font-weight:700; }
.stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover { background:%accent2%; color:#FFF !important; }
[data-testid="stDataFrame"] { border:1px solid %line%; border-radius:12px; overflow:hidden; }
[data-testid="stMain"] [data-baseweb="select"] > div, [data-testid="stMain"] [data-baseweb="input"],
[data-testid="stMain"] [data-baseweb="base-input"], [data-testid="stMain"] input,
[data-testid="stMain"] textarea { background:%surface% !important; color:%ink% !important; border-color:%line% !important; }
[data-testid="stAlert"] { background:%surface% !important; border:1px solid %line%; border-left:5px solid %accent%; }
[data-testid="stAlert"] * { color:%ink% !important; }
.stButton > button *, .stDownloadButton > button *, [data-testid="stFormSubmitButton"] > button *,
[data-testid="stBaseLinkButton-secondary"] * { color:#FFFFFF !important; }
div[data-baseweb="popover"] ul { background:%surface%; }
div[data-baseweb="popover"] li, div[data-baseweb="popover"] li * { color:%ink% !important; }
button[data-baseweb="tab"] { font-weight:700; }
hr { border-color:%line%; }
.footer { text-align:center; color:%muted% !important; padding:28px 8px 5px; font-size:11px; }
</style>"""
    for k, v in t.items():
        css = css.replace(f"%{k}%", v)
    st.markdown(css, unsafe_allow_html=True)


# =========================================================
# HELPERS
# =========================================================
def heading(kicker, title, sub=""):
    st.markdown(
        f'<div class="section-kicker">{kicker}</div><div class="section-title">{title}</div>'
        f'<div class="section-subtitle">{sub}</div>', unsafe_allow_html=True)


def num_cols(d):
    return d.select_dtypes(include=np.number).columns.tolist()


def cat_cols(d):
    return d.select_dtypes(include=["object", "category", "string", "bool"]).columns.tolist()


def to_csv(d):
    return d.to_csv(index=False).encode("utf-8-sig")


def to_excel(d):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        d.to_excel(w, index=False, sheet_name="Data")
    return buf.getvalue()


def show_fig(fig, t):
    fig.update_layout(template=t["plot"], margin=dict(l=15, r=15, t=55, b=15), title_font_size=18,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")


@st.cache_data(show_spinner="Reading file...")
def load_file(name, data):
    """Return ({dataset_name: DataFrame}, [errors]) for any supported file."""
    out, errs = {}, []
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    base = name.split("/")[-1]
    try:
        if ext in ("csv", "txt"):
            out[base] = pd.read_csv(io.BytesIO(data), sep=None, engine="python", encoding_errors="replace")
        elif ext == "tsv":
            out[base] = pd.read_csv(io.BytesIO(data), sep="\t", encoding_errors="replace")
        elif ext in ("xlsx", "xlsm", "xls"):
            sheets = pd.read_excel(io.BytesIO(data), sheet_name=None)
            for s, d in sheets.items():
                if not d.empty:
                    out[f"{base} › {s}"] = d
        elif ext == "json":
            try:
                out[base] = pd.read_json(io.BytesIO(data))
            except ValueError:
                out[base] = pd.json_normalize(json.loads(data.decode("utf-8", "replace")))
        elif ext == "parquet":
            out[base] = pd.read_parquet(io.BytesIO(data))
        elif ext == "zip":
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for m in z.namelist():
                    if m.endswith("/") or "__MACOSX" in m or m.split("/")[-1].startswith("."):
                        continue
                    if m.lower().rsplit(".", 1)[-1] in SUPPORTED[:-1]:
                        o, e = load_file(m, z.read(m))
                        out.update(o)
                        errs += e
        else:
            errs.append(f"{name}: unsupported format")
    except Exception as ex:
        errs.append(f"{name}: {ex}")
    return {k: v for k, v in out.items() if not v.empty}, errs


# =========================================================
# SIDEBAR  (everything lives here)
# =========================================================
@st.cache_data(show_spinner=False)
def make_sample():
    """Demo data: a messy Sales table + a Products table (for Merge, SQL, Pivot, Cleaning)."""
    rng = np.random.default_rng(42)
    n = 1200
    prods = pd.DataFrame({
        "Product_ID": [f"P{i:03d}" for i in range(1, 13)],
        "Product": ["Laptop", "Phone", "Tablet", "Headphones", "Monitor", "Keyboard", "Mouse", "Printer",
                    "Camera", "Speaker", "Router", "Smartwatch"],
        "Category": ["Computers", "Mobiles", "Mobiles", "Accessories", "Computers", "Accessories", "Accessories",
                     "Office", "Electronics", "Electronics", "Network", "Mobiles"],
        "Unit_Cost": [42000, 18000, 22000, 1800, 9000, 900, 400, 7000, 25000, 2500, 1800, 6000]})
    pid = rng.choice(prods["Product_ID"], n)
    cost = prods.set_index("Product_ID")["Unit_Cost"].reindex(pid).values
    units = rng.integers(1, 6, n)
    sales = pd.DataFrame({
        "Order_ID": np.arange(10001, 10001 + n),
        "Order_Date": pd.to_datetime("2025-01-01") + pd.to_timedelta(rng.integers(0, 600, n), unit="D"),
        "Region": rng.choice(["East", "West", "North", "South"], n, p=[.35, .2, .25, .2]),
        "State": rng.choice(["Bihar", "Jharkhand", "Delhi", "Maharashtra", "Karnataka", "Tamil Nadu", "Gujarat",
                             "West Bengal"], n),
        "Customer_Type": rng.choice(["New", "Returning"], n, p=[.4, .6]),
        "Product_ID": pid,
        "Units": units,
        "Sales": (cost * rng.uniform(1.15, 1.5, n) * units).round(0),
    })
    sales["Profit"] = (sales["Sales"] - cost * units).round(0)
    sales.loc[rng.choice(n, 40, replace=False), "Region"] = None
    sales["Units"] = sales["Units"].astype(float)
    sales.loc[rng.choice(n, 30, replace=False), "Units"] = np.nan
    sales = pd.concat([sales, sales.sample(15, random_state=1)], ignore_index=True)
    return {"Sample · Sales.csv": sales, "Sample · Products.csv": prods}


# ---- login wall + demo timer (see auth_db.py) ----
user, status = adb.gate(lambda: inject_css(THEMES["Light"]))
IS_ADMIN = user["role"] == "admin"
ACCESS_PAGE, ADMIN_PAGE = "🔓 Get Full Access", "👑 Admin"
SQL_PAGE, MERGE_PAGE, ACCOUNT_PAGE = "🧮 SQL Box", "🔗 Merge & Pivot", "🔑 My Account"
NAV = (PAGES[:5] + [SQL_PAGE, MERGE_PAGE] + PAGES[5:]
       + [ACCOUNT_PAGE, ADMIN_PAGE if IS_ADMIN else ACCESS_PAGE])

with st.sidebar:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:11px;padding:6px 2px 14px;">'
        '<div style="background:#526BFF;border-radius:12px;padding:9px;font-size:22px;">📊</div>'
        '<div><div style="font-size:19px;font-weight:800;">AG Data Analyzer</div>'
        '<div style="font-size:10px;letter-spacing:1.2px;color:#AEBBD1;">DATA INTELLIGENCE</div></div></div>',
        unsafe_allow_html=True)
    st.markdown('<div class="side-label">WORKSPACE</div>', unsafe_allow_html=True)
    page = st.radio("Navigation", NAV, label_visibility="collapsed")
    st.divider()

    st.markdown('<div class="side-label">📂 DATA SOURCE</div>', unsafe_allow_html=True)
    files = st.file_uploader(
        "Upload files (select many, or a ZIP of a whole folder)",
        type=SUPPORTED, accept_multiple_files=True,
        help="CSV, TSV, TXT, XLSX, XLS, JSON, Parquet, or ZIP containing these. Every Excel sheet is loaded.")

    use_sample = st.checkbox("🧪 Load sample datasets", help="Demo data (Sales + Products) to try Merge, SQL, Pivot and Cleaning")
    datasets, errors = {}, []
    for f in files or []:
        o, e = load_file(f.name, f.getvalue())
        datasets.update(o)
        errors += e
    if use_sample:
        datasets.update(make_sample())
    datasets.update(st.session_state.get("derived", {}))

    key = None
    if datasets:
        key = st.selectbox("Active dataset", list(datasets.keys()))
    st.divider()

    st.markdown('<div class="side-label">🎨 APPEARANCE</div>', unsafe_allow_html=True)
    theme_name = st.selectbox("Theme", list(THEMES.keys()), label_visibility="collapsed")
    st.divider()
    adb.account_box(user)
    st.divider()
    st.markdown('<div style="font-size:11px;color:#AEBBD1;line-height:1.8;">VERSION 3.0<br>BUILT FOR DATA-DRIVEN TEAMS</div>',
                unsafe_allow_html=True)

T = THEMES[theme_name]
inject_css(T)

# cleaned copies persist per dataset
st.session_state.setdefault("clean", {})
df, using_clean = None, False
if key:
    if key in st.session_state["clean"]:
        df, using_clean = st.session_state["clean"][key], True
    else:
        df = datasets[key]

for e in errors:
    st.error(f"⚠️ {e}")
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))


def need_data():
    if df is None:
        st.info("👈 Upload one or more files from the left sidebar to use this section.")
        return True
    if using_clean:
        st.caption("🧹 Working on the cleaned version of this dataset (reset it from the Data Cleaning page).")
    return False


# =========================================================
# OVERVIEW
# =========================================================
if page == PAGES[0]:
    st.markdown("""
    <div class="hero">
      <div class="eyebrow">AG DATA ANALYZER · WORKSPACE</div>
      <h1>Turn your data into<br>clear business decisions.</h1>
      <p>Upload files, explore, visualize, check quality and clean your data in one professional analytics workspace.</p>
      <span class="hero-tag">Excel · CSV · JSON · Parquet · ZIP</span><span class="hero-tag">Interactive Charts</span>
      <span class="hero-tag">Data Quality</span><span class="hero-tag">Data Cleaning</span>
    </div>""", unsafe_allow_html=True)

    if df is None:
        heading("GET STARTED", "Welcome to your analytics workspace",
                "Upload data from the sidebar. Your original files are never modified.")
        cards = [("📁", "Import any data", "Multiple files at once, every Excel sheet, or a ZIP of an entire folder."),
                 ("📈", "Explore insights", "Filters, statistics, distributions, trends, correlations and group summaries."),
                 ("🛡️", "Improve quality", "Find missing values, duplicates and outliers, clean, then export CSV or Excel.")]
        for col, (i, h, p) in zip(st.columns(3), cards):
            col.markdown(f'<div class="feature-card"><div class="feature-icon">{i}</div><h3>{h}</h3><p>{p}</p></div>',
                         unsafe_allow_html=True)
    else:
        need_data()
        heading("LIVE DATASET", "Dataset at a glance", f"Analyzing: {key}  ·  {len(datasets)} dataset(s) loaded")
        a, b, c, d, e = st.columns(5)
        a.metric("Records", f"{len(df):,}")
        b.metric("Columns", f"{df.shape[1]:,}")
        c.metric("Missing values", f"{int(df.isna().sum().sum()):,}")
        d.metric("Duplicate rows", f"{int(df.duplicated().sum()):,}")
        e.metric("Memory", f"{df.memory_usage(deep=True).sum() / 1e6:.2f} MB")

        st.markdown("#### 💡 Auto insights")
        tips = []
        miss = df.isna().mean().sort_values(ascending=False)
        if miss.iloc[0] > 0:
            tips.append(f"Column <b>{miss.index[0]}</b> has the most missing data ({miss.iloc[0]*100:.1f}%).")
        const = [c for c in df.columns if df[c].nunique(dropna=True) <= 1]
        if const:
            tips.append(f"Constant columns (no information): <b>{', '.join(map(str, const[:5]))}</b>.")
        ids = [c for c in df.columns if len(df) > 20 and df[c].nunique() == len(df)]
        if ids:
            tips.append(f"Likely ID / unique-key columns: <b>{', '.join(map(str, ids[:5]))}</b>.")
        tips.append(f"{len(num_cols(df))} numeric and {len(cat_cols(df))} text/category columns detected.")
        for t_ in tips:
            st.markdown(f'<div class="insight">{t_}</div>', unsafe_allow_html=True)

        st.markdown("#### Preview")
        st.dataframe(df.head(10), width="stretch", hide_index=True)

# =========================================================
# DATA EXPLORER
# =========================================================
elif page == PAGES[1]:
    heading("WORKSPACE / DATA", "Data Explorer", "Search, filter and profile your records.")
    if not need_data():
        t1, t2, t3 = st.tabs(["Data preview", "Column profile", "Statistics"])
        with t1:
            c1, c2 = st.columns([2, 3])
            q = c1.text_input("🔍 Search any text", placeholder="type to search all columns")
            cols = c2.multiselect("Columns to show", df.columns.tolist(), default=df.columns.tolist())
            view = df[cols] if cols else df
            if q:
                mask = view.astype(str).apply(lambda s: s.str.contains(q, case=False, na=False)).any(axis=1)
                view = view[mask]
            st.dataframe(view, width="stretch", hide_index=True)
            st.caption(f"{len(view):,} of {len(df):,} rows · {view.shape[1]} columns")
        with t2:
            prof = pd.DataFrame({"Column": df.columns.astype(str), "Type": df.dtypes.astype(str).values,
                                 "Non-null": df.notna().sum().values, "Missing": df.isna().sum().values,
                                 "Unique": df.nunique(dropna=True).values,
                                 "Sample": [str(df[c].dropna().iloc[0]) if df[c].notna().any() else "" for c in df.columns]})
            st.dataframe(prof, width="stretch", hide_index=True)
        with t3:
            st.dataframe(df.describe(include="all").T, width="stretch")

# =========================================================
# ANALYTICS
# =========================================================
elif page == PAGES[2]:
    heading("WORKSPACE / VISUALS", "Analytics", "Build quick visual summaries.")
    if not need_data():
        nums, cats = num_cols(df), cat_cols(df)
        tabs = st.tabs(["Distribution", "Categories", "Relationship", "Trend", "Correlation", "Group summary"])

        with tabs[0]:
            if nums:
                l, r = st.columns(2)
                col = l.selectbox("Numeric column", nums, key="d1")
                kind = r.selectbox("Chart", ["Histogram", "Box plot", "Violin"])
                if kind == "Histogram":
                    fig = px.histogram(df, x=col, title=f"Distribution of {col}")
                elif kind == "Box plot":
                    fig = px.box(df, y=col, title=f"Spread and outliers: {col}")
                else:
                    fig = px.violin(df, y=col, box=True, title=f"Violin: {col}")
                show_fig(fig, T)
            else:
                st.warning("No numeric columns found.")

        with tabs[1]:
            if cats:
                l, r, s = st.columns(3)
                col = l.selectbox("Category column", cats)
                kind = r.selectbox("Chart", ["Bar", "Pie"])
                n = s.slider("Top categories", 5, 30, 10)
                cnt = df[col].fillna("Missing").astype(str).value_counts().head(n).rename_axis(col).reset_index(name="Records")
                fig = px.bar(cnt, x=col, y="Records", title=f"Records by {col}") if kind == "Bar" \
                    else px.pie(cnt, names=col, values="Records", hole=.45, title=f"Share by {col}")
                show_fig(fig, T)
            else:
                st.warning("No text/category columns found.")

        with tabs[2]:
            if len(nums) >= 2:
                a, b, c = st.columns(3)
                x = a.selectbox("X axis", nums, key="sx")
                y = b.selectbox("Y axis", nums, index=1, key="sy")
                color = c.selectbox("Color by", ["None"] + cats)
                data = df.sample(min(len(df), 5000), random_state=1) if len(df) > 5000 else df
                show_fig(px.scatter(data, x=x, y=y, color=None if color == "None" else color,
                                    title=f"{y} vs {x}"), T)
                if len(df) > 5000:
                    st.caption("Showing a random sample of 5,000 rows for speed.")
            else:
                st.warning("Need at least two numeric columns.")

        with tabs[3]:
            if nums:
                a, b, c = st.columns(3)
                x = a.selectbox("X (time / order)", df.columns.tolist(), key="tx")
                y = b.selectbox("Y (numeric)", nums, key="ty")
                agg = c.selectbox("Aggregate", ["sum", "mean", "median", "count", "min", "max"], key="ta")
                xs = df[x]
                if xs.dtype == object:
                    conv = pd.to_datetime(xs, errors="coerce")
                    if conv.notna().mean() > .8:
                        xs = conv
                tr = pd.DataFrame({x: xs, y: df[y]}).dropna().groupby(x)[y].agg(agg).reset_index().sort_values(x)
                show_fig(px.line(tr, x=x, y=y, markers=len(tr) < 60, title=f"{agg.title()} of {y} by {x}"), T)
            else:
                st.warning("No numeric columns found.")

        with tabs[4]:
            if len(nums) >= 2:
                corr = df[nums].corr(numeric_only=True)
                show_fig(px.imshow(corr, text_auto=".2f", aspect="auto", color_continuous_scale="RdBu_r",
                                   zmin=-1, zmax=1, title="Correlation matrix"), T)
            else:
                st.warning("Need at least two numeric columns.")

        with tabs[5]:
            if nums and cats:
                a, b, c, d = st.columns(4)
                g = a.selectbox("Group by", cats)
                v = b.selectbox("Value", nums, key="gv")
                ag = c.selectbox("Aggregate", ["sum", "mean", "median", "count", "min", "max"], key="ga")
                n = d.slider("Top N", 5, 30, 10, key="gn")
                res = df.groupby(g)[v].agg(ag).sort_values(ascending=False).head(n).reset_index()
                st.dataframe(res, width="stretch", hide_index=True)
                show_fig(px.bar(res, x=g, y=v, title=f"{ag.title()} of {v} by {g}"), T)
            else:
                st.warning("Need at least one numeric and one category column.")

# =========================================================
# DATA QUALITY
# =========================================================
elif page == PAGES[3]:
    heading("WORKSPACE / VALIDATION", "Data Quality", "Missing values, duplicates and outliers.")
    if not need_data():
        miss, dup = int(df.isna().sum().sum()), int(df.duplicated().sum())
        cells = df.shape[0] * df.shape[1]
        comp = 100.0 if cells == 0 else (1 - miss / cells) * 100
        score = max(0.0, comp - (dup / max(len(df), 1)) * 100)
        a, b, c, d = st.columns(4)
        a.metric("Missing values", f"{miss:,}")
        b.metric("Duplicate rows", f"{dup:,}")
        c.metric("Completeness", f"{comp:.1f}%")
        d.metric("Quality score", f"{score:.0f}/100")

        q = pd.DataFrame({"Column": df.columns.astype(str), "Missing": df.isna().sum().values,
                          "Missing %": (df.isna().mean().values * 100).round(2),
                          "Unique": df.nunique(dropna=True).values})
        t1, t2, t3 = st.tabs(["Missing values", "Outliers (IQR)", "Duplicate rows"])
        with t1:
            st.dataframe(q, width="stretch", hide_index=True)
            mc = q[q["Missing"] > 0]
            if mc.empty:
                st.success("No missing values found.")
            else:
                show_fig(px.bar(mc, x="Column", y="Missing", title="Missing values by column"), T)
        with t2:
            rows = []
            for col in num_cols(df):
                s = df[col].dropna()
                q1, q3 = s.quantile(.25), s.quantile(.75)
                iqr = q3 - q1
                n_out = int(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum())
                rows.append({"Column": col, "Outliers": n_out, "Outlier %": round(n_out / max(len(s), 1) * 100, 2),
                             "Lower fence": q1 - 1.5 * iqr, "Upper fence": q3 + 1.5 * iqr})
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True) if rows else st.info("No numeric columns.")
        with t3:
            dd = df[df.duplicated(keep=False)]
            st.dataframe(dd, width="stretch", hide_index=True) if len(dd) else st.success("No duplicate rows.")

# =========================================================
# DATA CLEANING
# =========================================================
elif page == PAGES[4]:
    heading("WORKSPACE / TRANSFORM", "Data Cleaning Studio",
            "Choose steps, preview, then apply. Your uploaded files are never changed.")
    if df is None:
        need_data()
    else:
        src = datasets[key]
        base = src if st.checkbox("Start again from original data", value=not using_clean) else df
        c1, c2 = st.columns(2)
        with c1:
            do_dup = st.checkbox("Remove duplicate rows")
            do_strip = st.checkbox("Trim spaces in text columns")
            do_names = st.checkbox("Standardize column names (lower_snake_case)")
            drop_empty = st.checkbox("Drop completely empty rows")
            drop_any = st.checkbox("Drop rows with any missing value")
        with c2:
            num_fill = st.selectbox("Fill missing numeric values", ["Leave as is", "Median", "Mean", "Zero"])
            txt_fill = st.selectbox("Fill missing text values", ["Leave as is", "Most frequent", "Unknown"])
            drop_cols = st.multiselect("Drop columns", base.columns.tolist())
            dt_cols = st.multiselect("Convert to date", base.columns.tolist())

        out = base.copy()
        if drop_cols:
            out = out.drop(columns=drop_cols)
        if do_names:
            out.columns = (out.columns.astype(str).str.strip().str.lower()
                           .str.replace(r"[^0-9a-z]+", "_", regex=True).str.strip("_"))
        if do_strip:
            for col in cat_cols(out):
                out[col] = out[col].map(lambda v: v.strip() if isinstance(v, str) else v)
        for col in [c for c in dt_cols if c in out.columns]:
            out[col] = pd.to_datetime(out[col], errors="coerce")
        if drop_empty:
            out = out.dropna(how="all")
        if drop_any:
            out = out.dropna()
        if do_dup:
            out = out.drop_duplicates()
        for col in out.columns:
            if pd.api.types.is_numeric_dtype(out[col]) and num_fill != "Leave as is" and out[col].notna().any():
                val = {"Median": out[col].median(), "Mean": out[col].mean(), "Zero": 0}[num_fill]
                out[col] = out[col].fillna(val)
            elif out[col].dtype == object and txt_fill != "Leave as is":
                m = out[col].mode(dropna=True)
                out[col] = out[col].fillna(m.iloc[0] if txt_fill == "Most frequent" and not m.empty else "Unknown")

        a, b, c, d = st.columns(4)
        a.metric("Original rows", f"{len(src):,}")
        b.metric("Cleaned rows", f"{len(out):,}")
        c.metric("Rows removed", f"{len(base) - len(out):,}")
        d.metric("Missing now", f"{int(out.isna().sum().sum()):,}")
        st.markdown("#### Preview")
        st.dataframe(out.head(25), width="stretch", hide_index=True)

        stem = key.replace(" › ", "_").rsplit(".", 1)[0]
        d1, d2 = st.columns(2)
        d1.download_button("⬇️ Download clean CSV", to_csv(out), f"{stem}_clean.csv", "text/csv", width="stretch")
        d2.download_button("⬇️ Download clean Excel", to_excel(out), f"{stem}_clean.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")

        x, y = st.columns(2)
        if x.button("✅ Apply to workspace", width="stretch"):
            st.session_state["clean"][key] = out
            st.rerun()
        if using_clean and y.button("↩️ Reset to original", width="stretch"):
            st.session_state["clean"].pop(key, None)
            st.rerun()

# =========================================================
# EXPORT
# =========================================================
elif page == PAGES[5]:
    heading("WORKSPACE / OUTPUT", "Export", "Download the active dataset (cleaned version if you applied cleaning).")
    if not need_data():
        stem = key.replace(" › ", "_").rsplit(".", 1)[0]
        a, b = st.columns(2)
        a.download_button("⬇️ Download CSV", to_csv(df), f"{stem}_cleaned.csv", "text/csv", width="stretch")
        b.download_button("⬇️ Download Excel", to_excel(df), f"{stem}_cleaned.xlsx",
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
        st.dataframe(df.head(25), width="stretch", hide_index=True)

elif page == SQL_PAGE:
    heading("WORKSPACE / SQL", "SQL Box", "Run SQL (DuckDB engine) on any uploaded file, sheet or sample table.")
    if not datasets:
        st.info("👈 Upload files or tick “Load sample datasets” in the sidebar.")
    else:
        try:
            import duckdb
        except ImportError:
            duckdb = None
            st.error("SQL engine missing. Run `pip install duckdb` and add `duckdb` to requirements.txt.")
        if duckdb:
            tables = {}
            for k, v in datasets.items():
                base = re.sub(r"\.(csv|tsv|txt|xlsx|xlsm|xls|json|parquet)", "", k, flags=re.I)
                nm_ = re.sub(r"\W+", "_", base).strip("_").lower() or "table"
                if nm_[0].isdigit():
                    nm_ = "t_" + nm_
                while nm_ in tables:
                    nm_ += "_2"
                t_df = (df if k == key else v).copy()
                t_df.columns = t_df.columns.astype(str)
                tables[nm_] = t_df
            with st.expander("📚 Tables you can query", expanded=True):
                st.dataframe(pd.DataFrame({"Table name": list(tables), "Rows": [len(t) for t in tables.values()],
                                           "Columns": [", ".join(t.columns) for t in tables.values()]}),
                             width="stretch", hide_index=True)
            sql = st.text_area("SQL query (SELECT / WITH only)", f"SELECT * FROM {next(iter(tables))} LIMIT 100", height=170)
            if st.button("▶ Run query"):
                body = sql.strip().rstrip(";")
                if not re.match(r"(?is)^\s*(select|with)\b", body):
                    st.error("Only SELECT queries are allowed.")
                else:
                    try:
                        con = duckdb.connect(":memory:")
                        for tn, td in tables.items():
                            con.register(tn, td)
                        con.execute("SET enable_external_access=false")
                        con.execute("SET lock_configuration=true")
                        st.session_state["sql_res"] = con.execute(f"SELECT * FROM ({body}) AS _q LIMIT 50000").df()
                        con.close()
                    except Exception as ex:
                        st.error(f"SQL error: {ex}")
            res = st.session_state.get("sql_res")
            if res is not None:
                st.success(f"{len(res):,} rows × {res.shape[1]} columns")
                st.dataframe(res, width="stretch", hide_index=True)
                c1, c2, c3 = st.columns([2, 1, 1])
                nm = c1.text_input("Save result as dataset named", "sql_result")
                if c2.button("➕ Save as dataset") and nm.strip():
                    st.session_state.setdefault("derived", {})[nm.strip()] = res
                    st.session_state["flash"] = f"Saved “{nm.strip()}”. Select it in the sidebar (Active dataset)."
                    st.rerun()
                c3.download_button("⬇️ CSV", to_csv(res), "sql_result.csv", "text/csv", width="stretch")

elif page == MERGE_PAGE:
    heading("WORKSPACE / TRANSFORM", "Merge & Pivot", "Join tables together and summarize with pivot tables.")
    if not datasets:
        st.info("👈 Upload files or tick “Load sample datasets” in the sidebar.")
    else:
        mt, pt = st.tabs(["🔗 Merge / Join", "📊 Pivot table"])
        with mt:
            if len(datasets) < 2:
                st.info("Load at least two tables to merge them (tick “Load sample datasets” to try).")
            else:
                names = list(datasets)
                c1, c2 = st.columns(2)
                ln = c1.selectbox("Left table", names, key="mj_l")
                rn = c2.selectbox("Right table", names, index=1, key="mj_r")
                L, R = datasets[ln], datasets[rn]
                k1, k2 = st.columns(2)
                lk = k1.multiselect("Left key column(s)", L.columns.tolist(), key="mj_lk")
                rk = k2.multiselect("Right key column(s)", R.columns.tolist(), key="mj_rk")
                how = st.selectbox("Join type", ["left", "inner", "right", "outer"])
                if not lk or len(lk) != len(rk):
                    st.info("Pick the same number of key columns on both sides (e.g. Product_ID and Product_ID).")
                else:
                    L2, R2 = L.copy(), R.copy()
                    for a_, b_ in zip(lk, rk):
                        if L2[a_].dtype != R2[b_].dtype:
                            L2[a_], R2[b_] = L2[a_].astype(str), R2[b_].astype(str)
                    m = L2.merge(R2, left_on=lk, right_on=rk, how=how, suffixes=("", "_right"), indicator=True)
                    a, b, c, d = st.columns(4)
                    a.metric("Result rows", f"{len(m):,}")
                    b.metric("Matched", f"{int((m['_merge'] == 'both').sum()):,}")
                    c.metric("Only in left", f"{int((m['_merge'] == 'left_only').sum()):,}")
                    d.metric("Only in right", f"{int((m['_merge'] == 'right_only').sum()):,}")
                    m = m.drop(columns="_merge")
                    st.dataframe(m.head(200), width="stretch", hide_index=True)
                    x1, x2 = st.columns([3, 1])
                    nm = x1.text_input("Save merged table as", "merged_data")
                    if x2.button("➕ Save as dataset", key="mj_save") and nm.strip():
                        st.session_state.setdefault("derived", {})[nm.strip()] = m
                        st.session_state["flash"] = f"Saved “{nm.strip()}”. Select it in the sidebar (Active dataset)."
                        st.rerun()
        with pt:
            if not need_data():
                allc = df.columns.tolist()
                nums = num_cols(df)
                a, b = st.columns(2)
                rws = a.multiselect("Rows", allc, key="pv_r")
                cls = b.multiselect("Columns (optional)", [c_ for c_ in allc if c_ not in rws], key="pv_c")
                c, d, e = st.columns(3)
                val = c.selectbox("Values", nums or allc, key="pv_v")
                agg = d.selectbox("Aggregate", ["sum", "mean", "count", "median", "min", "max"], key="pv_a")
                tot = e.checkbox("Show totals", value=True)
                if not rws:
                    st.info("Pick at least one field for Rows.")
                else:
                    try:
                        pv = pd.pivot_table(df, index=rws, columns=cls or None, values=val, aggfunc=agg,
                                            margins=tot, fill_value=0)
                        if isinstance(pv.columns, pd.MultiIndex):
                            pv.columns = [" | ".join(map(str, c_)) for c_ in pv.columns]
                        pv = pv.reset_index()
                        st.dataframe(pv, width="stretch", hide_index=True)
                        y1, y2, y3 = st.columns(3)
                        y1.download_button("⬇️ CSV", to_csv(pv), "pivot.csv", "text/csv", width="stretch")
                        y2.download_button("⬇️ Excel", to_excel(pv), "pivot.xlsx",
                                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                           width="stretch")
                        if y3.button("➕ Save as dataset", key="pv_save", width="stretch"):
                            st.session_state.setdefault("derived", {})["pivot_result"] = pv
                            st.session_state["flash"] = "Saved “pivot_result”. Select it in the sidebar (Active dataset)."
                            st.rerun()
                    except Exception as ex:
                        st.error(f"Could not build the pivot: {ex}")

elif page == ACCOUNT_PAGE:
    heading("WORKSPACE / ACCOUNT", "My Account", "Your details and password.")
    adb.account_page(user)

elif page == PAGES[6]:
    heading("WORKSPACE / SUPPORT", "Feedback", "Help me improve AG Data Analyzer.")
    adb.feedback_page(user)

elif page == ACCESS_PAGE:
    heading("WORKSPACE / ACCOUNT", "Get Full Access", "Continue without the demo time limit.")
    adb.access_request_ui(user)

elif page == ADMIN_PAGE and IS_ADMIN:
    heading("WORKSPACE / ADMIN", "Admin Panel", "Users, access, requests, feedback and settings.")
    adb.admin_panel()

st.markdown('<div class="footer"><strong>AG DATA ANALYZER</strong> · PROFESSIONAL DATA ANALYTICS WORKSPACE<br>'
            'Built with Python · Streamlit · Pandas · Plotly</div>', unsafe_allow_html=True)
