from __future__ import annotations

import base64
import os
import uuid
from pathlib import Path

import httpx
import streamlit as st

from ui_contract import API_PATHS, load_personas, select_persona


API_URL = os.getenv("API_URL", "http://localhost:8000")
_ASSETS = Path(__file__).parent / "assets"


def _encode_image(path: Path) -> tuple[str, str]:
    """Return (base64_data, mime_subtype) for a local image file."""
    ext = path.suffix.lstrip(".").lower()
    mime = "jpeg" if ext == "jpg" else ext
    return base64.b64encode(path.read_bytes()).decode(), mime


def _inject_custom_theme(compact_layout: bool = False) -> None:
    bg_path = _ASSETS / "xts_bg.jpeg"

    bg_css = ""
    if bg_path.is_file():
        bg_data, bg_mime = _encode_image(bg_path)
        bg_css = (
            '.stApp, [data-testid="stAppViewContainer"] {'
            "  background: linear-gradient("
            "    rgba(15, 23, 42, 0.80),"
            "    rgba(15, 23, 42, 0.75)"
            "  ),"
            f'  url("data:image/{bg_mime};base64,{bg_data}") !important;'
            "  background-size: cover !important;"
            "  background-position: center !important;"
            "  background-repeat: no-repeat !important;"
            "  background-attachment: fixed !important;"
            "}"
            ' [data-testid="stHeader"],'
            ' [data-testid="stAppViewBlockContainer"],'
            " .main .block-container {"
            "  background-color: transparent !important;"
            "}"
        )

    # Static CSS that contains # (hex colors) and literal braces —
    # kept as a plain string so Python does not parse it as an f-string.
    static_css = r"""
        /* ── Global typography on dark overlay ── */
        .stApp, .stApp [data-testid="stMarkdown"] p,
        .stApp [data-testid="stMarkdown"] li {
            color: #e2e8f0;
        }
        .stApp h1, .stApp h2, .stApp h3 {
            color: #f8fafc;
            text-shadow: 0 1px 6px rgba(0,0,0,0.45);
        }
        .stApp [data-testid="stCaptionContainer"] {
            color: #94a3b8;
        }

        /* ── Brand logo styling in sidebar ── */
        [data-testid="stImage"] img {
            filter: drop-shadow(0 2px 10px rgba(0,0,0,0.5));
        }
        section[data-testid="stSidebar"] [data-testid="stImage"] {
            text-align: center;
            padding: 0.5rem 0 0.75rem 0;
        }

        /* ── Loading indicators ── */
        [data-testid="stStatusWidget"], .stStatusWidget {
            visibility: visible !important;
            display: inline-flex !important;
            align-items: center !important;
            gap: 8px !important;
            padding: 6px 14px !important;
            background: rgba(15, 23, 42, 0.95) !important;
            border: 2px solid #38bdf8 !important;
            border-radius: 9999px !important;
            box-shadow: 0 0 16px rgba(56, 189, 248, 0.65),
                        inset 0 0 8px rgba(56, 189, 248, 0.25) !important;
            backdrop-filter: blur(8px) !important;
            animation: statusPulse 1.8s infinite ease-in-out !important;
            z-index: 999999 !important;
        }
        @keyframes statusPulse {
            0%, 100% {
                box-shadow: 0 0 12px rgba(56, 189, 248, 0.5),
                            inset 0 0 6px rgba(56, 189, 248, 0.2);
                border-color: #38bdf8;
            }
            50% {
                box-shadow: 0 0 24px rgba(56, 189, 248, 0.9),
                            inset 0 0 12px rgba(56, 189, 248, 0.4);
                border-color: #7dd3fc;
            }
        }
        [data-testid="stStatusWidget"] svg, .stStatusWidget svg {
            fill: #38bdf8 !important;
            stroke: #38bdf8 !important;
            filter: drop-shadow(0 0 4px rgba(56, 189, 248, 0.8)) !important;
        }
        [data-testid="stStatusWidget"] [data-testid="stStatusWidgetRunningIcon"],
        [data-testid="stStatusWidget"] [data-testid="stStatusWidgetRunningManIcon"] {
            filter: drop-shadow(0 0 8px #38bdf8) !important;
        }
        [data-testid="stStatusWidget"] * {
            color: #f0f9ff !important;
            font-weight: 600 !important;
        }

        /* Top-edge animated loading bar */
        [data-testid="stHeader"]:has([data-testid="stStatusWidget"])::before {
            content: "";
            position: fixed;
            top: 0; left: 0; right: 0;
            height: 3px;
            background: linear-gradient(90deg, #38bdf8, #818cf8, #38bdf8, #06b6d4);
            background-size: 200% 100%;
            animation: topBarLoading 1.2s linear infinite;
            z-index: 999999;
        }
        @keyframes topBarLoading {
            0%   { background-position: 200% 0; }
            100% { background-position: -200% 0; }
        }

        /* In-page spinner */
        [data-testid="stSpinner"], .stSpinner {
            background: rgba(15, 23, 42, 0.9) !important;
            border: 1.5px solid rgba(56, 189, 248, 0.5) !important;
            border-radius: 12px !important;
            padding: 0.9rem 1.4rem !important;
            box-shadow: 0 6px 24px rgba(0,0,0,0.4),
                        0 0 16px rgba(56, 189, 248, 0.3) !important;
            backdrop-filter: blur(8px) !important;
            margin: 1rem 0 !important;
        }
        [data-testid="stSpinner"] > div, .stSpinner > div {
            border-top-color: #38bdf8 !important;
        }
        [data-testid="stSpinner"] span, .stSpinner span {
            color: #f0f9ff !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            letter-spacing: 0.3px !important;
        }

        /* ── Sidebar ── */
        section[data-testid="stSidebar"] {
            background: rgba(15, 23, 42, 0.92) !important;
            border-right: 1px solid rgba(100, 116, 139, 0.3) !important;
        }
        section[data-testid="stSidebar"] * {
            color: #cbd5e1 !important;
        }

        /* ── Tabs ── */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            background: rgba(30, 41, 59, 0.7);
            border-radius: 8px 8px 0 0;
            color: #94a3b8;
            padding: 0.5rem 1.2rem;
            border: 1px solid rgba(100, 116, 139, 0.25);
            border-bottom: none;
            transition: background 0.2s, color 0.2s;
        }
        .stTabs [aria-selected="true"] {
            background: rgba(51, 65, 85, 0.85) !important;
            color: #f1f5f9 !important;
            font-weight: 600;
        }

        /* ── Buttons ── */
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #3b82f6, #2563eb);
            border: none;
            border-radius: 8px;
            color: #fff;
            font-weight: 600;
            padding: 0.5rem 1.6rem;
            transition: transform 0.15s, box-shadow 0.15s;
        }
        .stButton > button[kind="primary"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 14px rgba(37, 99, 235, 0.45);
        }
        .stButton > button {
            border-radius: 8px;
        }

        /* ── Cards: expanders, alerts, metric containers ── */
        [data-testid="stExpander"] {
            background: rgba(30, 41, 59, 0.75);
            border: 1px solid rgba(100, 116, 139, 0.3);
            border-radius: 10px;
            backdrop-filter: blur(6px);
        }
        .stAlert {
            background: rgba(30, 41, 59, 0.7) !important;
            border-radius: 8px;
            border-left: 4px solid #3b82f6;
        }
        [data-testid="stMetric"] {
            background: rgba(30, 41, 59, 0.72);
            border: 1px solid rgba(100, 116, 139, 0.25);
            border-radius: 10px;
            padding: 0.8rem 1rem;
            backdrop-filter: blur(4px);
        }
        [data-testid="stMetric"] label {
            color: #94a3b8 !important;
        }
        [data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: #e2e8f0 !important;
        }

        /* ── Text area & inputs ── */
        .stTextArea textarea, .stTextInput input {
            background: rgba(30, 41, 59, 0.8) !important;
            color: #e2e8f0 !important;
            border: 1px solid rgba(100, 116, 139, 0.35);
            border-radius: 8px;
        }
        .stTextArea textarea::placeholder, .stTextInput input::placeholder {
            color: #64748b !important;
        }

        /* ── Dataframe ── */
        [data-testid="stDataFrame"] {
            border-radius: 8px;
            overflow: hidden;
        }

        /* ── LLM answer container ── */
        .llm-answer-box {
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid rgba(100, 116, 139, 0.35);
            border-radius: 8px;
            padding: 1rem 1.2rem;
            color: #e2e8f0;
            line-height: 1.65;
            backdrop-filter: blur(4px);
            margin: 0.5rem 0 0.75rem 0;
        }
        .llm-answer-box p { margin: 0.4em 0; }
        .llm-answer-box strong { color: #f1f5f9; }
        .llm-answer-box code {
            background: rgba(51, 65, 85, 0.6);
            padding: 0.15em 0.4em;
            border-radius: 4px;
            font-size: 0.9em;
        }
    """

    if compact_layout:
        static_css += r"""
        /* Bring the brand and tabs close to the top only after chat starts,
           without expanding the height of the main page. */
        [data-testid="stMainBlockContainer"],
        .main .block-container,
        [data-testid="stAppViewBlockContainer"] {
            padding-top: 0.75rem !important;
            padding-bottom: 0.5rem !important;
        }
        [data-testid="stHeading"] {
            margin-top: -0.75rem !important;
            margin-bottom: 0.1rem !important;
        }
        [data-testid="stHeading"] h1,
        [data-testid="stHeading"] h1 span {
            margin: 0 !important;
            padding: 0 !important;
            line-height: 1.1 !important;
            position: static !important;
        }
        [data-testid="stCaptionContainer"] {
            margin: -0.35rem 0 0.25rem 0 !important;
        }
        """

    st.markdown(
        "<style>" + bg_css + static_css + "</style>",
        unsafe_allow_html=True,
    )


