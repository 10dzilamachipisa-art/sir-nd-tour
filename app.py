"""
Sir ND V2 — by Machipisa Ngonidzashe
Premium Dark Cyberpunk / Neon Classroom web app for ZIMSEC O-Level tutoring.

Stack:
- Streamlit (UI + hosting on Streamlit Community Cloud)
- Supabase (auth + Postgres database for chat history & timetable)
- google-genai (current Gemini SDK — NOT the deprecated google-generativeai)

Run locally:
    streamlit run app.py

See DEPLOYMENT.md and schema.sql for setup.
"""

import datetime
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from google.genai import types
from supabase import create_client, Client

# ==========================================================================
# PAGE CONFIG
# ==========================================================================
st.set_page_config(
    page_title="Sir ND | ZIMSEC AI Tutor",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ==========================================================================
# THEME — Dark Cyberpunk / Neon Classroom CSS
# ==========================================================================
# Note: Streamlit's internal DOM class names (data-testid, etc.) can shift
# between Streamlit versions. If a future Streamlit upgrade makes a selector
# stop matching, open browser dev tools, inspect the element, and update the
# selector here — the color variables at the top are the only thing you
# should need to touch for a re-theme.
NEON_CYAN = "#00f2fe"
NEON_PURPLE = "#4facfe"

CUSTOM_CSS = f"""
<style>
:root {{
    --neon-cyan: {NEON_CYAN};
    --neon-purple: {NEON_PURPLE};
    --bg-deep: #05070a;
    --bg-panel: #0d1117;
    --text-crisp: #e8ecf1;
}}

.stApp {{
    background: radial-gradient(circle at 20% 0%, #0f1420 0%, var(--bg-deep) 55%);
    color: var(--text-crisp);
}}

h1, h2, h3 {{
    color: var(--text-crisp) !important;
    text-shadow: 0 0 8px rgba(0,242,254,0.45), 0 0 18px rgba(79,172,254,0.25);
    letter-spacing: 0.5px;
}}

/* Tabs */
button[data-baseweb="tab"] {{
    color: #9fb0c3 !important;
    border-bottom: 2px solid transparent !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
    color: var(--neon-cyan) !important;
    border-bottom: 2px solid var(--neon-cyan) !important;
    text-shadow: 0 0 10px rgba(0,242,254,0.7);
}}

/* Buttons */
.stButton>button, .stDownloadButton>button {{
    background: linear-gradient(135deg, rgba(0,242,254,0.12), rgba(79,172,254,0.12));
    color: var(--text-crisp);
    border: 1px solid var(--neon-cyan);
    border-radius: 10px;
    box-shadow: 0 0 10px rgba(0,242,254,0.35);
    transition: all 0.15s ease-in-out;
}}
.stButton>button:hover, .stDownloadButton>button:hover {{
    box-shadow: 0 0 18px rgba(0,242,254,0.75), 0 0 28px rgba(79,172,254,0.4);
    border-color: var(--neon-purple);
    color: white;
}}

/* Inputs */
.stTextInput>div>div>input,
.stTextArea textarea,
.stTimeInput input,
.stSelectbox div[data-baseweb="select"] {{
    background-color: var(--bg-panel) !important;
    color: var(--text-crisp) !important;
    border: 1px solid rgba(79,172,254,0.5) !important;
    border-radius: 8px !important;
}}
.stTextInput>div>div>input:focus, .stTextArea textarea:focus {{
    border-color: var(--neon-cyan) !important;
    box-shadow: 0 0 10px rgba(0,242,254,0.5) !important;
}}

/* Chat bubbles */
[data-testid="stChatMessage"] {{
    background: var(--bg-panel);
    border: 1px solid rgba(79,172,254,0.35);
    border-radius: 12px;
    box-shadow: 0 0 12px rgba(79,172,254,0.12);
}}

/* Containers / cards */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    border-color: rgba(0,242,254,0.35) !important;
    box-shadow: 0 0 14px rgba(0,242,254,0.08);
}}

hr {{
    border-color: rgba(79,172,254,0.4);
}}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ==========================================================================
# SECRETS / CONFIG
# ==========================================================================
def secret(key, required=True, default=None):
    try:
        return st.secrets[key]
    except Exception:
        if required:
            st.error(f"⚠️ Missing `{key}` in Streamlit secrets. See DEPLOYMENT.md.")
            st.stop()
        return default


GEMINI_API_KEY = secret("GEMINI_API_KEY")
SUPABASE_URL = secret("SUPABASE_URL")
SUPABASE_ANON_KEY = secret("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = secret("SUPABASE_SERVICE_ROLE_KEY", required=False)
ADMIN_PASSPHRASE = secret("ADMIN_PASSPHRASE", required=False, default="sir nd report")

MODEL_NAME = "gemini-3.6-flash"
# Google retires Flash versions on a few months' notice and ships new ones
# every few weeks. If this ever 404s, swap in whichever version the error
# message names, or use the alias "gemini-flash-latest" instead.

SUBJECTS = {
    "mathematics": {"label": "📐 Mathematics", "icon": "📐"},
    "science": {"label": "🔬 Combined Science", "icon": "🔬"},
}

SIR_ND_BASE_PERSONA = """
You are "Sir ND" (full name: Machipisa Ngonidzashe), a warm, authoritative, and
deeply encouraging Zimbabwean secondary school teacher tutoring ZIMSEC O-Level
candidates, strictly aligned to the current ZIMSEC syllabus.

NON-NEGOTIABLE RULES:
1. NEVER give a direct final answer to a homework, practice, or exam-style
   question on the first ask. Use the Socratic method: ask a leading question,
   give a hint, break the problem into its first small step, and let the
   student attempt the next step. Only reveal a full worked answer after the
   student has genuinely tried multiple times and walked through the method
   with you — and even then, show the reasoning, not just the final figure.
   Conceptual "what is / define / explain" questions (not graded items) can be
   answered directly.
2. Teach in SHORT, BITE-SIZED, MOBILE-FRIENDLY chunks (most students are on
   small Android screens with costly data). Keep messages under ~120 words
   unless a worked example needs more. Use short paragraphs and numbered
   steps. End most explanations with one simple check-understanding question.
3. Use local ZIMBABWEAN CONTEXT: ZiG/USD, kombis, mealie-meal, Mbare Musika,
   ecocash/airtime, Kariba Dam, Victoria Falls, Great Zimbabwe, Eastern
   Highlands, maize/tobacco/cotton farming, load-shedding, pre-colonial
   kingdoms, the Chimurenga wars, 1980 independence — wherever it fits
   naturally and respectfully.
4. ZIMSEC ALIGNMENT: use ZIMSEC command words (state, describe, explain,
   discuss, calculate, evaluate) and show full working for calculations,
   since method marks matter as much as the final answer.
5. TONE: firm but warm. Never mock a wrong answer — correct it kindly and
   explain the misconception, with genuine encouragement.
6. Stay in character as Sir ND. Don't mention being an AI/Gemini/Google unless
   directly asked how you work; answer briefly, then return to teaching.
"""

SUBJECT_CONTEXT = {
    "mathematics": (
        "This session is the MATHEMATICS room. Focus on ZIMSEC O-Level "
        "Mathematics syllabus topics: number, algebra, geometry, statistics, "
        "trigonometry, and graphs. Show full working for every calculation."
    ),
    "science": (
        "This session is the COMBINED SCIENCE room. Cover ZIMSEC O-Level "
        "Combined Science: Biology, Chemistry, and Physics topics. Use "
        "correct scientific terminology alongside local examples (e.g. "
        "farming for biology, Kariba's hydro turbines for physics)."
    ),
}

REPORT_SYSTEM_INSTRUCTION = """
You are an academic report-writing assistant working for "Sir ND", a ZIMSEC
O-Level tutor. Given transcripts of tutoring sessions between Sir ND and a
student (across Mathematics and/or Combined Science), write a short, formal,
professional progress report addressed to the student's PARENT/GUARDIAN. It
must:
- Open with a polite greeting to the parent/guardian, naming the student.
- Summarize which subject(s)/topics were covered.
- Give an honest but constructive assessment of understanding, effort, and
  strengths.
- Clearly flag topics where the student struggled and needs more home
  practice.
- Suggest 1-3 concrete next steps or home revision activities.
- Close with an encouraging, respectful sign-off from "Sir ND (Machipisa
  Ngonidzashe)".
