import os
import json
import time
import hashlib
import joblib
import pandas as pd
from llm_client import create_embedding

JSON_FOLDER = "jsons"
OUTPUT_FILE = "embeddings.joblib"
PROGRESS_FILE = "embeddings_progress.joblib"

MERGE_CHUNKS = False  # JSON files pehle se merged hain to False kar dein
GROUP_SIZE = 5        # kitne chhote chunks ko jod kar ek bana
OVERLAP = 0           # 1 karne par har chunk pichle ke aakhri hisse se shuru hoga

BATCH_SIZE = 50       # ek API call mein kitne texts bhejne hain
PAUSE_SECONDS = 5     # API calls ko free-tier rate limit ke andar rakhne ke liye


def merge_chunks(chunks, group_size=5, overlap=0):
    """Ek hi video ke chunks ko jodta hai. Title, numbers jaise baaki fields pehle chunk se aate hain."""
    if group_size <= overlap:
        raise ValueError("GROUP_SIZE, OVERLAP se bada hona chahiye.")
    step = group_size - overlap
    merged = []
    for i in range(0, len(chunks), step):
        group = chunks[i:i + group_size]
        if not group:
            break
        new_chunk = dict(group[0])
        new_chunk["end"] = group[-1]["end"]
        new_chunk["text"] = " ".join(c["text"].strip() for c in group)
        merged.append(new_chunk)
        if i + group_size >= len(chunks):
            break
    return merged


def embed_in_batches(texts):
    all_embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        all_embeddings.extend(create_embedding(batch))  # default: RETRIEVAL_DOCUMENT
        time.sleep(PAUSE_SECONDS)
    return all_embeddings


def save_progress(progress):
    temp_file = PROGRESS_FILE + ".tmp"
    joblib.dump(progress, temp_file)
    os.replace(temp_file, PROGRESS_FILE)


json_files = sorted(f for f in os.listdir(JSON_FOLDER) if f.endswith(".json"))

settings = {
    "merge_chunks": MERGE_CHUNKS,
    "group_size": GROUP_SIZE,
    "overlap": OVERLAP,
}
if os.path.exists(PROGRESS_FILE):
    progress = joblib.load(PROGRESS_FILE)
    if not isinstance(progress, dict) or progress.get("settings") != settings:
        raise RuntimeError(
            f"{PROGRESS_FILE} has incompatible settings. Remove it to start over."
        )
else:
    progress = {"settings": settings, "files": {}}

rows_by_file = {}

for json_file in json_files:
    file_path = os.path.join(JSON_FOLDER, json_file)
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    source_hash = hashlib.sha256(file_bytes).hexdigest()

    saved_file = progress["files"].get(json_file)
    if saved_file and saved_file.get("source_hash") == source_hash:
        print(f"{json_file}: embeddings already saved, skipping.")
        rows_by_file[json_file] = saved_file["rows"]
        continue

    data = json.loads(file_bytes.decode("utf-8"))

    chunks = [c for c in data["chunks"] if c.get("text", "").strip()]
    before = len(chunks)

    # merge har video ke andar alag se hota hai, isliye videos aapas mein nahi milte
    if MERGE_CHUNKS:
        chunks = merge_chunks(chunks, GROUP_SIZE, OVERLAP)

    print(f"{json_file}: {before} chunks -> {len(chunks)} chunks, embedding ban rahi hai...")
    embeddings = embed_in_batches([c["text"] for c in chunks])

    file_rows = []
    for chunk, emb in zip(chunks, embeddings):
        chunk = dict(chunk)
        chunk["embedding"] = emb
        file_rows.append(chunk)

    rows_by_file[json_file] = file_rows
    progress["files"][json_file] = {
        "source_hash": source_hash,
        "rows": file_rows,
    }
    save_progress(progress)

rows = []
for json_file in json_files:
    for row in rows_by_file[json_file]:
        row = dict(row)
        row["chunk_id"] = len(rows)
        rows.append(row)

df = pd.DataFrame.from_records(rows)
joblib.dump(df, OUTPUT_FILE)
if os.path.exists(PROGRESS_FILE):
    os.remove(PROGRESS_FILE)

print(f"Done. Total chunks: {len(df)}, vector size: {len(df['embedding'].iloc[0])}")