"""
SAIV Instructor Dashboard - Module 4

This is the skeleton implementation for the Observability module.
Students must implement the instructor dashboard with session management,
attendance monitoring, and metrics visualization.
"""

import streamlit as st
import os

# Page configuration
st.set_page_config(
    page_title="SAIV Instructor Dashboard",
    page_icon="📊",
    layout="wide"
)

# Environment variables
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")

st.title("SAIV Instructor Dashboard")
st.write("Welcome to the Secure Attendance & Identity Verification System")

# =============================================================================
# TODO: Implement the following pages/features
# =============================================================================

from datetime import datetime
import pandas as pd
import plotly.express as px
import requests

API_V1 = f"{BACKEND_URL}/api/v1"

# -----------------------------------------------------------------------------
# Authentication
# -----------------------------------------------------------------------------
# - Login form for instructors
# - JWT token management
# - Session persistence

if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "refresh_token" not in st.session_state:
    st.session_state.refresh_token = None
if "user_info" not in st.session_state:
    st.session_state.user_info = None

def get_auth_headers() -> dict:
    if st.session_state.access_token:
        return {"Authorization": f"Bearer {st.session_state.access_token}"}
    return {}

def api_request(method: str, endpoint: str, **kwargs) -> requests.Response:
    headers = kwargs.pop("headers", {})
    headers.update(get_auth_headers())
    url = f"{API_V1}{endpoint}"
    try:
        response = requests.request(method, url, headers=headers, timeout=15, **kwargs)
        if response.status_code == 401 and st.session_state.refresh_token:
            refresh_res = requests.post(
                f"{API_V1}/auth/refresh",
                json={"refresh_token": st.session_state.refresh_token},
                timeout=10
            )
            if refresh_res.status_code == 200:
                data = refresh_res.json()
                st.session_state.access_token = data.get("access_token")
                st.session_state.refresh_token = data.get("refresh_token", st.session_state.refresh_token)
                headers.update(get_auth_headers())
                response = requests.request(method, url, headers=headers, timeout=15, **kwargs)
            else:
                st.session_state.access_token = None
                st.session_state.user_info = None
        return response
    except requests.RequestException as e:
        st.error(f"Network error connecting to Backend API ({url}): {e}")
        return None

def login(email: str, password: str) -> bool:
    try:
        res = requests.post(
            f"{API_V1}/auth/login",
            json={"email": email, "password": password},
            timeout=10
        )
        if res.status_code == 200:
            payload = res.json()
            st.session_state.access_token = payload.get("access_token")
            st.session_state.refresh_token = payload.get("refresh_token")
            st.session_state.user_info = payload.get("user")
            
            if not st.session_state.user_info:
                me_res = api_request("GET", "/users/me")
                if me_res and me_res.status_code == 200:
                    st.session_state.user_info = me_res.json()
            return True
        else:
            detail = res.json().get("detail", "Login failed") if res.content else "Invalid credentials"
            st.error(f"Authentication Failed: {detail}")
            return False
    except requests.RequestException as e:
        st.error(f"Cannot reach Backend API at {BACKEND_URL}: {e}")
        return False

def logout():
    st.session_state.access_token = None
    st.session_state.refresh_token = None
    st.session_state.user_info = None
    st.rerun()

if not st.session_state.access_token:
    st.markdown("---")
    st.subheader("Instructor Login")
    with st.form("login_form"):
        login_email = st.text_input("Instructor / Admin Email", placeholder="instructor@ntu.edu.sg")
        login_password = st.text_input("Password", type="password")
        login_submitted = st.form_submit_button("Sign In")
        if login_submitted:
            if not login_email or not login_password:
                st.warning("Please enter both email and password.")
            else:
                if login(login_email, login_password):
                    st.success("Successfully logged in.")
                    st.rerun()
    st.stop()

user = st.session_state.user_info or {}
role = user.get("role", "student")
if role not in ["instructor", "admin", "ta"]:
    st.error(f"Access Denied: Your account role `{role}` does not have instructor dashboard privileges.")
    if st.button("Logout"):
        logout()
    st.stop()

st.sidebar.markdown(f"### 👤 {user.get('full_name', 'User')}")
st.sidebar.caption(f"Role: **{role.upper()}** | `{user.get('email')}`")

