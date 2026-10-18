import os
import hashlib
import json
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import pypdf  

from pinecone import Pinecone, ServerlessSpec
from pinecone.exceptions import NotFoundException
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# ==========================================
# 1. PATH RESOLUTION & SETUP
# ==========================================
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent 
load_dotenv(project_root / ".env")

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

if not PINECONE_API_KEY or not OPENROUTER_API_KEY:
    raise ValueError("Missing PINECONE_API_KEY or OPENROUTER_API_KEY in .env")

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
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws").strip()
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1").strip()

# Keep the cache separate for each index so changing the target cannot cause
# unchanged files to be skipped in a new, empty index.
cache_dir = project_root / "Data" / "cache"
cache_dir.mkdir(parents=True, exist_ok=True)
HASH_CACHE_FILE = cache_dir / f"{PINECONE_INDEX_NAME}_ingestion_hash_cache.json"

hash_cache = {}
if HASH_CACHE_FILE.exists():
    try:
        with open(HASH_CACHE_FILE, "r", encoding="utf-8") as f:
            hash_cache = json.load(f)
    except (OSError, json.JSONDecodeError):
        hash_cache = {}

# ==========================================
# 2. OPENROUTER EMBEDDINGS
# ==========================================
print(
    f"Embeddings: {EMBEDDING_MODEL} via OpenRouter "
    f"({EMBEDDING_DIMENSION} dimensions)"
)
embeddings = OpenAIEmbeddings(
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_BASE_URL,
    model=EMBEDDING_MODEL,
    dimensions=EMBEDDING_DIMENSION,
    check_embedding_ctx_length=False,
)

# ==========================================
# 3. PINECONE PROVISIONING
# ==========================================
print(f"Connecting to Pinecone index: [{PINECONE_INDEX_NAME}]...")
pc = Pinecone(api_key=PINECONE_API_KEY)

existing_indexes = pc.list_indexes().names()

if PINECONE_INDEX_NAME in existing_indexes:
    desc = pc.describe_index(PINECONE_INDEX_NAME)
    if desc.dimension != EMBEDDING_DIMENSION:
        raise ValueError(
            f"Pinecone index {PINECONE_INDEX_NAME!r} has dimension "
            f"{desc.dimension}, but {EMBEDDING_MODEL!r} is configured for "
            f"{EMBEDDING_DIMENSION}. Use a different index name or remove the "
            "old index manually."
        )
else:
    print(
        f"Creating Pinecone index: {PINECONE_INDEX_NAME} "
        f"({EMBEDDING_DIMENSION} dimensions)..."
    )
    pc.create_index(
        name=PINECONE_INDEX_NAME,
        dimension=EMBEDDING_DIMENSION,
        metric="cosine",
        spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION),
        timeout=60,
    )

index_client = pc.Index(PINECONE_INDEX_NAME)
vector_store = PineconeVectorStore(
    index=index_client,
    embedding=embeddings,
    namespace=PINECONE_NAMESPACE,
)


def delete_file_vectors(file_name: str) -> None:
    """Delete a file's old vectors; a missing first-run namespace is empty."""
    try:
        index_client.delete(
            filter={"source_file": {"$eq": file_name}},
            namespace=PINECONE_NAMESPACE,
        )
    except NotFoundException:
        pass

