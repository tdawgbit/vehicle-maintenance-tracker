import streamlit as st
import psycopg2

def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])

st.set_page_config(page_title="Vehicle Maintenance Tracker", layout="wide")
st.title("🔧 Vehicle Maintenance Tracker")

# --- Load summary metrics ---
def load_metrics():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM vehicles;")
    total_vehicles = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM maintenance_logs;")
    total_logs = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(total_cost), 0) FROM maintenance_logs;")
    total_spent = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM service_types;")
    total_service_types = cur.fetchone()[0]

    cur.close()
    conn.close()
    return total_vehicles, total_logs, total_spent, total_service_types

# --- Load recent logs ---
def load_recent_logs():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            v.year, v.make, v.model, v.nickname,
            ml.log_date,
            ml.mileage_at_service,
            ml.shop_name,
            ml.total_cost,
            STRING_AGG(st.name, ', ' ORDER BY st.name) as services
        FROM maintenance_logs ml
        JOIN vehicles v ON ml.vehicle_id = v.id
        LEFT JOIN log_services ls ON ml.id = ls.log_id
        LEFT JOIN service_types st ON ls.service_type_id = st.id
        GROUP BY ml.id, v.year, v.make, v.model, v.nickname
        ORDER BY ml.log_date DESC
        LIMIT 10;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# --- Load last service per vehicle ---
def load_last_serviced():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT ON (v.id)
            v.id, v.year, v.make, v.model, v.nickname,
            ml.log_date,
            ml.mileage_at_service,
            STRING_AGG(st.name, ', ' ORDER BY st.name) as services
        FROM vehicles v
        LEFT JOIN maintenance_logs ml ON v.id = ml.vehicle_id
        LEFT JOIN log_services ls ON ml.id = ls.log_id
        LEFT JOIN service_types st ON ls.service_type_id = st.id
        GROUP BY v.id, v.year, v.make, v.model, v.nickname, ml.id, ml.log_date, ml.mileage_at_service
        ORDER BY v.id, ml.log_date DESC NULLS LAST;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# --- Metrics Row ---
total_vehicles, total_logs, total_spent, total_service_types = load_metrics()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Vehicles", total_vehicles)
col2.metric("Maintenance Logs", total_logs)
col3.metric("Total Spent", f"${total_spent:,.2f}")
col4.metric("Service Types", total_service_types)

st.divider()

# --- Per Vehicle Last Serviced ---
st.subheader("Vehicle Status")
last_serviced = load_last_serviced()

if not last_serviced:
    st.info("No vehicles added yet.")
else:
    cols = st.columns(min(len(last_serviced), 3))
    for i, row in enumerate(last_serviced):
        vid, yr, mk, md, nick, log_date, mileage, services = row
        label = f"{yr} {mk} {md}" + (f'\n"{nick}"' if nick else "")
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**{yr} {mk} {md}**" + (f' — *{nick}*' if nick else ""))
                if log_date:
                    st.write(f"Last serviced: {log_date.strftime('%b %d, %Y')}")
                    st.write(f"Mileage: {mileage:,} mi" if mileage else "Mileage: —")
                    st.caption(services or "—")
                else:
                    st.write("No service logged yet.")

st.divider()

# --- Recent Logs Table ---
st.subheader("Recent Maintenance Logs")
recent_logs = load_recent_logs()

if not recent_logs:
    st.info("No maintenance logs yet.")
else:
    for log in recent_logs:
        yr, mk, md, nick, log_date, mileage, shop, cost, services = log
        vehicle_label = f"{yr} {mk} {md}" + (f' — "{nick}"' if nick else "")
        cost_str = f"${cost:,.2f}" if cost else "—"
        mileage_str = f"{mileage:,} mi" if mileage else "—"
        shop_str = shop or "—"
        st.markdown(f"**{vehicle_label}** | {log_date.strftime('%b %d, %Y')} | {mileage_str} | {shop_str} | {cost_str}")
        st.caption(f"Services: {services or '—'}")
    st.divider()