nav_selection = st.sidebar.radio(
    "Modules & Views",
    ["Overview", "Sessions Management", "Check-ins View", "Audit Logs", "Metrics Dashboard"]
)

if st.sidebar.button("Logout"):
    logout()

# -----------------------------------------------------------------------------
# Overview Page
# -----------------------------------------------------------------------------
# - Total sessions (active/inactive)
# - Total check-ins & success rate
# - Recent check-ins table
# - Check-ins by hour chart
# - Verification status pie chart

if nav_selection == "Overview":
    st.markdown("---")
    st.header("Overview")
    
    stats_res = api_request("GET", "/stats/overview")
    if stats_res and stats_res.status_code == 200:
        stats = stats_res.json()
        
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        active_sess = stats.get("active_sessions", 0)
        tot_sess = stats.get("total_sessions", 0)
        kpi1.metric("Total Sessions", tot_sess, f"{active_sess} Active / {tot_sess - active_sess} Inactive")
        kpi2.metric("Check-ins Today", stats.get("total_checkins_today", 0), f"Week: {stats.get('total_checkins_week', 0)}")
        appr_rate = stats.get("approval_rate", 0.0) * 100
        kpi3.metric("Success Rate", f"{appr_rate:.1f}%")
        kpi4.metric("Flagged Pending Review", stats.get("flagged_pending_review", 0), delta_color="inverse")
        
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.subheader("Check-ins by Day / Volume")
            checkins_trend = stats.get("trends", {}).get("checkins_by_day", [])
            if checkins_trend:
                df_trend = pd.DataFrame(checkins_trend)
                fig_trend = px.line(df_trend, x="date", y="count", markers=True, title="Check-in Volume")
                fig_trend.update_yaxes(rangemode="tozero")
                st.plotly_chart(fig_trend, use_container_width=True)
            else:
                st.info("No check-in volume trend data available.")
                
        with chart_col2:
            st.subheader("Verification Status Distribution")
            recent_for_pie = api_request("GET", "/checkins/?limit=100")
            if recent_for_pie and recent_for_pie.status_code == 200:
                p_items = recent_for_pie.json().get("items", [])
                if p_items:
                    df_pie = pd.DataFrame(p_items)
                    if "status" in df_pie.columns:
                        status_counts = df_pie["status"].value_counts().reset_index()
                        status_counts.columns = ["Status", "Count"]
                        fig_pie = px.pie(
                            status_counts, 
                            names="Status", 
                            values="Count", 
                            title="Status Breakdown",
                            color="Status",
                            color_discrete_map={
                                "approved": "#2ca02c", 
                                "flagged": "#ff7f0e", 
                                "rejected": "#d62728",
                                "appealed": "#1f77b4",
                                "pending": "#7f7f7f"
                            }
                        )
                        st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("No check-in status records found for distribution.")
    else:
        st.warning("Could not load stats from `/stats/overview`.")

    st.subheader("Recent Check-ins")
    recent_res = api_request("GET", "/checkins/?limit=10")
    if recent_res and recent_res.status_code == 200:
        data = recent_res.json()
        items = data.get("items", []) if isinstance(data, dict) else data
        if items:
            df_recent = pd.DataFrame(items)
            display_cols = [c for c in ["student_name", "student_email", "session_name", "status", "checked_in_at", "risk_score"] if c in df_recent.columns]
            st.dataframe(df_recent[display_cols].astype(str), use_container_width=True)
        else:
            st.info("No recent check-ins found.")

# -----------------------------------------------------------------------------
# Sessions Management
# -----------------------------------------------------------------------------
# - View all sessions with details
# - Create new sessions with geofence config
# - View check-ins per session
# - CSV export for gradebook

