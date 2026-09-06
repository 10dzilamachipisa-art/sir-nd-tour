"""
Sir ND by Machipisa Ngonidzashe
A ZIMSEC O-Level AI Tutor built with Streamlit + Google Gemini 1.5 Flash.

Run locally:
    streamlit run app.py

Deploy: see DEPLOYMENT.md
"""

import io
import datetime
import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader

# --------------------------------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Sir ND | ZIMSEC AI Tutor",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------
# CONSTANTS
# --------------------------------------------------------------------------
MODEL_NAME = "gemini-1.5-flash"

SYSTEM_INSTRUCTION = """
You are "Sir ND" (full name: Machipisa Ngonidzashe), a warm, authoritative, and deeply
encouraging Zimbabwean secondary school teacher. You tutor ZIMSEC O-Level candidates
across all subjects (Mathematics, Combined Science, Biology, Chemistry, Physics,
English Language, Shona, History, Geography, Business Studies, Accounts, Commerce,
Agriculture, etc.), strictly aligned to the current ZIMSEC syllabus.

YOUR TEACHING PHILOSOPHY (non-negotiable rules):
1. NEVER give a direct final answer to a homework question, past exam question, or
   assignment on the first ask. Instead, you guide the student using the Socratic
   method: ask a leading question, give a hint, break the problem into the first
   small step, and let the student attempt the next step themselves.
   - Exception: if the student has genuinely attempted the problem multiple times
     and is still stuck after your hints, you may reveal the answer, but ONLY after
     walking through the full reasoning/method first, so they understand the "why".
   - You may always give direct answers to conceptual "what is / define / explain"
     questions that are not graded homework/exam items.
2. Teach in SHORT, BITE-SIZED, MOBILE-FRIENDLY chunks. Most students are on cheap
   Android phones with small screens and expensive data bundles.
   - Keep each message under ~120 words unless a worked example truly needs more.
   - Use short paragraphs (1-3 sentences), numbered or bulleted steps, and blank
     lines between ideas. Avoid giant walls of text.
   - End most explanations with ONE simple follow-up question to check
     understanding before moving on.
3. Use LOCAL ZIMBABWEAN CONTEXT AND EXAMPLES wherever possible:
   - Money problems: use ZiG/USD, mombe (cattle), mealie-meal, kombis, tuck-shops,
     vendors at Mbare Musika, airtime/ecocash, school fees in USD.
   - Science/geography examples: Kariba Dam, Victoria Falls, Great Zimbabwe,
     Eastern Highlands, maize/tobacco/cotton farming, load-shedding, gold panning.
   - History: pre-colonial kingdoms, the Chimurenga wars, independence in 1980.
   - Keep examples respectful, realistic, and appropriate for a teenage audience.
4. ZIMSEC ALIGNMENT: Frame explanations the way ZIMSEC marking schemes reward —
   command words (state, describe, explain, discuss, calculate, evaluate), showing
   full working for calculations (method marks matter as much as the final answer),
   and correct terminology in English (or Shona, if the student asks in Shona).
5. TONE: Firm but warm, like a teacher who genuinely wants the student to pass and
   believes they can. Encourage effort. Never mock a wrong answer — correct it
   kindly and explain the misconception. Use "well done", "beautiful effort",
   "let's try again together" type encouragement, in a natural, not over-the-top way.
6. If reference material has been uploaded (textbook excerpts, past exam papers,
   notes), you MUST ground your teaching in that material first before relying on
   your general knowledge, and mention when you're drawing from "your uploaded
   notes/past paper".
7. Stay in character as Sir ND at all times. Do not mention that you are an AI
   language model, Gemini, or Google unless the student directly asks how you work,
   in which case you may briefly explain you are an AI tutor built for them, then
   return to teaching.
"""

REPORT_SYSTEM_INSTRUCTION = """
You are an academic report-writing assistant working for "Sir ND", a ZIMSEC
O-Level tutor. Given a transcript of a tutoring chat session between Sir ND and a
student, write a short, formal, professional progress report addressed to the
student's PARENT/GUARDIAN. The report must:
- Open with a polite greeting to the parent/guardian.
- Summarize which subject(s)/topics were covered in the session.
- Give an honest but constructive assessment of the student's understanding,
  effort, and areas of strength.
- Clearly flag any topics/concepts where the student struggled and needs more
  practice at home.
- Suggest 1-3 concrete next steps or home revision activities.
- Close with an encouraging, respectful sign-off from "Sir ND (Machipisa
  Ngonidzashe)".
- Keep it to roughly 200-350 words, in formal written English, no slang, no markdown
  headers beyond simple paragraphs — this is going to be read/printed for a parent.
"""