# ==========================================
# 4. ROBUST POLYMORPHIC PARSER
# ==========================================
def parse_and_chunk_document(doc_path: Path) -> list[Document]:
    ext = doc_path.suffix.lower()
    raw_chunks: list[Document] = []
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=60)
    
    if ext == ".md":
        headers_to_split_on = [("#", "Header_1"), ("##", "Header_2"), ("###", "Header_3")]
        md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        raw_text = doc_path.read_text(encoding="utf-8")
        header_docs = md_splitter.split_text(raw_text)
        raw_chunks = text_splitter.split_documents(header_docs)
        
    elif ext == ".txt":
        raw_text = doc_path.read_text(encoding="utf-8")
        raw_docs = [Document(page_content=raw_text)]
        raw_chunks = text_splitter.split_documents(raw_docs)
        
    elif ext == ".pdf":
        pdf_docs = []
        try:
            with open(doc_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                for page_num, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        pdf_docs.append(Document(page_content=page_text, metadata={"page_number": page_num + 1}))
            raw_chunks = text_splitter.split_documents(pdf_docs)
        except Exception as e:
            print(f"  ERROR: Could not parse PDF {doc_path.name}: {e}")
            return []
        
    elif ext in [".csv", ".xlsx"]:
        try:
            df = pd.read_csv(doc_path) if ext == ".csv" else pd.read_excel(doc_path)
        except Exception as e:
            print(f"  ERROR: Could not read table: {e}")
            return []
            
        for idx, row in df.iterrows():
            row_dict = row.to_dict()
            row_items = [
                f"{str(col)}: {str(val)}" 
                for col, val in row_dict.items() 
                if pd.notna(val) and str(val).strip() != ""
            ]
            
            if row_items:
                row_text = " | ".join(row_items)
                doc_item = Document(page_content=row_text, metadata={"row_index": int(idx)})
                raw_chunks.append(doc_item)

    # sanity check
    valid_chunks = []
    for chunk in raw_chunks:
        clean_text = chunk.page_content.strip()
        if clean_text:
            chunk.page_content = clean_text
            valid_chunks.append(chunk)
            
    return valid_chunks

# ==========================================
# 5. INCREMENTAL PIPELINE WITH BATCHING
# ==========================================
policy_dir = project_root / "Data" / "policy"
if not policy_dir.is_dir():
    raise FileNotFoundError(f"Policy directory does not exist: {policy_dir}")

target_patterns = ["*.md", "*.txt", "*.pdf", "*.csv", "*.xlsx"]
current_files = {}
for pattern in target_patterns:
    for file_path in policy_dir.glob(pattern):
        current_files[file_path.name] = file_path

if not current_files:
    raise RuntimeError(f"No supported policy files found in {policy_dir}")

print(f"Found {len(current_files)} policy file(s) in {policy_dir}...")

updated_cache = dict(hash_cache)
cache_modified = False
ingestion_failed = False

cached_filenames = set(hash_cache.keys())
current_filenames = set(current_files.keys())
deleted_files = cached_filenames - current_filenames

for deleted_file in deleted_files:
    print(f"Deleted file detected: {deleted_file}. Purging from Pinecone...")
    try:
        delete_file_vectors(deleted_file)
        updated_cache.pop(deleted_file, None)
        cache_modified = True
    except Exception as e:
        print(f"  ERROR: Failed to purge {deleted_file}: {e}")
        ingestion_failed = True

for file_name, file_path in current_files.items():
    file_bytes = file_path.read_bytes()
    file_hash = hashlib.md5(file_bytes).hexdigest()
    updated_cache[file_name] = file_hash
    
    if hash_cache.get(file_name) == file_hash:
        print(f"Skipped (unchanged): {file_name}")
        continue
        
    print(f"Processing updates: {file_name}...")
    cache_modified = True
    
    try:
        delete_file_vectors(file_name)
        
        chunks = parse_and_chunk_document(file_path)
        if not chunks:
            print(f"  WARNING: No valid text chunks extracted from {file_name}.")
            updated_cache.pop(file_name, None)
            ingestion_failed = True
            continue
            
        explicit_ids = []
        for idx, chunk in enumerate(chunks):
            chunk.metadata["source_file"] = file_name
            chunk.metadata["file_format"] = file_path.suffix.replace(".", "").upper()
            chunk.metadata["document_type"] = "Palm Logistics Policy"
            explicit_ids.append(f"{file_name}-chunk-{idx}")
            
        batch_size = 100
        total_chunks = len(chunks)
        print(f"  Upserting {total_chunks} chunk(s) in batches of {batch_size}...")
        
        for i in range(0, total_chunks, batch_size):
            batch_docs = chunks[i : i + batch_size]
            batch_ids = explicit_ids[i : i + batch_size]
            vector_store.add_documents(documents=batch_docs, ids=batch_ids)
            
    except Exception as e:
        print(f"ERROR: Ingestion failed for {file_name}: {e}")
        updated_cache.pop(file_name, None)
        ingestion_failed = True

# ==========================================
# 6. SYNC HASH CACHE
# ==========================================
if cache_modified:
    with open(HASH_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(updated_cache, f, indent=4)
    if ingestion_failed:
        print("ERROR: Ingestion finished with errors. Failed files will be retried.")
    else:
        print("Ingestion and cache update complete.")
else:
    print("Index is already up to date.")

if ingestion_failed:
    raise SystemExit(1)