elif nav_selection == "Sessions Management":
    st.markdown("---")
    st.header("Sessions Management")
    
    courses_res = api_request("GET", "/courses/")
    course_list = courses_res.json().get("items", []) if (courses_res and courses_res.status_code == 200) else []
    course_map = {f"{c['code']} - {c['name']}": c["id"] for c in course_list}
    
    tab_view, tab_create = st.tabs(["View Sessions & Check-ins", "Create New Session"])
    
    with tab_view:
        sessions_res = api_request("GET", "/sessions/?limit=50")
        if sessions_res and sessions_res.status_code == 200:
            sess_data = sessions_res.json()
            sessions = sess_data.get("items", []) if isinstance(sess_data, dict) else sess_data
            
            if sessions:
                for s in sessions:
                    with st.expander(f"📌 {s.get('course_code', '')}: {s.get('name')} [{s.get('status', '').upper()}]"):
                        c1, c2, c3 = st.columns(3)
                        c1.markdown(f"**Session ID:** `{s.get('id')}`")
                        c1.markdown(f"**Type:** {s.get('session_type', 'lecture')}")
                        c1.markdown(f"**Venue:** {s.get('venue_name', 'N/A')}")
                        
                        c2.markdown(f"**Start:** {s.get('scheduled_start', '')}")
                        c2.markdown(f"**End:** {s.get('scheduled_end', '')}")
                        c2.markdown(f"**Geofence Radius:** {s.get('geofence_radius_meters', 100)}m")
                        
                        c3.markdown(f"**Attendance:** {s.get('checked_in_count', 0)} / {s.get('total_enrolled', 0)}")
                        
                        btn_c1, btn_c2, btn_c3 = st.columns(3)
                        cur_status = s.get("status")
                        if cur_status == "scheduled":
                            if btn_c1.button("▶️ Activate Session", key=f"btn_act_{s['id']}"):
                                res = api_request("PATCH", f"/sessions/{s['id']}", json={"status": "active"})
                                if res and res.status_code == 200:
                                    st.success("Session activated.")
                                    st.rerun()
                                else:
                                    st.error("Failed to activate session.")
                        elif cur_status == "active":
                            if btn_c2.button("⏹️ Close Session", key=f"btn_cls_{s['id']}"):
                                res = api_request("PATCH", f"/sessions/{s['id']}", json={"status": "closed"})
                                if res and res.status_code == 200:
                                    st.success("Session closed.")
                                    st.rerun()
                                else:
                                    st.error("Failed to close session.")
                                    
                        exp_res = api_request("GET", f"/export/session/{s['id']}?format=csv")
                        if exp_res and exp_res.status_code == 200:
                            btn_c3.download_button(
                                "📥 Export Gradebook (CSV)",
                                data=exp_res.content,
                                file_name=f"gradebook_session_{s['id']}.csv",
                                mime="text/csv",
                                key=f"btn_exp_{s['id']}"
                            )
                            
                        st.markdown("**Session Check-ins Table:**")
                        chk_res = api_request("GET", f"/checkins/session/{s['id']}")
                        if chk_res and chk_res.status_code == 200:
                            sess_checkins = chk_res.json()
                            if sess_checkins:
                                df_s_chk = pd.DataFrame(sess_checkins)
                                st.dataframe(df_s_chk.astype(str), use_container_width=True)
                            else:
                                st.info("No check-ins submitted for this session yet.")
            else:
                st.info("No sessions available.")
        else:
            st.error("Failed to fetch sessions list.")

    with tab_create:
        if not course_map:
            st.warning("No courses available to attach a session.")
        else:
            with st.form("create_session_form"):
                sel_course = st.selectbox("Course", list(course_map.keys()))
                s_name = st.text_input("Session Title", placeholder="Lecture 5: System Observability")
                s_type = st.selectbox("Type", ["lecture", "tutorial", "lab", "exam"])
                
                dt_c1, dt_c2 = st.columns(2)
                start_dt = dt_c1.date_input("Start Date")
                start_tm = dt_c1.time_input("Start Time", datetime.strptime("09:30", "%H:%M").time())
                end_dt = dt_c2.date_input("End Date")
                end_tm = dt_c2.time_input("End Time", datetime.strptime("11:20", "%H:%M").time())
                
                v_c1, v_c2, v_c3 = st.columns(3)
                venue_name = v_c1.text_input("Venue Name", value="LT26")
                venue_lat = v_c2.number_input("Venue Latitude", value=1.3483, format="%.6f")
                venue_lon = v_c3.number_input("Venue Longitude", value=103.6831, format="%.6f")
                
                geofence_r = st.slider("Geofence Radius (meters)", min_value=10.0, max_value=500.0, value=100.0)
                risk_limit = st.slider("Risk Cutoff Threshold", min_value=0.1, max_value=0.9, value=0.5, step=0.05)
                req_liveness = st.checkbox("Require Liveness Detection", value=True)
                
                if st.form_submit_button("Create Session"):
                    payload = {
                        "course_id": course_map[sel_course],
                        "name": s_name,
                        "session_type": s_type,
                        "scheduled_start": f"{start_dt}T{start_tm.strftime('%H:%M:%S')}Z",
                        "scheduled_end": f"{end_dt}T{end_tm.strftime('%H:%M:%S')}Z",
                        "venue_name": venue_name,
                        "venue_latitude": venue_lat,
                        "venue_longitude": venue_lon,
                        "geofence_radius_meters": geofence_r,
                        "risk_threshold": risk_limit,
                        "require_liveness_check": req_liveness
                    }
                    res = api_request("POST", "/sessions/", json=payload)
                    if res and res.status_code in [200, 201]:
                        st.success("Session successfully created.")
                        st.rerun()
                    else:
                        st.error(f"Failed to create session: {res.text if res else 'Unknown error'}")