def request(method: str, path: str, token: str, **kwargs):
    headers = {"Authorization": f"Bearer {token}"}
    response = httpx.request(method, f"{API_URL}{path}", headers=headers, timeout=40, **kwargs)
    if response.is_error:
        detail = response.json().get("detail", response.text)
        st.error(f"API {response.status_code}: {detail}")
        return None
    return response.json()


st.set_page_config(page_title="OnCall-HR-ADMO", page_icon="⌬", layout="wide")
_inject_custom_theme(compact_layout=bool(st.session_state.get("chat_history")))

_logo_file = _ASSETS / "text_logo2.png"
if _logo_file.is_file():
    st.sidebar.image(str(_logo_file), width="stretch")

personas = load_personas(Path(__file__).with_name("demo_personas.json"))
persona = st.sidebar.selectbox("Persona demo", personas, format_func=lambda item: item["label"])
select_persona(st.session_state, persona)
st.sidebar.caption(persona["scenario"])
token = persona["demo_token"]

st.title("꥟ OnCall-HR")
st.caption("Asisten Kebijakan HR dan Cuti")

chat_tab, leave_tab, monitor_tab = st.tabs(["Percakapan", "Permintaan Cuti", "Monitoring"])

with chat_tab:
    # ── Header Tab: Keterangan status & Tombol Reset ──
    if st.session_state.get("chat_history"):
        header_col1, header_col2 = st.columns([0.7, 0.3])
        with header_col2:
            if st.button("Mulai percakapan baru", key="btn_reset_chat", use_container_width=True):
                st.session_state.pop("chat_history", None)
                st.session_state.pop("conversation_id", None)
                st.rerun()

    history = st.session_state.get("chat_history", [])

    # ── 1. Placeholder untuk Container Pesan ──
    # Menggunakan st.empty() agar ketika riwayat obrolan masih kosong,
    # tidak ada kotak container yang muncul dan textfield langsung menempati posisi teratas.
    chat_placeholder = st.empty()
    chat_container = None

    # Render pesan riwayat hanya jika sudah ada riwayat obrolan
    if history:
        chat_container = chat_placeholder.container(height=560)
        with chat_container:
            for entry in history:
                with st.chat_message(entry["role"]):
                    st.markdown(entry["content"])
                    if entry["role"] == "assistant" and entry.get("citations"):
                        with st.expander("Sumber kebijakan"):
                            for citation in entry["citations"]:
                                st.markdown(f"**{citation['document_id']} — {citation['section']}**")
                                st.write(citation["excerpt"])
                    if entry["role"] == "assistant" and entry.get("proposal"):
                        proposal = entry["proposal"]
                        st.warning("⚠️ Tindakan belum dijalankan. Periksa detail lalu konfirmasikan.")
                        col1, col2 = st.columns(2)
                        col1.markdown(f"**Tipe cuti:** {proposal['leave_type']}")
                        col1.markdown(f"**Mulai:** {proposal['start_date']}")
                        col2.markdown(f"**Selesai:** {proposal['end_date']}")
                        col2.markdown(f"**Hari kerja:** {proposal['business_days']}")
                        if proposal.get("validation_summary"):
                            st.info(" · ".join(proposal["validation_summary"]))
                        key_name = f"idem_{proposal['proposal_id']}"
                        st.session_state.setdefault(key_name, str(uuid.uuid4()))
                        if st.button("✅ Konfirmasi pengajuan cuti", key=f"confirm_{proposal['proposal_id']}"):
                            with st.spinner("Mengonfirmasi tindakan..."):
                                confirmed = request(
                                    "POST",
                                    API_PATHS["confirm"].format(proposal_id=proposal["proposal_id"]),
                                    token,
                                    json={"idempotency_key": st.session_state[key_name]},
                                )
                                if confirmed:
                                    st.success(f"✅ Permintaan {confirmed['request_id']} berstatus {confirmed['status']}.")

    # ── 2. Textfield Input (Berada di atas jika kosong, stick di bawah container jika aktif) ──
    message = st.chat_input("Pertanyaan atau permintaan, contoh: Berapa saldo cuti saya?")
    if message:
        st.session_state.setdefault("chat_history", []).append({"role": "user", "content": message})

        # Jika container belum dibuat (giliran pertama), inisialisasi di dalam placeholder
        if chat_container is None:
            chat_container = chat_placeholder.container(height=560)

        # Pesan baru pengguna dan asisten dirender KE DALAM chat_container, di atas input
        with chat_container:
            with st.chat_message("user"):
                st.markdown(message)

            conversation_id = st.session_state.get("conversation_id")
            with st.chat_message("assistant"):
                with st.spinner("Sedang memproses..."):
                    payload: dict = {"message": message}
                    if conversation_id:
                        payload["conversation_id"] = conversation_id
                    result = request("POST", API_PATHS["chat"], token, json=payload)
                if result:
                    # Simpan conversation_id untuk percakapan berikutnya
                    st.session_state["conversation_id"] = result.get("conversation_id")
                    # Simpan ke riwayat sesi lalu rerun agar header tombol reset dan pesan ter-render sinkron
                    history_entry: dict = {
                        "role": "assistant",
                        "content": result["answer"],
                        "citations": result.get("citations", []),
                        "proposal": result.get("action_proposal"),
                    }
                    st.session_state["chat_history"].append(history_entry)
                    st.rerun()
                else:
                    st.error("Gagal mendapatkan respons dari asisten.")

