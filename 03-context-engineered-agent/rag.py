"""
RAG (Retrieval-Augmented Generation) over a small markdown knowledge base.

Documents in knowledge_base/ are split into chunks at each "## " heading and
indexed with TF-IDF. At query time the most similar chunks are returned and
inserted into the LLM's context, so answers are grounded in *our* policies and
guides instead of whatever the model remembers from pre-training.

TF-IDF keeps the demo dependency-free and fully offline. In production you
would swap `_vectorise` for an embedding model and the dict index for a vector
database - the retrieve-then-generate pattern stays the same.
"""
import math
import os
import re
from collections import Counter

BASE_DIR = os.path.dirname(__file__)

STOPWORDS = set("""
a an and are as at be by can for from has have how i in is it its me my of on or our
so that the their them there this to up us was we what when where which who will with
you your do does not no any all about into than then should would could just want need
""".split())


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9£]+", text.lower())
    # Very light stemming: "flights" -> "flight", "bags" -> "bag"
    return [t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t
            for t in tokens if t not in STOPWORDS]


class KnowledgeBase:
    def __init__(self, directory: str = os.path.join(BASE_DIR, "knowledge_base")):
        self.chunks: list[dict] = []
        for filename in sorted(os.listdir(directory)):
            if filename.endswith(".md"):
                with open(os.path.join(directory, filename)) as f:
                    self.chunks.extend(self._chunk(filename, f.read()))
        self._build_index()

    @staticmethod
    def _chunk(source: str, text: str) -> list[dict]:
        doc_title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), source)
        chunks = []
        for section in re.split(r"^## ", text, flags=re.MULTILINE)[1:]:
            heading, _, body = section.partition("\n")
            chunks.append({
                "id": f"{source}#{heading.strip().lower().replace(' ', '-')}",
                "source": source,
                "title": f"{doc_title} › {heading.strip()}",
                "text": body.strip(),
            })
        return chunks

    def _vectorise(self, tokens: list[str]) -> dict[str, float]:
        counts = Counter(tokens)
        vec = {t: (1 + math.log(c)) * self.idf.get(t, 0.0) for t, c in counts.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def _build_index(self):
        # Titles are repeated so a heading match counts for more than a passing mention
        docs = [tokenize(c["title"]) * 3 + tokenize(c["text"]) for c in self.chunks]
        n = len(docs)
        df = Counter(t for d in docs for t in set(d))
        self.idf = {t: math.log((1 + n) / (1 + d)) + 1 for t, d in df.items()}
        self.vectors = [self._vectorise(d) for d in docs]

    def search(self, query: str, k: int = 4, min_score: float = 0.08) -> list[dict]:
        q = self._vectorise(tokenize(query))
        scored = []
        for chunk, vec in zip(self.chunks, self.vectors):
            score = sum(w * vec.get(t, 0.0) for t, w in q.items())
            if score >= min_score:
                scored.append({**chunk, "score": round(score, 3)})
        scored.sort(key=lambda c: c["score"], reverse=True)
        return scored[:k]

    @staticmethod
    def format_for_prompt(chunks: list[dict]) -> str:
        return "\n\n".join(f"[{i + 1}] {c['title']} (source: {c['source']})\n{c['text']}" for i, c in enumerate(chunks))


if __name__ == "__main__":
    kb = KnowledgeBase()
    print(f"Indexed {len(kb.chunks)} chunks")
    for hit in kb.search("family flying easyJet to Dublin with bags"):
        print(f"{hit['score']:.3f}  {hit['title']}")
