"""Tools used by the Palm Logistics AI assistant."""

import os
import re
import urllib.parse
from pathlib import Path

import requests
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
from sqlalchemy import create_engine, text

try:
    import streamlit as st
except ImportError:
    st = None


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _required_env(*names: str) -> str:
    """Return the first configured value, including supported legacy names."""
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    raise ValueError(f"Missing required environment variable: {' or '.join(names)}")


PINECONE_API_KEY = _required_env("PINECONE_API_KEY")
OPENROUTER_API_KEY = _required_env("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
).strip()
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "openai/text-embedding-3-small"
).strip()
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1536"))
PINECONE_INDEX_NAME = os.getenv(
    "PINECONE_INDEX_NAME", "palm-logistics-sop"
).strip()
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "policy").strip()

SQL_SERVER_HOST = os.getenv("SQL_SERVER_HOST", "127.0.0.1").strip()
SQL_SERVER_PORT = os.getenv("SQL_SERVER_PORT", "1433").strip()
SQL_SERVER_DATABASE = os.getenv("SQL_SERVER_DATABASE", "PalmLogistics").strip()
SQL_READER_USER = _required_env("SQL_READ_ONLY_USER", "SQL_Read_only_User")
SQL_READER_PASSWORD = _required_env(
    "SQL_READ_ONLY_PASSWORD", "palm_logistics_reader_password"
)
# The current legacy SQL Server container does not support the encrypted ODBC
# handshake. Set SQL_ENCRYPT=yes in production after configuring SQL Server TLS.
SQL_ENCRYPT = os.getenv("SQL_ENCRYPT", "no").strip()
SQL_TRUST_SERVER_CERTIFICATE = os.getenv(
    "SQL_TRUST_SERVER_CERTIFICATE", "yes"
).strip()
SQL_RESULT_LIMIT = int(os.getenv("SQL_RESULT_LIMIT", "20"))


def _create_openrouter_embeddings(
    model_name: str,
    dimensions: int,
) -> OpenAIEmbeddings:
    """Create the OpenRouter embedding client used by Palm Logistics."""
    print(f"Initializing embedding client: {model_name} via OpenRouter")
    return OpenAIEmbeddings(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        model=model_name,
        dimensions=dimensions,
        check_embedding_ctx_length=False,
    )


if st is not None:

    @st.cache_resource(show_spinner=False)
    def _get_streamlit_cached_openrouter_embeddings(
        model_name: str,
        dimensions: int,
    ) -> OpenAIEmbeddings:
        """Keep one embedding client across Streamlit script reruns."""
        return _create_openrouter_embeddings(model_name, dimensions)


def get_cached_openrouter_embeddings(
    model_name: str,
    dimensions: int,
) -> OpenAIEmbeddings:
    """Use Streamlit's resource cache only while Streamlit is running."""
    if st is not None and st.runtime.exists():
        return _get_streamlit_cached_openrouter_embeddings(
            model_name,
            dimensions,
        )

    return _create_openrouter_embeddings(model_name, dimensions)


# Use exactly the same embedding model, index, and namespace as the ingestion
# pipeline so queries and stored vectors remain compatible.
embeddings = get_cached_openrouter_embeddings(
    model_name=EMBEDDING_MODEL,
    dimensions=EMBEDDING_DIMENSION,
)

pinecone_client = Pinecone(api_key=PINECONE_API_KEY)
vector_store = PineconeVectorStore(
    index=pinecone_client.Index(PINECONE_INDEX_NAME),
    embedding=embeddings,
    namespace=PINECONE_NAMESPACE,
)
retriever = vector_store.as_retriever(search_kwargs={"k": 4})


odbc_connection_string = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={SQL_SERVER_HOST},{SQL_SERVER_PORT};"
    f"DATABASE={SQL_SERVER_DATABASE};"
    f"UID={SQL_READER_USER};"
    f"PWD={SQL_READER_PASSWORD};"
    f"Encrypt={SQL_ENCRYPT};"
    f"TrustServerCertificate={SQL_TRUST_SERVER_CERTIFICATE};"
)
sql_engine = create_engine(
    "mssql+pyodbc:///?odbc_connect="
    + urllib.parse.quote_plus(odbc_connection_string),
    pool_pre_ping=True,
)


def _is_read_only_query(sql_query: str) -> bool:
    """Apply a small defense-in-depth check before the read-only SQL login."""
    query = sql_query.strip()
    if not query:
        return False

    # Permit one SELECT statement (or a SELECT using a common table expression).
    query_without_trailing_semicolon = query[:-1].rstrip() if query.endswith(";") else query
    if ";" in query_without_trailing_semicolon:
        return False
    if not re.match(r"^(SELECT|WITH)\b", query_without_trailing_semicolon, re.IGNORECASE):
        return False

    blocked = re.compile(
        r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|TRUNCATE|EXEC(?:UTE)?|"
        r"GRANT|REVOKE|DENY|BACKUP|RESTORE|DBCC|USE)\b",
        re.IGNORECASE,
    )
    return blocked.search(query_without_trailing_semicolon) is None