- Roughly 200-350 words, formal written English, no markdown headers — this
  is read/printed for a parent.
"""

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# ==========================================================================
# CLIENTS
# ==========================================================================
@st.cache_resource(show_spinner=False)
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)


@st.cache_resource(show_spinner=False)
def get_supabase_client() -> Client:
    """Anon-key client — respects Row Level Security, used for all
    student-facing reads/writes so students can only ever touch their own
    rows."""
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


@st.cache_resource(show_spinner=False)
def get_supabase_admin_client():
    """Service-role client — bypasses RLS. Only used inside the password-
    gated admin panel, and only server-side (this code runs on Streamlit's
    server, never in the student's browser), so the service key is never
    exposed to any client."""
    if not SUPABASE_SERVICE_ROLE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


gemini_client = get_gemini_client()
supabase = get_supabase_client()

# ==========================================================================
# SESSION STATE
# ==========================================================================
defaults = {
    "auth_user": None,          # dict with id, email, full_name once logged in
    "auth_mode": "login",       # "login" or "signup"
    "chat_cache": {"mathematics": [], "science": []},
    "timetable": {day: {"topic": "", "target_time": None} for day in DAYS_OF_WEEK},
    "admin_unlocked": False,
    "last_report": None,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ==========================================================================
# AUTH HELPERS
# ==========================================================================
def sign_up(email, password, full_name):
    try:
        result = supabase.auth.sign_up({"email": email, "password": password})
        user = result.user
        if user is None:
            return False, "Sign-up did not return a user — check your email for a confirmation link."
        # Store the display name in a profiles row (id matches auth.users.id)
        supabase.table("profiles").insert(
            {"id": user.id, "full_name": full_name}
        ).execute()
        return True, "Account created! If email confirmation is enabled on your Supabase project, check your inbox before logging in."
    except Exception as e:
        return False, f"Sign-up failed: {e}"


def sign_in(email, password):
    try:
        result = supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        user = result.user
        if user is None:
            return False, "Login failed — check your email and password."
        profile = (
            supabase.table("profiles")
            .select("full_name")
            .eq("id", user.id)
            .single()
            .execute()
        )
        full_name = profile.data["full_name"] if profile.data else email
        st.session_state.auth_user = {
            "id": user.id,
            "email": user.email,
            "full_name": full_name,
        }
        load_all_chats(user.id)
        load_timetable(user.id)
        return True, f"Welcome back, {full_name}!"
    except Exception as e:
        return False, f"Login failed: {e}"


def sign_out():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.auth_user = None
    st.session_state.chat_cache = {"mathematics": [], "science": []}
    st.session_state.timetable = {day: {"topic": "", "target_time": None} for day in DAYS_OF_WEEK}


# ==========================================================================
# CHAT PERSISTENCE (Supabase)
# ==========================================================================
def load_all_chats(student_id):
    for subject in SUBJECTS:
        try:
            rows = (
                supabase.table("chat_messages")
                .select("role, content, created_at")
                .eq("student_id", student_id)
                .eq("subject", subject)
                .order("created_at")
                .execute()
            )
            st.session_state.chat_cache[subject] = [
                {"role": r["role"], "content": r["content"]} for r in rows.data
            ]
        except Exception as e:
            st.session_state.chat_cache[subject] = []
            st.warning(f"Could not load {subject} history: {e}")


def save_message(student_id, subject, role, content):
    try:
        supabase.table("chat_messages").insert(
            {
                "student_id": student_id,
                "subject": subject,
                "role": role,
                "content": content,
            }
        ).execute()
    except Exception as e:
        st.warning(f"Could not save message to database: {e}")


def gemini_history(messages):
    history = []
    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        history.append({"role": role, "parts": [{"text": m["content"]}]})
    return history


def send_to_sir_nd(subject, student_id, user_message):
    st.session_state.chat_cache[subject].append({"role": "user", "content": user_message})
    save_message(student_id, subject, "user", user_message)

    history_for_model = gemini_history(st.session_state.chat_cache[subject][:-1])
    system_instruction = SIR_ND_BASE_PERSONA + "\n\n" + SUBJECT_CONTEXT[subject]

    full_reply = ""
    try:
        chat_session = gemini_client.chats.create(
            model=MODEL_NAME,
            history=history_for_model,
            config=types.GenerateContentConfig(system_instruction=system_instruction),
        )
        for chunk in chat_session.send_message_stream(user_message):
            if chunk.text:
                full_reply += chunk.text
    except Exception as e:
        full_reply = f"⚠️ Sorry, I hit an error talking to Gemini: {e}"

    st.session_state.chat_cache[subject].append({"role": "assistant", "content": full_reply})
    save_message(student_id, subject, "assistant", full_reply)
    return full_reply


# ==========================================================================
# TIMETABLE PERSISTENCE (Supabase)
# ==========================================================================
def load_timetable(student_id):
    try:
        rows = (
            supabase.table("timetable")
            .select("day_of_week, topic, target_time")
            .eq("student_id", student_id)
            .execute()
        )
        table = {day: {"topic": "", "target_time": None} for day in DAYS_OF_WEEK}
        for r in rows.data:
            table[r["day_of_week"]] = {
                "topic": r["topic"] or "",
                "target_time": r["target_time"],
            }
        st.session_state.timetable = table
    except Exception as e:
        st.warning(f"Could not load timetable: {e}")


def save_timetable(student_id, timetable):
    try:
        for day, entry in timetable.items():
            target_time_str = None
            if entry["target_time"]:
                t = entry["target_time"]
                target_time_str = t.strftime("%H:%M:%S") if hasattr(t, "strftime") else str(t)
            supabase.table("timetable").upsert(
                {
                    "student_id": student_id,
                    "day_of_week": day,
                    "topic": entry["topic"],
                    "target_time": target_time_str,
                },
                on_conflict="student_id,day_of_week",
            ).execute()
        return True, "Timetable saved!"
    except Exception as e:
        return False, f"Could not save timetable: {e}"


# ==========================================================================
# ADMIN REPORT GENERATION
# ==========================================================================
def generate_parent_report(student_name, student_id, admin_client):
    transcript_lines = [f"Student: {student_name}\n"]
    for subject in SUBJECTS:
        try:
            rows = (
                admin_client.table("chat_messages")
                .select("role, content, created_at")
                .eq("student_id", student_id)
                .eq("subject", subject)
                .order("created_at", desc=True)
                .limit(40)
                .execute()
            )
            msgs = list(reversed(rows.data))
            if msgs:
                transcript_lines.append(f"\n--- {SUBJECTS[subject]['label']} session ---")
                for m in msgs:
                    speaker = "Student" if m["role"] == "user" else "Sir ND"
                    transcript_lines.append(f"{speaker}: {m['content']}")
        except Exception as e:
            transcript_lines.append(f"\n[Could not load {subject} history: {e}]")

    transcript = "\n".join(transcript_lines)
    if len(transcript_lines) <= 1:
        return "No chat history found for this student yet."

    prompt = f"Here is the recent tutoring transcript:\n\n{transcript}\n\nPlease write the parent progress report now."

    try:
        response = gemini_client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=REPORT_SYSTEM_INSTRUCTION),
        )
        return response.text
    except Exception as e:
        return f"⚠️ Could not generate report: {e}"


# ==========================================================================
# TIMETABLE ALARM — client-side JS (runs while this tab is open in-browser)
# ==========================================================================
def render_alarm_widget(timetable):
    """Injects a small JS clock that watches the student's target times and
    pops a glowing alert + plays a chime when one is hit. Runs entirely in
    the browser (Web Audio API — no audio file needed). Note: this only
    fires while the Timetable tab is open and the browser tab stays active;
    it depends on the visitor's device clock, and Streamlit reruns will
    reset the JS timer (it just restarts checking, nothing breaks)."""
    schedule = []
    for day, entry in timetable.items():
        if entry.get("target_time") and entry.get("topic"):
            t = entry["target_time"]
            time_str = t.strftime("%H:%M") if hasattr(t, "strftime") else str(t)[:5]
            schedule.append({"day": day, "time": time_str, "topic": entry["topic"]})

    schedule_json = str(schedule).replace("'", '"')

    html_code = f"""
    <div id="sir-nd-alarm-root"></div>
    <style>
    #sir-nd-alert-overlay {{
        display: none;
        position: fixed; inset: 0; z-index: 999999;
        background: rgba(2,4,8,0.88);
        align-items: center; justify-content: center;
        font-family: 'Segoe UI', sans-serif;
    }}
    #sir-nd-alert-box {{
        background: #0d1117;
        border: 2px solid {NEON_CYAN};
        box-shadow: 0 0 25px {NEON_CYAN}, 0 0 55px {NEON_PURPLE};
        border-radius: 16px;
        padding: 32px 40px;
        text-align: center;
        color: #f0f4f8;
        animation: sirnd-pulse 1.2s infinite alternate;
    }}
    @keyframes sirnd-pulse {{
        from {{ box-shadow: 0 0 20px {NEON_CYAN}, 0 0 40px {NEON_PURPLE}; }}
        to   {{ box-shadow: 0 0 35px {NEON_CYAN}, 0 0 70px {NEON_PURPLE}; }}
    }}
    #sir-nd-alert-box h2 {{ color: {NEON_CYAN}; margin: 0 0 8px 0; }}
    #sir-nd-alert-box button {{
        margin-top: 16px; padding: 8px 20px; border-radius: 8px;
        border: 1px solid {NEON_CYAN}; background: transparent; color: #fff;
        cursor: pointer;
    }}
    </style>
    <div id="sir-nd-alert-overlay">
      <div id="sir-nd-alert-box">
        <h2>⏰ Time for class!</h2>
        <p id="sir-nd-alert-msg">Sir ND is waiting for you.</p>
        <button onclick="document.getElementById('sir-nd-alert-overlay').style.display='none'">Dismiss</button>
      </div>
    </div>
    <script>
    const sirNdSchedule = {schedule_json};
    const sirNdFiredKey = "sirNdFiredToday";

    function sirNdPlayChime() {{
        try {{
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const notes = [523.25, 659.25, 783.99, 1046.50];
            notes.forEach((freq, i) => {{
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = "sine";
                osc.frequency.value = freq;
                gain.gain.value = 0.15;
                osc.connect(gain);
                gain.connect(ctx.destination);
                const start = ctx.currentTime + i * 0.18;
                osc.start(start);
                osc.stop(start + 0.35);
            }});
        }} catch (e) {{ console.log("Audio blocked until user interacts with the page:", e); }}
    }}

    function sirNdCheckSchedule() {{
        const now = new Date();
        const dayNames = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
        const currentDay = dayNames[now.getDay()];
        const currentHM = String(now.getHours()).padStart(2,"0") + ":" + String(now.getMinutes()).padStart(2,"0");
        const todayKey = now.toDateString();

        sirNdSchedule.forEach(entry => {{
            if (entry.day === currentDay && entry.time === currentHM) {{
                const firedFlag = todayKey + "-" + entry.day + "-" + entry.time;
                if (sessionStorage.getItem(firedFlag)) return;
                sessionStorage.setItem(firedFlag, "1");
                document.getElementById("sir-nd-alert-msg").innerText =
                    "Time for " + entry.topic + "! Sir ND is waiting for you.";
                document.getElementById("sir-nd-alert-overlay").style.display = "flex";
                sirNdPlayChime();
            }}
        }});
    }}

    setInterval(sirNdCheckSchedule, 15000);
    sirNdCheckSchedule();
    </script>
    """
    components.html(html_code, height=0, width=0)


# ==========================================================================
# UI — HEADER
# ==========================================================================
st.title("🎓 Sir ND")
st.caption("ZIMSEC O-Level AI Tutor — Machipisa Ngonidzashe")

tab_portal, tab_subjects, tab_timetable, tab_admin = st.tabs(
    ["🔐 Student Portal", "💬 Subject Rooms", "🗓️ Timetable & Alarm", "🔒 Parent Admin"]
)

# --------------------------------------------------------------------------
# TAB 1 — STUDENT PORTAL (Sign-up / Login)
# --------------------------------------------------------------------------
with tab_portal:
    if st.session_state.auth_user:
        st.success(f"Logged in as **{st.session_state.auth_user['full_name']}** ({st.session_state.auth_user['email']})")
        if st.button("Log out"):
            sign_out()
            st.rerun()
    else:
        mode = st.radio("", ["Login", "Sign Up"], horizontal=True, label_visibility="collapsed")

        if mode == "Sign Up":
            with st.form("signup_form"):
                full_name = st.text_input("Full name")
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Create account")
            if submitted:
                if not (full_name and email and password):
                    st.error("Please fill in all fields.")
                else:
                    ok, msg = sign_up(email, password, full_name)
                    (st.success if ok else st.error)(msg)
        else:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Log in")
            if submitted:
                ok, msg = sign_in(email, password)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()

# --------------------------------------------------------------------------
# TAB 2 — INTERACTIVE SUBJECT ROOMS
# --------------------------------------------------------------------------
with tab_subjects:
    if not st.session_state.auth_user:
        st.info("Log in from the Student Portal tab to enter the subject rooms.")
    else:
        student_id = st.session_state.auth_user["id"]
        math_tab, science_tab = st.tabs([SUBJECTS["mathematics"]["label"], SUBJECTS["science"]["label"]])

        for subject_key, subject_tab in [("mathematics", math_tab), ("science", science_tab)]:
            with subject_tab:
                for msg in st.session_state.chat_cache[subject_key]:
                    avatar = "🧑‍🎓" if msg["role"] == "user" else "🎓"
                    with st.chat_message(msg["role"], avatar=avatar):
                        st.markdown(msg["content"])

                user_input = st.chat_input(
                    f"Ask Sir ND about {SUBJECTS[subject_key]['label']}...",
                    key=f"chat_input_{subject_key}",
                )
                if user_input:
                    with st.chat_message("user", avatar="🧑‍🎓"):
                        st.markdown(user_input)
                    with st.chat_message("assistant", avatar="🎓"):
                        with st.spinner("Sir ND is thinking..."):
                            reply = send_to_sir_nd(subject_key, student_id, user_input)
                        st.markdown(reply)
                    st.rerun()

# --------------------------------------------------------------------------
# TAB 3 — STUDY TIMETABLE & SMART DESKTOP ALARM
# --------------------------------------------------------------------------
with tab_timetable:
    if not st.session_state.auth_user:
        st.info("Log in from the Student Portal tab to set up your timetable.")
    else:
        student_id = st.session_state.auth_user["id"]
        st.subheader("🗓️ Weekly Study Timetable")
        st.caption("Set a topic and target time for each day. Keep this tab open in your browser and Sir ND will flash a neon alert with a chime when it's time for class.")

        new_timetable = {}
        for day in DAYS_OF_WEEK:
            col1, col2, col3 = st.columns([1, 3, 2])
            entry = st.session_state.timetable.get(day, {"topic": "", "target_time": None})
            with col1:
                st.markdown(f"**{day}**")
            with col2:
                topic = st.text_input(
                    "Topic", value=entry["topic"], key=f"topic_{day}", label_visibility="collapsed",
                    placeholder="e.g. Algebra — simultaneous equations",
                )
            with col3:
                default_time = entry["target_time"]
                if isinstance(default_time, str):
                    try:
                        default_time = datetime.datetime.strptime(default_time[:5], "%H:%M").time()
                    except Exception:
                        default_time = None
                target_time = st.time_input(
                    "Time", value=default_time or datetime.time(16, 0), key=f"time_{day}",
                    label_visibility="collapsed",
                )
            new_timetable[day] = {"topic": topic, "target_time": target_time}

        if st.button("💾 Save Timetable"):
            st.session_state.timetable = new_timetable
            ok, msg = save_timetable(student_id, new_timetable)
            (st.success if ok else st.error)(msg)

        st.divider()
        render_alarm_widget(st.session_state.timetable)
        st.caption("🔔 Alarm is armed for this browser tab. It checks every 15 seconds — leave the tab open for it to fire.")

# --------------------------------------------------------------------------
# TAB 4 — SECURE PARENT ADMIN PANEL
# --------------------------------------------------------------------------
with tab_admin:
    st.subheader("🔒 Parent / Admin Panel")

    if not st.session_state.admin_unlocked:
        admin_input = st.text_input("Enter admin passphrase", type="password", key="admin_phrase_input")
        if st.button("Unlock", key="admin_unlock_btn"):
            if admin_input.strip().lower() == str(ADMIN_PASSPHRASE).strip().lower():
                st.session_state.admin_unlocked = True
                st.rerun()
            else:
                st.error("Incorrect passphrase.")
    else:
        st.success("Admin panel unlocked ✅")
        admin_client = get_supabase_admin_client()
        if admin_client is None:
            st.error(
                "⚠️ `SUPABASE_SERVICE_ROLE_KEY` is not set in secrets, so the "
                "admin panel can't bypass student-level row security to look "
                "up a student by name. Add it in Settings → Secrets."
            )
        else:
            student_name_input = st.text_input("Student's full name (as entered at sign-up)")
            if st.button("📄 Generate Progress Report", key="gen_report_btn"):
                if not student_name_input.strip():
                    st.error("Enter the student's name first.")
                else:
                    with st.spinner("Looking up student and asking Sir ND to write the report..."):
                        try:
                            profile_rows = (
                                admin_client.table("profiles")
                                .select("id, full_name")
                                .ilike("full_name", student_name_input.strip())
                                .execute()
                            )
                        except Exception as e:
                            profile_rows = None
                            st.error(f"Lookup failed: {e}")

                    if profile_rows and profile_rows.data:
                        matched = profile_rows.data[0]
                        st.session_state.last_report = generate_parent_report(
                            matched["full_name"], matched["id"], admin_client
                        )
                    elif profile_rows is not None:
                        st.warning("No student found with that exact name.")

            if st.session_state.last_report:
                st.text_area("Progress Report", value=st.session_state.last_report, height=320)
                st.download_button(
                    "⬇️ Download report as .txt",
                    data=st.session_state.last_report,
                    file_name=f"progress_report_{datetime.date.today().isoformat()}.txt",
                    mime="text/plain",
                )

        if st.button("🔒 Lock admin panel", key="admin_lock_btn"):
            st.session_state.admin_unlocked = False
            st.session_state.last_report = None
            st.rerun()