# -----------------------------------------------------------------------------
# Check-ins View
# -----------------------------------------------------------------------------
# - Filter by session, verification status
# - Real-time updates
# - CSV export for gradebook integration
# - Attendance data with all signals

elif nav_selection == "Check-ins View":
    st.markdown("---")
    st.header("Check-ins View")
    
    triage_tab, full_roster_tab = st.tabs(["Flagged / Triage Review", "All Attendance Check-ins"])
    
    with triage_tab:
        st.subheader("Flagged & Appealed Items Requiring Action")
        flagged_res = api_request("GET", "/checkins/flagged")
        if flagged_res and flagged_res.status_code == 200:
            flagged_data = flagged_res.json()
            flagged_list = flagged_data.get("items", []) if isinstance(flagged_data, dict) else flagged_data
            if flagged_list:
                for fl in flagged_list:
                    with st.container():
                        print(type(fl))
                        print(fl)
                        st.markdown(f"#### Student: **{type(fl)}** | Session: {fl} | Session: {type(flagged_list)} | Session: {flagged_list}")
                        #st.markdown(f"#### Student: **{fl.get('student_name', 'Student')}** | Session: {fl.get('session_name', 'N/A')}")
                        fl_col1, fl_col2, fl_col3 = st.columns([1, 1, 1])
                        fl_col1.markdown(f"**Check-in ID:** `{fl.get('id')}`")
                        fl_col1.markdown(f"**Status:** `{fl.get('status')}`")
                        fl_col1.markdown(f"**Timestamp:** {fl.get('checked_in_at')}")
                        
                        fl_col2.metric("Risk Score", f"{fl.get('risk_score', 0.0):.2f}")
                        factors = fl.get("risk_factors") or []
                        if factors:
                            fl_col2.markdown("**Triggered Signals:**")
                            for f in factors:
                                fl_col2.caption(f"- `{f}`")
                                
                        if fl.get("appeal_reason"):
                            fl_col2.warning(f"Appeal Reason: {fl.get('appeal_reason')}")
                            
                        with fl_col3:
                            with st.form(f"review_box_{fl['id']}"):
                                rev_notes = st.text_input("Review Notes", placeholder="e.g., Confirmed attendance")
                                ap_btn = st.form_submit_button("✅ Approve")
                                rj_btn = st.form_submit_button("❌ Reject")
                                
                                if ap_btn:
                                    r_res = api_request("POST", f"/checkins/{fl['id']}/review", json={"status": "approved", "review_notes": rev_notes})
                                    if r_res and r_res.status_code == 200:
                                        st.success("Approved.")
                                        st.rerun()
                                    else:
                                        st.error("Failed to submit approval.")
                                if rj_btn:
                                    r_res = api_request("POST", f"/checkins/{fl['id']}/review", json={"status": "rejected", "review_notes": rev_notes})
                                    if r_res and r_res.status_code == 200:
                                        st.error("Rejected.")
                                        st.rerun()
                                    else:
                                        st.error("Failed to submit rejection.")
                        st.divider()
            else:
                st.success("No flagged check-ins currently pending review.")
        else:
            st.error("Unable to load flagged check-ins.")

    with full_roster_tab:
        st.subheader("Filter Check-in Records")
        fc1, fc2 = st.columns(2)
        status_filter = fc1.selectbox("Verification Status", ["All", "approved", "flagged", "rejected", "pending", "appealed"])
        
        endpoint_url = "/checkins/?limit=100"
        if status_filter != "All":
            endpoint_url += f"&status={status_filter}"
            
        all_chk_res = api_request("GET", endpoint_url)
        if all_chk_res and all_chk_res.status_code == 200:
            resp_json = all_chk_res.json()
            items = resp_json.get("items", []) if isinstance(resp_json, dict) else resp_json
            if items:
                df_all = pd.DataFrame(items)
                st.dataframe(df_all.astype(str), use_container_width=True)
                
                # CSV Export for gradebook integration
                csv_bytes = df_all.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Export Filtered Roster to CSV",
                    data=csv_bytes,
                    file_name="saiv_checkin_records.csv",
                    mime="text/csv"
                )
            else:
                st.info("No records found.")
        else:
            st.error("Could not fetch check-in list.")