MAX_KB_CHARS = 60_000  # cap knowledge-base text injected into prompts

# --------------------------------------------------------------------------
# SESSION STATE INIT
# --------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {"role": "user"/"assistant", "content": str}

if "knowledge_base" not in st.session_state:
    st.session_state.knowledge_base = ""  # combined text extracted from uploads

if "kb_filenames" not in st.session_state:
    st.session_state.kb_filenames = []

if "admin_unlocked" not in st.session_state:
    st.session_state.admin_unlocked = False

if "last_report" not in st.session_state:
    st.session_state.last_report = None


# --------------------------------------------------------------------------
# GEMINI SETUP
# --------------------------------------------------------------------------
def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return None


def get_admin_passphrase():
    # Falls back to a default if not set in secrets, but strongly recommend
    # setting ADMIN_PASSPHRASE in st.secrets for a real deployment.
    try:
        return st.secrets["ADMIN_PASSPHRASE"]
    except Exception:
        return "sir nd report"  # default fallback phrase


API_KEY = get_api_key()

if not API_KEY:
    st.error(
        "⚠️ GEMINI_API_KEY not found in Streamlit secrets. "
        "Add it under Settings → Secrets before using Sir ND."
    )
    st.stop()

genai.configure(api_key=API_KEY)


@st.cache_resource(show_spinner=False)
def load_tutor_model():
    return genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=SYSTEM_INSTRUCTION,
    )


@st.cache_resource(show_spinner=False)
def load_report_model():
    return genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=REPORT_SYSTEM_INSTRUCTION,
    )


tutor_model = load_tutor_model()
report_model = load_report_model()


# --------------------------------------------------------------------------
# FILE / KNOWLEDGE BASE HELPERS
# --------------------------------------------------------------------------
def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception as e:
        return f"[Could not read PDF: {e}]"


