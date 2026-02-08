import streamlit as st
import sqlite3
import pandas as pd
import random
import datetime
import time
import plotly.express as px
import plotly.io as pio

pio.templates.default = "plotly_dark"

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
st.set_page_config(page_title="Smart Electricity Theft Detection", layout="wide")
DB = "electricity_theft.db"
THRESHOLD = 250

# --------------------------------------------------
# DATABASE
# --------------------------------------------------
conn = sqlite3.connect(DB, check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS CONSUMER(
    consumer_id INTEGER PRIMARY KEY,
    name TEXT,
    area TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS METER(
    meter_id INTEGER PRIMARY KEY,
    consumer_id INTEGER,
    meter_type TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS CONSUMPTION(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meter_id INTEGER,
    units REAL,
    reading_date TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS ALERT(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meter_id INTEGER,
    units REAL,
    alert_type TEXT,
    alert_date TEXT
)
""")
conn.commit()

# --------------------------------------------------
# INITIAL DATA
# --------------------------------------------------
if cur.execute("SELECT COUNT(*) FROM CONSUMER").fetchone()[0] == 0:
    cur.executemany(
        "INSERT INTO CONSUMER VALUES (?,?,?)",
        [(1,"Ravi","Chennai"),
         (2,"Anitha","Madurai"),
         (3,"Karthik","Coimbatore")]
    )
    cur.executemany(
        "INSERT INTO METER VALUES (?,?,?)",
        [(101,1,"Smart"),
         (102,2,"Smart"),
         (103,3,"Smart")]
    )
    conn.commit()

# --------------------------------------------------
# REAL-TIME SIMULATION
# --------------------------------------------------
def simulate():
    meter = random.choice([101,102,103])
    units = random.randint(40,330)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur.execute(
        "INSERT INTO CONSUMPTION(meter_id, units, reading_date) VALUES (?,?,?)",
        (meter, units, ts)
    )

    if units > THRESHOLD:
        cur.execute(
            "INSERT INTO ALERT(meter_id, units, alert_type, alert_date) VALUES (?,?,?,?)",
            (meter, units, "POSSIBLE THEFT", ts)
        )
    conn.commit()

# --------------------------------------------------
# HEADER
# --------------------------------------------------
st.markdown("""
<h1 style="color:#00E5FF;">⚡ Smart Electricity Theft Detection</h1>
<p style="color:#AAAAAA;">
Real-time monitoring • Interactive analytics • Dark dashboard
</p>
<hr>
""", unsafe_allow_html=True)

# --------------------------------------------------
# CONTROLS
# --------------------------------------------------
c1, c2 = st.columns(2)
if c1.button("▶ Simulate 10 Readings"):
    for _ in range(10):
        simulate()
        time.sleep(0.4)
    st.success("Simulation completed")

if c2.button("➕ Add One Reading"):
    simulate()
    st.success("Reading added")

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------
base_df = pd.read_sql("""
SELECT c.area, m.meter_id, cs.units, cs.reading_date
FROM CONSUMER c
JOIN METER m ON c.consumer_id = m.consumer_id
JOIN CONSUMPTION cs ON m.meter_id = cs.meter_id
""", conn)

alert_df = pd.read_sql("SELECT * FROM ALERT", conn)

if base_df.empty:
    st.warning("No data yet. Start simulation.")
    st.stop()

base_df["reading_date"] = pd.to_datetime(base_df["reading_date"])

# --------------------------------------------------
# SIDEBAR FILTERS
# --------------------------------------------------
st.sidebar.header("🔍 Filters")

areas = ["All"] + sorted(base_df["area"].unique().tolist())
meters = ["All"] + sorted(base_df["meter_id"].astype(str).unique().tolist())

sel_area = st.sidebar.selectbox("Area", areas)
sel_meter = st.sidebar.selectbox("Meter ID", meters)

min_d = base_df["reading_date"].min().date()
max_d = base_df["reading_date"].max().date()

date_range = st.sidebar.date_input(
    "Date Range",
    value=(min_d, max_d),
    min_value=min_d,
    max_value=max_d
)

filtered = base_df.copy()

if sel_area != "All":
    filtered = filtered[filtered["area"] == sel_area]

if sel_meter != "All":
    filtered = filtered[filtered["meter_id"].astype(str) == sel_meter]

if len(date_range) == 2:
    s, e = date_range
    filtered = filtered[
        (filtered["reading_date"].dt.date >= s) &
        (filtered["reading_date"].dt.date <= e)
    ]

# --------------------------------------------------
# METRICS
# --------------------------------------------------
m1, m2, m3 = st.columns(3)
m1.metric("Total Readings", len(filtered))
m2.metric("Theft Alerts", len(alert_df))
m3.metric("Normal Usage", max(len(filtered)-len(alert_df),0))

# --------------------------------------------------
# CHARTS
# --------------------------------------------------
st.header("📊 Analytics")

# Area-wise
area_df = filtered.groupby("area", as_index=False)["units"].sum()
if not area_df.empty:
    st.plotly_chart(
        px.bar(area_df, x="area", y="units", color="area",
               title="Area-wise Electricity Consumption"),
        use_container_width=True
    )

# Trend
trend_df = filtered.groupby("reading_date", as_index=False)["units"].sum()
if not trend_df.empty:
    st.plotly_chart(
        px.line(trend_df, x="reading_date", y="units",
                markers=True, title="Consumption Trend"),
        use_container_width=True
    )

# Rolling Average
if len(trend_df) >= 3:
    trend_df["rolling_avg"] = trend_df["units"].rolling(3).mean()
    st.plotly_chart(
        px.line(trend_df, x="reading_date",
                y=["units","rolling_avg"],
                title="Smoothed Consumption Trend"),
        use_container_width=True
    )

# Heatmap (Area x Hour)
heat_df = filtered.copy()
heat_df["hour"] = heat_df["reading_date"].dt.hour.astype(str)

if heat_df.shape[0] >= 2:
    st.plotly_chart(
        px.density_heatmap(
            heat_df, x="hour", y="area", z="units",
            color_continuous_scale="YlOrRd",
            title="Consumption Heatmap (Area vs Hour)"
        ),
        use_container_width=True
    )

# Peak Hour
hour_df = heat_df.groupby("hour", as_index=False)["units"].sum()
if not hour_df.empty:
    st.plotly_chart(
        px.bar(hour_df, x="hour", y="units",
               title="Peak Hour Usage"),
        use_container_width=True
    )

# Theft Trend
if not alert_df.empty:
    alert_df["alert_date"] = pd.to_datetime(alert_df["alert_date"])
    tdf = alert_df.groupby(alert_df["alert_date"].dt.date,
                           as_index=False).size()
    st.plotly_chart(
        px.line(tdf, x="alert_date", y="size",
                markers=True, title="Theft Alert Trend"),
        use_container_width=True
    )

# --------------------------------------------------
# DATA + EXPORT
# --------------------------------------------------
st.header("📄 Data")

st.dataframe(filtered.tail(20), use_container_width=True)

csv = filtered.to_csv(index=False).encode("utf-8")
st.download_button("⬇ Download Filtered Data (CSV)",
                   csv, "filtered_consumption.csv")

if not alert_df.empty:
    alert_df.to_excel("alerts.xlsx", index=False)
    with open("alerts.xlsx","rb") as f:
        st.download_button("⬇ Download Alerts (Excel)",
                           f, "alerts.xlsx")