# -----------------------------------------------------------------------------
# Audit Logs
# -----------------------------------------------------------------------------
# - Browse system events
# - Filter by event type, user, action
# - Color-coded by severity
# - Export audit trail

elif nav_selection == "Audit Logs":
    st.markdown("---")
    st.header("Audit Logs")
    
    if role != "admin":
        st.info("Note: System audit log querying requires administrative permissions according to API specifications.")
        
    al_c1, al_c2, al_c3 = st.columns(3)
    action_flt = al_c1.selectbox(
        "Action Type",
        ["All", "login_success", "login_failed", "checkin_attempted", "checkin_approved", "checkin_flagged", "checkin_rejected", "security_violation"]
    )
    res_flt = al_c2.selectbox("Resource Type", ["All", "user", "session", "checkin", "course"])
    limit_cnt = al_c3.slider("Log Limit", 20, 200, 50)
    
    audit_q = f"?limit={limit_cnt}"
    if action_flt != "All":
        audit_q += f"&action={action_flt}"
    if res_flt != "All":
        audit_q += f"&resource_type={res_flt}"
        
    audit_res = api_request("GET", f"/audit/{audit_q}")
    if audit_res and audit_res.status_code == 200:
        a_data = audit_res.json()
        logs_items = a_data.get("items", []) if isinstance(a_data, dict) else a_data
        if logs_items:
            df_logs = pd.DataFrame(logs_items)
            st.dataframe(df_logs.astype(str), use_container_width=True)
            
            csv_audit_bytes = df_logs.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Export Audit Trail (CSV)",
                data=csv_audit_bytes,
                file_name="saiv_audit_trail.csv",
                mime="text/csv"
            )
        else:
            st.info("No audit logs found for the selected filters.")
    else:
        st.warning("Could not query `/audit/` (endpoint requires admin privileges).")

# -----------------------------------------------------------------------------
# Metrics Dashboard
# -----------------------------------------------------------------------------
# - API response times (p95 latency)
# - Request rates
# - Success rates
# - Risk score distribution
# - High-risk alerts
# - System health status

