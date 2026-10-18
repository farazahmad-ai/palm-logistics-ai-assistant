"""Streamlit interface for the Palm Logistics AI assistant."""

import json
import os
import sys
import urllib.parse
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, ToolMessage
from sqlalchemy import create_engine, text


# This must be the first Streamlit command executed by the UI script.
st.set_page_config(
    page_title="Palm Logistics Operations Console",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Project and environment setup
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from src.orchestrator import AGENT_MODEL, palm_agent  # noqa: E402


def _required_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    raise ValueError(f"Missing required environment variable: {' or '.join(names)}")


SQL_SERVER_HOST = os.getenv("SQL_SERVER_HOST", "127.0.0.1").strip()
SQL_SERVER_PORT = os.getenv("SQL_SERVER_PORT", "1433").strip()
SQL_SERVER_DATABASE = os.getenv("SQL_SERVER_DATABASE", "PalmLogistics").strip()
SQL_READER_USER = _required_env("SQL_READ_ONLY_USER", "SQL_Read_only_User")
SQL_READER_PASSWORD = _required_env(
    "SQL_READ_ONLY_PASSWORD", "palm_logistics_reader_password"
)
SQL_ENCRYPT = os.getenv("SQL_ENCRYPT", "no").strip()
SQL_TRUST_SERVER_CERTIFICATE = os.getenv(
    "SQL_TRUST_SERVER_CERTIFICATE", "yes"
).strip()


def _create_sql_engine(username: str, password: str):
    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={SQL_SERVER_HOST},{SQL_SERVER_PORT};"
        f"DATABASE={SQL_SERVER_DATABASE};"
        f"UID={username};"
        f"PWD={password};"
        f"Encrypt={SQL_ENCRYPT};"
        f"TrustServerCertificate={SQL_TRUST_SERVER_CERTIFICATE};"
    )
    params = urllib.parse.quote_plus(connection_string)
    return create_engine(
        f"mssql+pyodbc:///?odbc_connect={params}",
        pool_pre_ping=True,
    )


@st.cache_resource(show_spinner=False)
def get_audit_write_engine():
    """Reuse the reader's SQL connection pool across Streamlit reruns."""
    return _create_sql_engine(SQL_READER_USER, SQL_READER_PASSWORD)


audit_write_engine = get_audit_write_engine()