def extract_text_from_txt(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        return f"[Could not read text file: {e}]"


def add_files_to_knowledge_base(uploaded_files):
    added = []
    for f in uploaded_files:
        if f.name in st.session_state.kb_filenames:
            continue  # skip duplicates already ingested
        raw = f.read()
        if f.name.lower().endswith(".pdf"):
            text = extract_text_from_pdf(raw)
        else:
            text = extract_text_from_txt(raw)

        st.session_state.knowledge_base += (
            f"\n\n--- BEGIN DOCUMENT: {f.name} ---\n{text}\n--- END DOCUMENT: {f.name} ---\n"
        )
        st.session_state.kb_filenames.append(f.name)
        added.append(f.name)

    # Trim from the front if it grows too large (keep most recent material)
    if len(st.session_state.knowledge_base) > MAX_KB_CHARS:
        st.session_state.knowledge_base = st.session_state.knowledge_base[-MAX_KB_CHARS:]

    return added


def build_prompt_with_context(user_message: str) -> str:
    """Prefix the user's message with knowledge-base context, if any."""
    if not st.session_state.knowledge_base.strip():
        return user_message

    return (
        "The student has uploaded the following reference material "
        "(textbook excerpts / past papers / notes). Use it as your primary "
        "source when relevant, and mention when you're drawing on it:\n"
        f"{st.session_state.knowledge_base}\n\n"
        "--- END OF REFERENCE MATERIAL ---\n\n"
        f"Student's message: {user_message}"
    )


def gemini_chat_history():
    """Convert session_state.messages into Gemini's expected history format."""
    history = []
    for m in st.session_state.messages:
        role = "user" if m["role"] == "user" else "model"
        history.append({"role": role, "parts": [m["content"]]})
    return history


# --------------------------------------------------------------------------
# REPORT GENERATION
# --------------------------------------------------------------------------
def generate_parent_report() -> str:
    if not st.session_state.messages:
        return "No chat history yet — the student hasn't started a session."

    transcript_lines = []
    for m in st.session_state.messages:
        speaker = "Student" if m["role"] == "user" else "Sir ND"
        transcript_lines.append(f"{speaker}: {m['content']}")
    transcript = "\n".join(transcript_lines)

    prompt = (
        "Here is the full tutoring session transcript:\n\n"
        f"{transcript}\n\n"
        "Please write the parent progress report now."
    )

    try:
        response = report_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ Could not generate report: {e}"


# --------------------------------------------------------------------------
# SIDEBAR — KNOWLEDGE BASE + ADMIN PANEL
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🎓 Sir ND")
    st.caption("Machipisa Ngonidzashe — Your ZIMSEC AI Tutor")

    st.divider()

    # ---- Knowledge base upload ----
    st.markdown("### 📚 Knowledge Base")
    st.caption("Upload textbook excerpts or past ZIMSEC papers (PDF or TXT).")
    uploaded_files = st.file_uploader(
        "Upload notes / past papers",
        type=["pdf", "txt"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    if uploaded_files:
        newly_added = add_files_to_knowledge_base(uploaded_files)
        if newly_added:
            st.success(f"Added: {', '.join(newly_added)}")

    if st.session_state.kb_filenames:
        st.caption("Currently loaded:")
        for name in st.session_state.kb_filenames:
            st.write(f"• {name}")
        if st.button("🗑️ Clear knowledge base", use_container_width=True):
            st.session_state.knowledge_base = ""
            st.session_state.kb_filenames = []
            st.rerun()

    st.divider()

    # ---- Admin / Parent panel ----
    st.markdown("### 🔒 Parent / Admin Panel")

    if not st.session_state.admin_unlocked:
        admin_input = st.text_input(
            "Enter admin phrase to unlock",
            type="password",
            key="admin_phrase_input",
        )
        if st.button("Unlock", use_container_width=True):
            if admin_input.strip().lower() == get_admin_passphrase().strip().lower():
                st.session_state.admin_unlocked = True
                st.rerun()
            else:
                st.error("Incorrect phrase.")
    else:
        st.success("Admin panel unlocked ✅")
        st.caption(f"Messages in current session: {len(st.session_state.messages)}")

        if st.button("📄 Generate Parent Progress Report", use_container_width=True):
            with st.spinner("Sir ND is writing the report..."):
                st.session_state.last_report = generate_parent_report()

        if st.session_state.last_report:
            st.text_area(
                "Progress Report",
                value=st.session_state.last_report,
                height=300,
            )
            st.download_button(
                "⬇️ Download report as .txt",
                data=st.session_state.last_report,
                file_name=f"progress_report_{datetime.date.today().isoformat()}.txt",
                mime="text/plain",
                use_container_width=True,
            )

        if st.button("🔒 Lock admin panel", use_container_width=True):
            st.session_state.admin_unlocked = False
            st.session_state.last_report = None
            st.rerun()

    st.divider()
    if st.button("🧹 Clear chat history", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


# --------------------------------------------------------------------------
# MAIN CHAT UI
# --------------------------------------------------------------------------
st.title("🎓 Sir ND")
st.caption("Your ZIMSEC O-Level AI Tutor — ask a question to get started, mudiwa wangu!")

# Render existing conversation
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="🧑‍🎓" if message["role"] == "user" else "🎓"):
        st.markdown(message["content"])

# Chat input
user_input = st.chat_input("Ask Sir ND anything about your ZIMSEC subjects...")

if user_input:
    # Show + store user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧑‍🎓"):
        st.markdown(user_input)

    # Build history for Gemini (everything EXCEPT the message we're about to send)
    history_for_model = gemini_chat_history()[:-1]

    prompt = build_prompt_with_context(user_input)

    with st.chat_message("assistant", avatar="🎓"):
        placeholder = st.empty()
        full_reply = ""
        try:
            chat_session = tutor_model.start_chat(history=history_for_model)
            response_stream = chat_session.send_message(prompt, stream=True)
            for chunk in response_stream:
                if chunk.text:
                    full_reply += chunk.text
                    placeholder.markdown(full_reply + "▌")
            placeholder.markdown(full_reply)
        except Exception as e:
            full_reply = f"⚠️ Sorry, I hit an error talking to Gemini: {e}"
            placeholder.markdown(full_reply)

    st.session_state.messages.append({"role": "assistant", "content": full_reply})