elif nav_selection == "Metrics Dashboard":
    st.markdown("---")
    st.header("Metrics & Telemetry Dashboard")
    
    def fetch_prom_query(query: str):
        try:
            r = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query}, timeout=3)
            if r.status_code == 200:
                q_res = r.json().get("data", {}).get("result", [])
                if q_res and "value" in q_res[0]:
                    return float(q_res[0]["value"][1])
        except Exception:
            return None
        return None

    def fetch_prom_targets():
        try:
            r = requests.get(f"{PROMETHEUS_URL}/api/v1/targets", timeout=3)
            if r.status_code == 200:
                active_targets = r.json().get("data", {}).get("activeTargets", [])
                return [
                    {
                        "Job": t.get("labels", {}).get("job"),
                        "Endpoint": t.get("scrapeUrl"),
                        "Health": t.get("health"),
                        "Last Scrape": t.get("lastScrape")
                    }
                    for t in active_targets
                ]
        except Exception:
            return []
        return []

    # KPI Telemetry Metrics from Prometheus
    m_col1, m_col2, m_col3 = st.columns(3)
    p95_val = fetch_prom_query("histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))")
    m_col1.metric("API Latency (p95)", f"{(p95_val * 1000):.1f} ms" if p95_val is not None else "N/A")
    
    succ_rate = fetch_prom_query("sum(rate(checkin_success_total[5m])) / sum(rate(checkin_attempts_total[5m])) * 100")
    m_col2.metric("Check-in Success Rate", f"{succ_rate:.1f}%" if succ_rate is not None else "100.0%")
    
    req_rate = fetch_prom_query("sum(rate(http_requests_total[5m]))")
    m_col3.metric("API Request Rate", f"{req_rate:.2f} req/s" if req_rate is not None else "Normal")
    
    st.markdown("---")
    
    # Risk Score Distribution & Alerts
    st.subheader("Risk Score Distribution & High-Risk Alerts")
    all_checkins_for_metrics = api_request("GET", "/checkins/?limit=100")
    if all_checkins_for_metrics and all_checkins_for_metrics.status_code == 200:
        c_items = all_checkins_for_metrics.json().get("items", [])
        if c_items:
            df_m = pd.DataFrame(c_items)
            if "risk_score" in df_m.columns:
                df_m["risk_score"] = pd.to_numeric(df_m["risk_score"], errors="coerce")
                fig_hist = px.histogram(df_m, x="risk_score", nbins=20, title="Risk Score Distribution", labels={"risk_score": "Risk Score (0.0 to 1.0)"})
                fig_hist.update_xaxes(range=[0, 1])
                st.plotly_chart(fig_hist, use_container_width=True)
                
                high_risk_df = df_m[df_m["risk_score"] >= 0.5]
                if not high_risk_df.empty:
                    st.warning(f"🚨 High-Risk Alert: {len(high_risk_df)} check-ins currently exceed risk threshold (>= 0.5).")
                    st.dataframe(high_risk_df[["student_name", "session_name", "risk_score", "status"]].astype(str), use_container_width=True)
                else:
                    st.success("No high-risk anomalies detected across current records.")
        else:
            st.info("No check-in metrics available yet.")
            
    st.markdown("---")
    
    # System & Scrape Health from Prometheus Targets
    st.subheader("System Health & Infrastructure Telemetry")
    targets = fetch_prom_targets()
    if targets:
        st.markdown("**Active Scrape Targets Status:**")
        st.dataframe(pd.DataFrame(targets).astype(str), use_container_width=True)
    else:
        st.info(f"Prometheus is active at `{PROMETHEUS_URL}`. Running targets will appear when scraping.")

    # Grafana Launch Portal
    st.markdown("---")
    st.subheader("Grafana Visualization Portal")
    g_col1, g_col2 = st.columns([2, 1])
    with g_col1:
        st.markdown(
            """
            Grafana provides visual dashboards for Prometheus metrics, running on port `:3001`. 
            Default credentials are configured in `docker-compose.yml`:
            - **URL**: [http://localhost:3001](http://localhost:3001)
            - **Username**: `admin`
            - **Password**: `admin`
            """
        )
    with g_col2:
        st.link_button("🚀 Open Grafana Portal", "http://localhost:3001", use_container_width=True)

# =============================================================================
# CSV Export Format
# =============================================================================
# Required columns:
# - Check-in ID, Student ID, Session ID
# - Timestamp, Verification Status
# - Risk Score, Liveness Score, Face Match Score
# - GPS Coordinates (latitude, longitude)

st.sidebar.markdown("---")
st.sidebar.subheader("Gradebook Export Format")
if st.sidebar.button("Generate Template CSV"):
    sample_df = pd.DataFrame({
        "Check-in ID": ["sample-chk-001"],
        "Student ID": ["sample-std-001"],
        "Session ID": ["sample-ses-001"],
        "Timestamp": [datetime.utcnow().isoformat() + "Z"],
        "Verification Status": ["approved"],
        "Risk Score": [0.15],
        "Liveness Score": [0.92],
        "Face Match Score": [0.85],
        "GPS Latitude": [1.3483],
        "GPS Longitude": [103.6831]
    })
    st.sidebar.download_button(
        "Download Template",
        data=sample_df.to_csv(index=False).encode("utf-8"),
        file_name="saiv_export_spec_template.csv",
        mime="text/csv"
    )
