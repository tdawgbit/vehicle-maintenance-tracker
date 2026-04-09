import streamlit as st
import psycopg2
from datetime import date

def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])

st.set_page_config(page_title="Log Maintenance", layout="wide")
st.title("Log Maintenance")

# --- Load vehicles ---
def load_vehicles():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, year, make, model, nickname
        FROM vehicles
        ORDER BY year DESC, make;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# --- Load service types ---
def load_service_types():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM service_types ORDER BY name;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

vehicles = load_vehicles()
service_types = load_service_types()

if not vehicles:
    st.warning("No vehicles found. Please add a vehicle first.")
    st.stop()

if not service_types:
    st.warning("No service types found. Please add service types first.")
    st.stop()

# --- Build dropdowns ---
vehicle_options = {
    f"{yr} {mk} {md}" + (f' — "{nick}"' if nick else ""): vid
    for vid, yr, mk, md, nick in vehicles
}
service_options = {name: sid for sid, name in service_types}

# --- Log Maintenance Form ---
st.subheader("New Maintenance Log")
with st.form("log_maintenance"):
    col1, col2 = st.columns(2)
    with col1:
        vehicle_label = st.selectbox("Vehicle *", options=list(vehicle_options.keys()))
        log_date = st.date_input("Service Date *", value=date.today())
        mileage = st.number_input("Mileage at Service", min_value=0, step=1, value=0)
    with col2:
        shop_name = st.text_input("Shop / Location")
        total_cost = st.number_input("Total Cost ($)", min_value=0.0, step=0.01, value=0.0)

    notes = st.text_area("Notes")

    st.markdown("**Services Performed *** — select all that apply")
    selected_services = st.multiselect(
        "Services",
        options=list(service_options.keys())
    )

    # Per-service cost and notes
    service_details = {}
    if selected_services:
        st.markdown("**Optional: per-service details**")
        for svc in selected_services:
            with st.expander(svc):
                scol1, scol2 = st.columns(2)
                with scol1:
                    svc_cost = st.number_input(f"Cost for {svc} ($)", min_value=0.0, step=0.01, value=0.0, key=f"cost_{svc}")
                with scol2:
                    svc_notes = st.text_input(f"Notes for {svc}", key=f"notes_{svc}")
                service_details[svc] = {"cost": svc_cost, "notes": svc_notes}

    submitted = st.form_submit_button("Save Log")

    if submitted:
        errors = []
        if log_date > date.today():
            errors.append("Service date cannot be in the future.")
        if not selected_services:
            errors.append("At least one service must be selected.")
        if total_cost < 0:
            errors.append("Total cost must be 0 or greater.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            try:
                conn = get_connection()
                cur = conn.cursor()

                # Insert maintenance log
                cur.execute("""
                    INSERT INTO maintenance_logs (vehicle_id, log_date, mileage_at_service, shop_name, total_cost, notes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id;
                """, (
                    vehicle_options[vehicle_label],
                    log_date,
                    int(mileage) if mileage else None,
                    shop_name.strip() or None,
                    float(total_cost) if total_cost else None,
                    notes.strip() or None
                ))
                log_id = cur.fetchone()[0]

                # Insert one row per service into log_services
                for svc_name in selected_services:
                    svc_id = service_options[svc_name]
                    detail = service_details.get(svc_name, {})
                    cur.execute("""
                        INSERT INTO log_services (log_id, service_type_id, cost, notes)
                        VALUES (%s, %s, %s, %s);
                    """, (
                        log_id,
                        svc_id,
                        float(detail["cost"]) if detail.get("cost") else None,
                        detail["notes"].strip() or None
                    ))

                conn.commit()
                cur.close()
                conn.close()
                st.success("Maintenance log saved successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Something went wrong: {e}")