import streamlit as st
import psycopg2
from datetime import datetime

def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])

st.set_page_config(page_title="Manage Vehicles", layout="wide")
st.title("Manage Vehicles")

# --- Load vehicle types from DB ---
def load_vehicle_types():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM vehicle_types ORDER BY name;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {row[1]: row[0] for row in rows}

# --- Load all vehicles ---
def load_vehicles():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT v.id, v.year, v.make, v.model, v.nickname, vt.name as type,
               v.color, v.current_mileage, v.vin, v.notes
        FROM vehicles v
        JOIN vehicle_types vt ON v.type_id = vt.id
        ORDER BY v.year DESC, v.make;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# --- Session state ---
if "edit_vehicle_id" not in st.session_state:
    st.session_state.edit_vehicle_id = None
if "delete_vehicle_id" not in st.session_state:
    st.session_state.delete_vehicle_id = None

vehicle_types = load_vehicle_types()
current_year = datetime.now().year

# --- Add Vehicle Form ---
st.subheader("Add a Vehicle")
with st.form("add_vehicle"):
    col1, col2, col3 = st.columns(3)
    with col1:
        year = st.number_input("Year *", min_value=1900, max_value=current_year + 1, step=1, value=current_year)
        make = st.text_input("Make *")
        model = st.text_input("Model *")
    with col2:
        nickname = st.text_input("Nickname")
        type_name = st.selectbox("Type *", options=list(vehicle_types.keys()))
        color = st.text_input("Color")
    with col3:
        current_mileage = st.number_input("Current Mileage", min_value=0, step=1, value=0)
        vin = st.text_input("VIN")
    notes = st.text_area("Notes")
    submitted = st.form_submit_button("Add Vehicle")

    if submitted:
        errors = []
        if not make.strip():
            errors.append("Make is required.")
        if not model.strip():
            errors.append("Model is required.")
        if current_mileage < 0:
            errors.append("Mileage must be a positive number.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO vehicles (year, make, model, nickname, type_id, color, current_mileage, vin, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    int(year),
                    make.strip(),
                    model.strip(),
                    nickname.strip() or None,
                    vehicle_types[type_name],
                    color.strip() or None,
                    int(current_mileage) if current_mileage else None,
                    vin.strip() or None,
                    notes.strip() or None
                ))
                conn.commit()
                cur.close()
                conn.close()
                st.success(f"{year} {make} {model} added successfully!")
                st.rerun()
            except psycopg2.errors.UniqueViolation:
                st.error("A vehicle with that VIN already exists.")
            except Exception as e:
                st.error(f"Something went wrong: {e}")

# --- Current Vehicles ---
st.subheader("Your Vehicles")
vehicles = load_vehicles()

if not vehicles:
    st.info("No vehicles added yet.")
else:
    for v in vehicles:
        vid, yr, mk, md, nick, vtype, clr, mil, vin_num, vnotes = v
        label = f"{yr} {mk} {md}" + (f' — "{nick}"' if nick else "")
        col1, col2, col3 = st.columns([4, 1, 1])
        with col1:
            st.write(f"**{label}** | {vtype} | {clr or '—'} | {mil or '—'} mi | VIN: {vin_num or '—'}")
        with col2:
            if st.button("Edit", key=f"edit_{vid}"):
                st.session_state.edit_vehicle_id = vid
                st.session_state.delete_vehicle_id = None
        with col3:
            if st.button("Delete", key=f"delete_{vid}"):
                st.session_state.delete_vehicle_id = vid
                st.session_state.edit_vehicle_id = None

    # --- Delete Confirmation ---
    if st.session_state.delete_vehicle_id:
        vid = st.session_state.delete_vehicle_id
        st.warning("Are you sure you want to delete this vehicle? This will also delete all its maintenance logs.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, delete it"):
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("DELETE FROM vehicles WHERE id = %s;", (vid,))
                conn.commit()
                cur.close()
                conn.close()
                st.session_state.delete_vehicle_id = None
                st.success("Vehicle deleted.")
                st.rerun()
        with col2:
            if st.button("Cancel"):
                st.session_state.delete_vehicle_id = None
                st.rerun()

    # --- Edit Form ---
    if st.session_state.edit_vehicle_id:
        vid = st.session_state.edit_vehicle_id
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT year, make, model, nickname, type_id, color, current_mileage, vin, notes
            FROM vehicles WHERE id = %s;
        """, (vid,))
        ev = cur.fetchone()
        cur.close()
        conn.close()

        if ev:
            st.subheader("Edit Vehicle")
            type_names = list(vehicle_types.keys())
            type_ids = list(vehicle_types.values())
            current_type_name = type_names[type_ids.index(ev[4])]

            with st.form("edit_vehicle"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    e_year = st.number_input("Year *", min_value=1900, max_value=current_year + 1, step=1, value=ev[0])
                    e_make = st.text_input("Make *", value=ev[1])
                    e_model = st.text_input("Model *", value=ev[2])
                with col2:
                    e_nickname = st.text_input("Nickname", value=ev[3] or "")
                    e_type = st.selectbox("Type *", options=type_names, index=type_names.index(current_type_name))
                    e_color = st.text_input("Color", value=ev[5] or "")
                with col3:
                    e_mileage = st.number_input("Current Mileage", min_value=0, step=1, value=ev[6] or 0)
                    e_vin = st.text_input("VIN", value=ev[7] or "")
                e_notes = st.text_area("Notes", value=ev[8] or "")
                save = st.form_submit_button("Save Changes")
                cancel = st.form_submit_button("Cancel")

                if cancel:
                    st.session_state.edit_vehicle_id = None
                    st.rerun()

                if save:
                    errors = []
                    if not e_make.strip():
                        errors.append("Make is required.")
                    if not e_model.strip():
                        errors.append("Model is required.")
                    if errors:
                        for e in errors:
                            st.error(e)
                    else:
                        try:
                            conn = get_connection()
                            cur = conn.cursor()
                            cur.execute("""
                                UPDATE vehicles SET year=%s, make=%s, model=%s, nickname=%s,
                                type_id=%s, color=%s, current_mileage=%s, vin=%s, notes=%s
                                WHERE id=%s;
                            """, (
                                int(e_year), e_make.strip(), e_model.strip(),
                                e_nickname.strip() or None, vehicle_types[e_type],
                                e_color.strip() or None, int(e_mileage) or None,
                                e_vin.strip() or None, e_notes.strip() or None, vid
                            ))
                            conn.commit()
                            cur.close()
                            conn.close()
                            st.session_state.edit_vehicle_id = None
                            st.success("Vehicle updated!")
                            st.rerun()
                        except psycopg2.errors.UniqueViolation:
                            st.error("A vehicle with that VIN already exists.")
                        except Exception as e:
                            st.error(f"Something went wrong: {e}")