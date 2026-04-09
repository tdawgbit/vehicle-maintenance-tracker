import streamlit as st
import psycopg2
from datetime import date

def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])

st.set_page_config(page_title="Maintenance History", layout="wide")
st.title("Maintenance History")

# --- Load vehicles for filter dropdown ---
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

# --- Load logs with filters ---
def load_logs(vehicle_id=None, date_from=None, date_to=None):
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT 
            ml.id,
            v.year, v.make, v.model, v.nickname,
            ml.log_date,
            ml.mileage_at_service,
            ml.shop_name,
            ml.total_cost,
            ml.notes,
            STRING_AGG(st.name, ', ' ORDER BY st.name) as services
        FROM maintenance_logs ml
        JOIN vehicles v ON ml.vehicle_id = v.id
        LEFT JOIN log_services ls ON ml.id = ls.log_id
        LEFT JOIN service_types st ON ls.service_type_id = st.id
        WHERE 1=1
    """
    params = []
    if vehicle_id:
        query += " AND ml.vehicle_id = %s"
        params.append(vehicle_id)
    if date_from:
        query += " AND ml.log_date >= %s"
        params.append(date_from)
    if date_to:
        query += " AND ml.log_date <= %s"
        params.append(date_to)
    query += " GROUP BY ml.id, v.year, v.make, v.model, v.nickname ORDER BY ml.log_date DESC;"
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# --- Load service types for edit form ---
def load_service_types():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM service_types ORDER BY name;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# --- Session state ---
if "edit_log_id" not in st.session_state:
    st.session_state.edit_log_id = None
if "delete_log_id" not in st.session_state:
    st.session_state.delete_log_id = None

vehicles = load_vehicles()

if not vehicles:
    st.warning("No vehicles found. Please add a vehicle first.")
    st.stop()

vehicle_options = {"All Vehicles": None}
vehicle_options.update({
    f"{yr} {mk} {md}" + (f' — "{nick}"' if nick else ""): vid
    for vid, yr, mk, md, nick in vehicles
})

# --- Filters ---
st.subheader("Filter Logs")
col1, col2, col3 = st.columns(3)
with col1:
    selected_vehicle = st.selectbox("Vehicle", options=list(vehicle_options.keys()))
with col2:
    date_from = st.date_input("From", value=None)
with col3:
    date_to = st.date_input("To", value=None)

vehicle_id_filter = vehicle_options[selected_vehicle]
logs = load_logs(vehicle_id_filter, date_from, date_to)

# --- Display Logs ---
st.subheader("Logs")

if not logs:
    st.info("No maintenance logs found.")
else:
    for log in logs:
        lid, yr, mk, md, nick, log_date, mileage, shop, cost, lnotes, services = log
        vehicle_label = f"{yr} {mk} {md}" + (f' — "{nick}"' if nick else "")
        cost_str = f"${cost:,.2f}" if cost else "—"
        mileage_str = f"{mileage:,} mi" if mileage else "—"
        shop_str = shop or "—"

        col1, col2, col3 = st.columns([5, 1, 1])
        with col1:
            st.markdown(f"**{vehicle_label}** | {log_date.strftime('%b %d, %Y')} | {mileage_str} | {shop_str} | {cost_str}")
            st.caption(f"Services: {services or '—'}")
            if lnotes:
                st.caption(f"Notes: {lnotes}")
        with col2:
            if st.button("Edit", key=f"edit_{lid}"):
                st.session_state.edit_log_id = lid
                st.session_state.delete_log_id = None
        with col3:
            if st.button("Delete", key=f"delete_{lid}"):
                st.session_state.delete_log_id = lid
                st.session_state.edit_log_id = None

    # --- Delete Confirmation ---
    if st.session_state.delete_log_id:
        lid = st.session_state.delete_log_id
        st.warning("Are you sure you want to delete this log? This cannot be undone.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, delete it"):
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("DELETE FROM maintenance_logs WHERE id = %s;", (lid,))
                conn.commit()
                cur.close()
                conn.close()
                st.session_state.delete_log_id = None
                st.success("Log deleted.")
                st.rerun()
        with col2:
            if st.button("Cancel"):
                st.session_state.delete_log_id = None
                st.rerun()

    # --- Edit Form ---
    if st.session_state.edit_log_id:
        lid = st.session_state.edit_log_id
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT vehicle_id, log_date, mileage_at_service, shop_name, total_cost, notes
            FROM maintenance_logs WHERE id = %s;
        """, (lid,))
        el = cur.fetchone()

        cur.execute("""
            SELECT ls.service_type_id, st.name, ls.cost, ls.notes
            FROM log_services ls
            JOIN service_types st ON ls.service_type_id = st.id
            WHERE ls.log_id = %s;
        """, (lid,))
        existing_services = cur.fetchall()
        cur.close()
        conn.close()

        if el:
            st.subheader("Edit Log")
            service_types = load_service_types()
            service_options = {name: sid for sid, name in service_types}
            existing_service_names = [row[1] for row in existing_services]
            existing_service_details = {row[1]: {"cost": row[2], "notes": row[3]} for row in existing_services}

            with st.form("edit_log"):
                col1, col2 = st.columns(2)
                with col1:
                    e_vehicle = st.selectbox("Vehicle *", options=list(vehicle_options.keys()),
                        index=list(vehicle_options.values()).index(el[0]))
                    e_date = st.date_input("Service Date *", value=el[1])
                    e_mileage = st.number_input("Mileage at Service", min_value=0, step=1, value=el[2] or 0)
                with col2:
                    e_shop = st.text_input("Shop / Location", value=el[3] or "")
                    e_cost = st.number_input("Total Cost ($)", min_value=0.0, step=0.01, value=float(el[4]) if el[4] else 0.0)
                e_notes = st.text_area("Notes", value=el[5] or "")

                st.markdown("**Services Performed ***")
                e_services = st.multiselect("Services", options=list(service_options.keys()), default=existing_service_names)

                service_details = {}
                if e_services:
                    st.markdown("**Optional: per-service details**")
                    for svc in e_services:
                        with st.expander(svc):
                            prev = existing_service_details.get(svc, {})
                            scol1, scol2 = st.columns(2)
                            with scol1:
                                svc_cost = st.number_input(f"Cost for {svc} ($)", min_value=0.0, step=0.01,
                                    value=float(prev.get("cost") or 0.0), key=f"edit_cost_{svc}")
                            with scol2:
                                svc_notes = st.text_input(f"Notes for {svc}",
                                    value=prev.get("notes") or "", key=f"edit_notes_{svc}")
                            service_details[svc] = {"cost": svc_cost, "notes": svc_notes}

                save = st.form_submit_button("Save Changes")
                cancel = st.form_submit_button("Cancel")

                if cancel:
                    st.session_state.edit_log_id = None
                    st.rerun()

                if save:
                    errors = []
                    if e_date > date.today():
                        errors.append("Service date cannot be in the future.")
                    if not e_services:
                        errors.append("At least one service must be selected.")
                    if errors:
                        for e in errors:
                            st.error(e)
                    else:
                        try:
                            conn = get_connection()
                            cur = conn.cursor()
                            cur.execute("""
                                UPDATE maintenance_logs
                                SET vehicle_id=%s, log_date=%s, mileage_at_service=%s,
                                    shop_name=%s, total_cost=%s, notes=%s
                                WHERE id=%s;
                            """, (
                                vehicle_options[e_vehicle],
                                e_date,
                                int(e_mileage) if e_mileage else None,
                                e_shop.strip() or None,
                                float(e_cost) if e_cost else None,
                                e_notes.strip() or None,
                                lid
                            ))
                            # Replace log_services
                            cur.execute("DELETE FROM log_services WHERE log_id = %s;", (lid,))
                            for svc_name in e_services:
                                svc_id = service_options[svc_name]
                                detail = service_details.get(svc_name, {})
                                cur.execute("""
                                    INSERT INTO log_services (log_id, service_type_id, cost, notes)
                                    VALUES (%s, %s, %s, %s);
                                """, (
                                    lid,
                                    svc_id,
                                    float(detail["cost"]) if detail.get("cost") else None,
                                    detail["notes"].strip() or None
                                ))
                            conn.commit()
                            cur.close()
                            conn.close()
                            st.session_state.edit_log_id = None
                            st.success("Log updated!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Something went wrong: {e}")