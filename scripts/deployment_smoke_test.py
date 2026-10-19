"""Post-deployment checks for Palm Logistics production dependencies."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

environment_file = Path(
    os.getenv("PALM_ENV_FILE", "/etc/palm-logistics/palm-logistics.env")
)
if not environment_file.is_file():
    raise RuntimeError(f"Production environment file not found: {environment_file}")

load_dotenv(environment_file, override=False)

# Import after loading production configuration. This also verifies that the
# deployed agent graph and its tools can be imported successfully.
from src.agent_tools import (  # noqa: E402
    EMBEDDING_DIMENSION,
    PINECONE_INDEX_NAME,
    PINECONE_NAMESPACE,
    embeddings,
    pinecone_client,
    sql_engine,
)
from src.orchestrator import palm_agent  # noqa: E402, F401


def main() -> None:
    """Fail immediately when a required production dependency is unavailable."""
    with sql_engine.connect() as connection:
        value = connection.execute(text("SELECT 1")).scalar_one()
        if value != 1:
            raise RuntimeError("SQL Server returned an unexpected smoke-test result")

    vector = embeddings.embed_query("Palm Logistics deployment smoke test")
    if len(vector) != EMBEDDING_DIMENSION:
        raise RuntimeError(
            "Embedding dimension mismatch: "
            f"expected {EMBEDDING_DIMENSION}, received {len(vector)}"
        )

    index = pinecone_client.Index(PINECONE_INDEX_NAME)
    stats = index.describe_index_stats()
    namespaces = stats.namespaces or {}
    if PINECONE_NAMESPACE not in namespaces:
        raise RuntimeError(
            f"Pinecone namespace not found: {PINECONE_NAMESPACE!r}"
        )

    print("Deployment smoke test passed: imports, SQL, embeddings, and Pinecone.")


if __name__ == "__main__":
    main()
