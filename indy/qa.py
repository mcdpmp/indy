"""Answer a question about the documents Indy was given, with citations.

Code picks the passages (word overlap, no model), the model only writes the answer from them,
and code maps the numbered markers in the answer back to documents. If nothing in the documents
matches, Indy says so without asking the model at all, so it cannot make something up.
An answer that cites no passage is flagged, because it cannot be traced to a document.
"""

import re

from .documents import Doc, Loaded
from .llm_client import DATA_RULE, LLM, untrusted

MAX_QUESTION = 500
PASSAGES = 6
PASSAGE_CHARS = 1100
_STOP = {
    "the",
    "and",
    "for",
    "with",
    "are",
    "was",
    "were",
    "been",
    "this",
    "that",
    "these",
    "those",
    "its",
    "from",
    "what",
    "who",
    "when",
    "where",
    "which",
    "how",
    "does",
    "did",
    "will",
    "would",
    "can",
    "could",
    "should",
    "about",
    "into",
    "than",
    "then",
    "there",
    "their",
    "they",
    "them",
    "our",
    "you",
    "your",
    "any",
    "all",
    "not",
    "yes",
}


def _terms(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9][a-z0-9'-]{2,}", text.lower()) if w not in _STOP}


def chunks(doc: Doc) -> list[dict]:
    """Passages of one document: each section, long ones split at paragraph breaks."""
    out: list[dict] = []
    for s in doc.sections:
        body = s.body.strip()
        if not body:
            continue
        buf = ""
        for para in re.split(r"\n\s*\n", body):
            if buf and len(buf) + len(para) > PASSAGE_CHARS:
                out.append({"doc": doc.filename, "where": s.title or "start", "text": buf})
                buf = ""
            buf = f"{buf}\n\n{para}".strip()
        if buf:
            out.append(
                {"doc": doc.filename, "where": s.title or "start", "text": buf[: PASSAGE_CHARS * 2]}
            )
    return out


def top_passages(question: str, loaded: Loaded, n: int = PASSAGES) -> list[dict]:
    q = _terms(question)
    scored: list[tuple[int, int, dict]] = []
    order = 0
    for doc in loaded.everything():
        for c in chunks(doc):
            order += 1
            hits = len(q & _terms(c["where"] + " " + c["text"]))
            if hits:
                scored.append((hits, -order, c))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [c for _, _, c in scored[:n]]


def answer(llm: LLM, loaded: Loaded, question: str) -> dict:
    question = question.strip()
    if not question or len(question) > MAX_QUESTION:
        raise ValueError(f"Ask a question of 1 to {MAX_QUESTION} characters.")
    if not loaded.everything():
        return {
            "answer": "No readable documents are filed for this opportunity, so there is nothing to answer from.",
            "sources": [],
            "grounded": False,
        }
    passages = top_passages(question, loaded)
    if not passages:
        return {
            "answer": "The documents Indy can read do not mention this, so Indy cannot answer it.",
            "sources": [],
            "grounded": False,
        }
    blocks = "\n\n".join(
        untrusted(f"P{i}", f"[{i}] {p['doc']}, {p['where']}\n{p['text']}", PASSAGE_CHARS * 2)
        for i, p in enumerate(passages, 1)
    )
    prompt = (
        f"{DATA_RULE}\n\nTASK: answer a question about project documents\n"
        "Answer in one to four sentences using only the numbered passages below. After each "
        "claim put the passage number in square brackets, like [2]. If the passages do not "
        "answer the question, say so plainly.\n\n"
        f"Question: {question}\n\n{blocks}"
    )
    text = llm.text(prompt, num_predict=500)
    used = sorted(
        {int(m) for m in re.findall(r"\[(\d{1,2})\]", text) if 1 <= int(m) <= len(passages)}
    )
    sources = [
        {
            "n": i,
            "doc": passages[i - 1]["doc"],
            "where": passages[i - 1]["where"],
            "excerpt": " ".join(passages[i - 1]["text"].split())[:500],
        }
        for i in used
    ]
    return {"answer": text, "sources": sources, "grounded": bool(sources)}