def write_audit_log(
    session_id: str,
    node_name: str,
    tool_name: str | None,
    content: str,
) -> None:
    """Append one parameterized event to the Palm Logistics audit table."""
    try:
        with audit_write_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO [dbo].[AgentAuditLog]
                        ([SessionID], [NodeExecuted], [ToolName], [Content])
                    VALUES
                        (:session_id, :node_name, :tool_name, :content)
                    """
                ),
                {
                    "session_id": session_id,
                    "node_name": node_name,
                    "tool_name": tool_name,
                    "content": content,
                },
            )
    except Exception as exc:
        # Observability failure must not break the dispatcher conversation.
        print(f"Palm Logistics audit logging failed: {exc}")


# ---------------------------------------------------------------------------
# Theme and session state
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
        .stApp { background-color: #0B0E14; color: #E2E8F0; }
        div[data-testid="stSidebar"] {
            background-color: #111622;
            border-right: 1px solid #1E293B;
        }
        .stMarkdown code {
            background-color: #1E293B !important;
            color: #38BDF8 !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "ui_messages" not in st.session_state:
    st.session_state.ui_messages = []

thread_config = {
    "configurable": {"thread_id": st.session_state.thread_id}
}

DISPATCH_MODE = "🚚 Dispatch Console"
AUDIT_MODE = "🛡️ Audit Logs"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("Palm Logistics")
    st.caption("AI Operations Command Center")

    app_mode = st.radio("System mode", [DISPATCH_MODE, AUDIT_MODE])

    st.markdown("---")
    st.caption(f"Session: `{st.session_state.thread_id[:8]}...`")
    st.markdown(f"**Agent model:** `{AGENT_MODEL}`")

    st.markdown("---")
    if st.button("Clear conversation", use_container_width=True):
        st.session_state.ui_messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()


# ---------------------------------------------------------------------------
# Dispatcher chat
# ---------------------------------------------------------------------------
if app_mode == DISPATCH_MODE:
    st.title("Palm Logistics Operations Console")
    st.caption("Operational telemetry, SOP guidance, and corridor context")

    for entry in st.session_state.ui_messages:
        avatar = "👤" if entry["role"] == "user" else "🤖"
        with st.chat_message(entry["role"], avatar=avatar):
            for trace in entry.get("traces", []):
                if trace["type"] == "tool_input":
                    st.markdown(f"**Tool request:** `{trace['name']}`")
                    with st.expander(
                        f"View generated input ({trace['name']})",
                        expanded=False,
                    ):
                        st.json(trace["args"])
                elif trace["type"] == "tool_output":
                    with st.expander(
                        f"View tool output ({trace['name']})",
                        expanded=False,
                    ):
                        st.code(trace["content"], language="text")
            st.markdown(entry["content"])

    if user_input := st.chat_input(
        "Ask about logistics telemetry, risks, or Palm Logistics policy..."
    ):
        st.session_state.ui_messages.append(
            {"role": "user", "content": user_input}
        )

        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)

        write_audit_log(
            session_id=st.session_state.thread_id,
            node_name="user_input",
            tool_name=None,
            content=user_input,
        )

        with st.chat_message("assistant", avatar="🤖"):
            final_response = ""
            current_traces = []

            try:
                with st.status(
                    "Investigating request...",
                    expanded=True,
                ) as status:
                    events = palm_agent.stream(
                        {"messages": [HumanMessage(content=user_input)]},
                        config=thread_config,
                        stream_mode="updates",
                    )

                    for event in events:
                        for node_name, node_state in event.items():
                            if node_name == "reasoner":
                                latest_message = node_state["messages"][-1]

                                for tool_call in getattr(
                                    latest_message, "tool_calls", []
                                ):
                                    status.update(
                                        label="Retrieving operational evidence..."
                                    )
                                    st.markdown(
                                        f"**Tool request:** `{tool_call['name']}`"
                                    )
                                    with st.expander(
                                        f"View generated input ({tool_call['name']})",
                                        expanded=False,
                                    ):
                                        st.json(tool_call["args"])

                                    current_traces.append(
                                        {
                                            "type": "tool_input",
                                            "name": tool_call["name"],
                                            "args": tool_call["args"],
                                        }
                                    )
                                    write_audit_log(
                                        session_id=st.session_state.thread_id,
                                        node_name="reasoner",
                                        tool_name=tool_call["name"],
                                        content=json.dumps(
                                            tool_call["args"],
                                            default=str,
                                        ),
                                    )

                                if latest_message.content:
                                    final_response = str(latest_message.content)
                                    status.update(
                                        label="Preparing operational response..."
                                    )

                            elif node_name == "tools":
                                status.update(
                                    label="Processing retrieved evidence..."
                                )
                                for message in node_state.get("messages", []):
                                    if not isinstance(message, ToolMessage):
                                        continue

                                    tool_content = str(message.content)
                                    with st.expander(
                                        f"View tool output ({message.name})",
                                        expanded=False,
                                    ):
                                        st.code(tool_content, language="text")

                                    current_traces.append(
                                        {
                                            "type": "tool_output",
                                            "name": message.name,
                                            "content": tool_content,
                                        }
                                    )
                                    write_audit_log(
                                        session_id=st.session_state.thread_id,
                                        node_name="tools",
                                        tool_name=message.name,
                                        content=tool_content,
                                    )

                    status.update(
                        label="Response complete",
                        state="complete",
                        expanded=False,
                    )

                if final_response:
                    st.markdown(final_response)
                    st.session_state.ui_messages.append(
                        {
                            "role": "assistant",
                            "content": final_response,
                            "traces": current_traces,
                        }
                    )
                    write_audit_log(
                        session_id=st.session_state.thread_id,
                        node_name="reasoner_final",
                        tool_name="llm_response",
                        content=final_response,
                    )
                else:
                    st.error("The agent completed without producing a response.")

            except Exception as exc:
                error_message = f"Agent request failed: {exc}"
                st.error(error_message)
                write_audit_log(
                    session_id=st.session_state.thread_id,
                    node_name="agent_error",
                    tool_name=None,
                    content=error_message,
                )


# ---------------------------------------------------------------------------
# Audit viewer
# ---------------------------------------------------------------------------
elif app_mode == AUDIT_MODE:
    st.title("Palm Logistics Agent Activity Log")
    st.caption("Authorized inspection of dbo.AgentAuditLog")

    st.markdown("### Database authorization")
    st.markdown(
        "Enter an authorized SQL administrator account to view audit entries. "
        "The Palm Logistics reader can insert logs but cannot read them."
    )

    with st.form("admin_auth_form"):
        column_user, column_password = st.columns(2)
        with column_user:
            admin_user = st.text_input(
                "Admin username",
                value=os.getenv("SQL_ADMIN_USER", ""),
            )
        with column_password:
            admin_password = st.text_input("Admin password", type="password")

        load_logs = st.form_submit_button(
            "Authenticate and load logs",
            use_container_width=True,
        )

    if load_logs:
        admin_engine = None
        try:
            admin_engine = _create_sql_engine(admin_user, admin_password)
            with admin_engine.connect() as connection:
                audit_query = text(
                    """
                    SELECT
                        [LogID],
                        [EventTimestampUtc],
                        [SessionID],
                        [NodeExecuted],
                        [ToolName],
                        [Content]
                    FROM [dbo].[AgentAuditLog]
                    ORDER BY [EventTimestampUtc] DESC, [LogID] DESC
                    """
                )
                audit_frame = pd.read_sql(audit_query, connection)

            st.success("Audit log loaded successfully.")

            if audit_frame.empty:
                st.info(
                    "No audit entries exist yet. Run a request in the "
                    "Dispatch Console first."
                )
            else:
                st.dataframe(
                    audit_frame,
                    column_config={
                        "LogID": st.column_config.NumberColumn(
                            "ID", format="%d"
                        ),
                        "EventTimestampUtc": st.column_config.DatetimeColumn(
                            "Event time (UTC)",
                            format="YYYY-MM-DD HH:mm:ss.SSS",
                        ),
                        "SessionID": "Session",
                        "NodeExecuted": "Graph node",
                        "ToolName": "Tool",
                        "Content": "Event content",
                    },
                    hide_index=True,
                    use_container_width=True,
                    height=600,
                )

        except Exception as exc:
            st.error(f"Unable to load the audit log: {exc}")
        finally:
            if admin_engine is not None:
                admin_engine.dispose()
