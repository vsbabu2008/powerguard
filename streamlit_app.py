import streamlit as st
import mysql.connector
import pandas as pd
import random
from datetime import datetime
import plotly.express as px

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(
    page_title="Smart Electricity Theft Detection",
    layout="wide"
)

# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------
def get_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"],
        port=st.secrets["mysql"]["port"]
    )

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------
@st.cache_data(show_spinner=False)
def load_data():
    conn = get_connection()
    query = """
    SELECT
        c.consumer_id,
        c.name,
        c.area,
        m.meter_id,
        cs.reading_date,
        cs.units AS units_consumed
    FROM CONSUMER c
    JOIN METER m ON c.consumer_id = m.consumer_id
    LEFT JOIN CONSUMPTION cs ON m.meter_id = cs.meter_id
    ORDER BY cs.reading_date DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# --------------------------------------------------
# INSERT SIMULATED READINGS
# --------------------------------------------------
def insert_readings(count=1):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT meter_id FROM METER")
    meters = cur.fetchall()

    if not meters:
        st.warning("⚠️ No meters found. Please add meter records first.")
        conn.close()
        return

    for _ in range(count):
        meter_id = random.choice(meters)[0]
        units = round(random.uniform(1, 25), 2)

        cur.execute(
            """
            INSERT INTO CONSUMPTION (meter_id, reading_date, units)
            VALUES (%s, %s, %s)
            """,
            (meter_id, datetime.now(), units)
        )

    conn.commit()
    conn.close()
    st.cache_data.clear()
    st.success(f"✅ {count} reading(s) simulated successfully")

# --------------------------------------------------
# UI
# --------------------------------------------------
st.title("⚡ Smart Electricity Theft Detection Dashboard")

st.subheader("🔁 Real-Time Reading Simulation")

c1, c2 = st.columns(2)
with c1:
    if st.button("➕ Simulate 1 Reading"):
        insert_readings(1)
with c2:
    if st.button("➕➕ Simulate 10 Readings"):
        insert_readings(10)

df = load_data()

if df.empty or df["reading_date"].isna().all():
    st.info("No consumption data available yet.")
    st.stop()

# --------------------------------------------------
# PREPROCESSING
# --------------------------------------------------
df = df.dropna(subset=["reading_date"])
df["reading_date"] = pd.to_datetime(df["reading_date"])
df["hour"] = df["reading_date"].dt.hour

# --------------------------------------------------
# METRICS
# --------------------------------------------------
m1, m2, m3 = st.columns(3)
m1.metric("Total Readings", len(df))
m2.metric("Total Units", round(df["units_consumed"].sum(), 2))
m3.metric("Avg Units / Reading", round(df["units_consumed"].mean(), 2))

# ==================================================
# 📈 1. SMOOTHED CONSUMPTION TREND
# ==================================================
st.subheader("📈 Smoothed Consumption Trend")

trend = (
    df.sort_values("reading_date")
      .set_index("reading_date")
      .rolling("3H")["units_consumed"]
      .mean()
      .reset_index()
)

fig_trend = px.line(
    trend,
    x="reading_date",
    y="units_consumed",
    title="Smoothed Electricity Consumption (Rolling Average)"
)

st.plotly_chart(fig_trend, use_container_width=True)

# ==================================================
# 🔥 2. CONSUMPTION HEATMAP (AREA × HOUR)
# ==================================================
st.subheader("🔥 Consumption Heatmap (Area vs Hour)")

heatmap_data = (
    df.groupby(["area", "hour"])["units_consumed"]
      .sum()
      .reset_index()
)

fig_heatmap = px.density_heatmap(
    heatmap_data,
    x="hour",
    y="area",
    z="units_consumed",
    color_continuous_scale="YlOrRd",
    title="Electricity Usage Heatmap (Area vs Hour)"
)

st.plotly_chart(fig_heatmap, use_container_width=True)

# ==================================================
# ⏰ 3. PEAK HOUR USAGE
# ==================================================
st.subheader("⏰ Peak Hour Usage")

peak = (
    df.groupby("hour")["units_consumed"]
      .sum()
      .reset_index()
)

fig_peak = px.bar(
    peak,
    x="hour",
    y="units_consumed",
    color="units_consumed",
    title="Peak Hour Electricity Usage",
    labels={"hour": "Hour of Day"}
)

st.plotly_chart(fig_peak, use_container_width=True)

# ==================================================
# 📄 LATEST RECORDS
# ==================================================
st.subheader("📄 Latest Records")
st.dataframe(df.head(20), use_container_width=True)