with leave_tab:
#     with st.expander("Ajukan Permintaan Cuti", expanded=False):
#         st.info(
#             "Isi formulir di bawah lalu klik **Ajukan via Obrolan**. "
#             "Asisten akan menyiapkan proposal — Anda perlu mengkonfirmasinya di tab Percakapan."
#         )

#         with st.form("leave_form"):
#             col_a, col_b = st.columns(2)
#             start_date = col_a.date_input("Tanggal mulai cuti")
#             end_date = col_b.date_input("Tanggal selesai cuti")
#             leave_type = st.selectbox(
#                 "Tipe cuti",
#                 options=["annual", "sick", "parental"],
#                 format_func=lambda x: {"annual": "Tahunan", "sick": "Sakit", "parental": "Orang Tua"}[x],
#             )
#             reason = st.text_input("Alasan (opsional)", max_chars=300)
#             submitted = st.form_submit_button("Ajukan via Obrolan", type="primary")

#         if submitted:
#             type_label = {"annual": "tahunan", "sick": "sakit", "parental": "orang tua"}[leave_type]
#             chat_message = (
#                 f"Siapkan cuti {type_label} mulai {start_date} sampai {end_date}"
#                 + (f". Alasan: {reason}" if reason else "")
#             )
#             st.session_state.setdefault("chat_history", []).append({"role": "user", "content": chat_message})
#             conversation_id = st.session_state.get("conversation_id")
#             with st.spinner("Mengirim permintaan ke asisten..."):
#                 payload = {"message": chat_message}
#                 if conversation_id:
#                     payload["conversation_id"] = conversation_id
#                 result = request("POST", API_PATHS["chat"], token, json=payload)
#             if result:
#                 st.session_state["conversation_id"] = result.get("conversation_id")
#                 history_entry = {
#                     "role": "assistant",
#                     "content": result["answer"],
#                     "citations": result.get("citations", []),
#                     "proposal": result.get("action_proposal"),
#                 }
#                 st.session_state["chat_history"].append(history_entry)
#                 if result.get("action_proposal"):
#                     st.success("✅ Proposal cuti disiapkan. Buka tab **Percakapan** untuk mengkonfirmasinya.")
#                 else:
#                     st.warning(result["answer"])

    # st.divider()
    st.subheader("Riwayat Permintaan Saya")
    if st.button("Riwayat Pengajuan"):
        with st.spinner("Memuat data permintaan cuti..."):
            data = request("GET", API_PATHS["my_requests"], token)
            if data is not None:
                if data:
                    st.dataframe(data, use_container_width=True)
                else:
                    st.info("Belum ada permintaan cuti yang tercatat.")

with monitor_tab:
    st.info("Gunakan token monitoring admin untuk membuka metrik dan alert agregat.")
    if st.button("Muat monitoring"):
        with st.spinner("Memuat monitoring..."):
            summary = request("GET", API_PATHS["monitoring_summary"], token)
            alerts = request("GET", API_PATHS["monitoring_alerts"], token)
            if summary:
                columns = st.columns(4)
                columns[0].metric("Runs", summary["run_count"])
                columns[1].metric("Error rate", f"{float(summary['error_rate']):.1%}")
                columns[2].metric("p95 latency", f"{int(summary['p95_latency_ms'])} ms")
                columns[3].metric("Tool calls", summary["tool_calls"])
            if alerts is not None:
                st.subheader("Alert aktif")
                st.json(alerts)