# ---------------------------------------------------------------------------
# Palm Logistics agent tools
# ---------------------------------------------------------------------------
@tool
def query_logistics_db(sql_query: str) -> str:
    """
    Run one read-only T-SQL query against the PalmLogistics database.

    The logistics data includes timestamp, vehicle_gps_latitude,
    vehicle_gps_longitude, fuel_consumption_rate, eta_variation_hours,
    traffic_congestion_level, warehouse_inventory_level,
    loading_unloading_time, handling_equipment_availability,
    order_fulfillment_status, weather_condition_severity,
    port_congestion_level, shipping_costs, supplier_reliability_score,
    lead_time_days, historical_demand, iot_temperature,
    cargo_condition_status, route_risk_level, customs_clearance_time,
    driver_behavior_score, fatigue_monitoring_score,
    disruption_likelihood_score, delay_probability, risk_classification,
    and delivery_time_deviation. Use SQL Server/T-SQL syntax and SELECT only.
    Results are limited to a small number of rows.
    """
    if not _is_read_only_query(sql_query):
        return "Security block: submit one SELECT-only T-SQL statement."

    try:
        with sql_engine.connect() as connection:
            result = connection.execute(text(sql_query))
            columns = list(result.keys())
            rows = result.fetchmany(SQL_RESULT_LIMIT)

        if not rows:
            return "No records matched the query criteria."

        lines = [f"Columns: {', '.join(columns)}"]
        lines.extend(str(tuple(row)) for row in rows)
        if len(rows) == SQL_RESULT_LIMIT:
            lines.append(
                f"Result display stopped at {SQL_RESULT_LIMIT} rows; narrow the query if needed."
            )
        return "\n".join(lines)
    except Exception as exc:
        return f"Palm Logistics database query failed: {exc}"


@tool
def fetch_corridor_conditions(latitude: float, longitude: float) -> str:
    """
    Fetch current external weather for a shipment's GPS coordinates.

    This is live third-party weather context, not Palm Logistics telemetry and
    not proof of the shipment's cargo temperature or road congestion.
    """
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,wind_speed_10m,weather_code",
                "wind_speed_unit": "kmh",
            },
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json().get("current", {})

        return (
            "External weather context (Open-Meteo)\n"
            f"Coordinates: {latitude}, {longitude}\n"
            f"Observed at: {payload.get('time', 'unknown')}\n"
            f"Temperature: {payload.get('temperature_2m', 'N/A')} C\n"
            f"Wind speed: {payload.get('wind_speed_10m', 'N/A')} km/h\n"
            f"Weather code: {payload.get('weather_code', 'N/A')}\n"
            "Validate operational decisions against Palm Logistics telemetry and SOP."
        )
    except Exception as exc:
        return f"External weather service request failed: {exc}"


@tool
def search_compliance_sop(query: str) -> str:
    """
    Search the Palm Logistics SOP for thresholds, escalation requirements,
    cold-chain procedures, delay response, and other operational policy.
    """
    try:
        matched_documents = retriever.invoke(query)
        if not matched_documents:
            return "No matching Palm Logistics SOP passages were found."

        passages = []
        for document in matched_documents:
            source = document.metadata.get("source_file", "Palm Logistics SOP")
            heading = (
                document.metadata.get("Header_3")
                or document.metadata.get("Header_2")
                or document.metadata.get("Header_1")
                or "Unsectioned passage"
            )
            passages.append(
                f"[Source: {source} | Section: {heading}]\n{document.page_content}"
            )

        return "Palm Logistics SOP context\n\n" + "\n\n".join(passages)
    except Exception as exc:
        return f"Palm Logistics SOP retrieval failed: {exc}"


if __name__ == "__main__":
    print("\n--- Testing Tool 1: Palm Logistics SQL Database ---")
    print(
        query_logistics_db.invoke(
            """
            SELECT TOP (5)
                TABLE_SCHEMA,
                TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_SCHEMA, TABLE_NAME
            """
        )
    )

    print("\n--- Testing Tool 2: Live Corridor Weather ---")
    print(
        fetch_corridor_conditions.invoke(
            {"latitude": 40.375568, "longitude": -77.014317}
        )
    )

    print("\n--- Testing Tool 3: Palm Logistics SOP Retrieval ---")
    print(
        search_compliance_sop.invoke(
            "What must operations do when refrigerated cargo exceeds its "
            "approved temperature range?"
        )
    )
