import streamlit as st
import psycopg2

def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])

st.set_page_config(page_title="Manage Service Types", layout="wide")
st.title("Manage Service Types")

# --- Load all service types ---
def load_service_types():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, default_interval_miles, default_interval_days FROM service_types ORDER BY name;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# --- Session state ---
if "edit_service_id" not in st.session_state:
    st.session_state.edit_service_id = None
if "delete_service_id" not in st.session_state:
    st.session_state.delete_service_id = None

# --- Add Service Type Form ---
st.subheader("Add a Service Type")
with st.form("add_service"):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Service Name *")
        description = st.text_area("Description")
    with col2:
        interval_miles = st.number_input("Default Interval (miles)", min_value=0, step=500, value=0)
        interval_days = st.number_input("Default Interval (days)", min_value=0, step=30, value=0)
    submitted = st.form_submit_button("Add Service Type")

    if submitted:
        errors = []
        if not name.strip():
            errors.append("Service name is required.")
        if interval_miles < 0:
            errors.append("Interval miles must be a positive number.")
        if interval_days < 0:
            errors.append("Interval days must be a positive number.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO service_types (name, description, default_interval_miles, default_interval_days)
                    VALUES (%s, %s, %s, %s);
                """, (
                    name.strip(),
                    description.strip() or None,
                    int(interval_miles) if interval_miles else None,
                    int(interval_days) if interval_days else None
                ))
                conn.commit()
                cur.close()
                conn.close()
                st.success(f"'{name}' added successfully!")
                st.rerun()
            except psycopg2.errors.UniqueViolation:
                st.error(f"A service type named '{name}' already exists.")
            except Exception as e:
                st.error(f"Something went wrong: {e}")

# --- Current Service Types ---
st.subheader("Current Service Types")
service_types = load_service_types()

if not service_types:
    st.info("No service types added yet.")
else:
    for s in service_types:
        sid, sname, sdesc, smiles, sdays = s
        col1, col2, col3 = st.columns([4, 1, 1])
        with col1:
            miles_str = f"{smiles:,} mi" if smiles else "—"
            days_str = f"{sdays} days" if sdays else "—"
            st.write(f"**{sname}** | Every {miles_str} or {days_str} | {sdesc or '—'}")
        with col2:
            if st.button("Edit", key=f"edit_{sid}"):
                st.session_state.edit_service_id = sid
                st.session_state.delete_service_id = None
        with col3:
            if st.button("Delete", key=f"delete_{sid}"):
                st.session_state.delete_service_id = sid
                st.session_state.edit_service_id = None

    # --- Delete Confirmation ---
    if st.session_state.delete_service_id:
        sid = st.session_state.delete_service_id
        st.warning("Are you sure you want to delete this service type? This cannot be undone.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, delete it"):
                try:
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("DELETE FROM service_types WHERE id = %s;", (sid,))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.session_state.delete_service_id = None
                    st.success("Service type deleted.")
                    st.rerun()
                except psycopg2.errors.ForeignKeyViolation:
                    st.error("Can't delete this service type — it's used in existing maintenance logs.")
                except Exception as e:
                    st.error(f"Something went wrong: {e}")
        with col2:
            if st.button("Cancel"):
                st.session_state.delete_service_id = None
                st.rerun()

    # --- Edit Form ---
    if st.session_state.edit_service_id:
        sid = st.session_state.edit_service_id
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name, description, default_interval_miles, default_interval_days FROM service_types WHERE id = %s;", (sid,))
        es = cur.fetchone()
        cur.close()
        conn.close()

        if es:
            st.subheader("Edit Service Type")
            with st.form("edit_service"):
                col1, col2 = st.columns(2)
                with col1:
                    e_name = st.text_input("Service Name *", value=es[0])
                    e_desc = st.text_area("Description", value=es[1] or "")
                with col2:
                    e_miles = st.number_input("Default Interval (miles)", min_value=0, step=500, value=es[2] or 0)
                    e_days = st.number_input("Default Interval (days)", min_value=0, step=30, value=es[3] or 0)
                save = st.form_submit_button("Save Changes")
                cancel = st.form_submit_button("Cancel")

                if cancel:
                    st.session_state.edit_service_id = None
                    st.rerun()

                if save:
                    errors = []
                    if not e_name.strip():
                        errors.append("Service name is required.")
                    if errors:
                        for e in errors:
                            st.error(e)
                    else:
                        try:
                            conn = get_connection()
                            cur = conn.cursor()
                            cur.execute("""
                                UPDATE service_types SET name=%s, description=%s,
                                default_interval_miles=%s, default_interval_days=%s
                                WHERE id=%s;
                            """, (
                                e_name.strip(),
                                e_desc.strip() or None,
                                int(e_miles) if e_miles else None,
                                int(e_days) if e_days else None,
                                sid
                            ))
                            conn.commit()
                            cur.close()
                            conn.close()
                            st.session_state.edit_service_id = None
                            st.success("Service type updated!")
                            st.rerun()
                        except psycopg2.errors.UniqueViolation:
                            st.error(f"A service type named '{e_name}' already exists.")
                        except Exception as e:
                            st.error(f"Something went wrong: {e}")