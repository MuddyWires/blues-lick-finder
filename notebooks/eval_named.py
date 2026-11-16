import json
import re
from pathlib import Path

from dotenv import load_dotenv

from embeddings import best_chunk_per_video, build_indexes, retrieve
from youtube_data import DATA_PATH

load_dotenv()

SONGS = ["Hide Away", "Pride and Joy", "Killing Floor", "Sweet Home Chicago",
         "Mannish Boy", "Born Under a Bad Sign", "Shame Shame Shame", "Baby Please Don't Go"]
TEMPLATES = ["{} guitar lesson", "how to play {}"]
METHODS = ("tfidf", "vector", "hybrid", "hybrid@0.5", "hybrid@0.25")


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


documents = json.loads(Path(DATA_PATH).read_text())
chunks, index, vector_index = build_indexes(documents)
with_transcript = {d["video_id"] for d in documents if d["transcript"]}

# A video is relevant if the song name is in its title (and it has a transcript,
# so it can be retrieved at all).
relevant = {
    s: {d["video_id"] for d in documents
        if d["video_id"] in with_transcript and norm(s) in norm(d["title"])}
    for s in SONGS
}
songs = [s for s in SONGS if len(relevant[s]) >= 2]
print("songs with >=2 matching videos:", {s: len(relevant[s]) for s in songs})

print(f"\n{'method':12} hit@5  prec@5   ({len(songs) * len(TEMPLATES)} queries)")
for method in METHODS:
    hits = prec = n = 0
    for s in songs:
        for template in TEMPLATES:
            results = best_chunk_per_video(retrieve(index, vector_index, template.format(s), method))
            flags = [r["video_id"] in relevant[s] for r in results]
            hits += any(flags)
            prec += sum(flags) / 5
            n += 1
    print(f"{method:12} {hits / n:.2f}   {prec / n:.2f}")
