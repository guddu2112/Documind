"""RAG Q&A endpoint — retrieve from Chroma, generate with LLM.

Routes:
    POST /ask — Answer a question grounded in the indexed documents.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from documind.api.schemas import AskCitation, AskRequest, AskResponse

logger = logging.getLogger(__name__)
router = APIRouter()


_PREVIEW_CHARS = 240
_CONTEXT_CHARS_PER_HIT = 1800


_PROMPT_TEMPLATE = """You are a careful document analyst. Answer the user's question using ONLY the context passages below.

Rules:
- If the context does not contain the answer, reply exactly: "The provided documents do not contain enough information to answer."
- Cite the sources you used by their [n] number in square brackets at the end of each supporting sentence.
- Keep the answer concise and factual.

Context:
{context}

Question: {question}

Answer:"""


def _build_context(hits: list[dict]) -> str:
    blocks: list[str] = []
    for i, hit in enumerate(hits, start=1):
        content = (hit.get("content") or "").strip()
        if len(content) > _CONTEXT_CHARS_PER_HIT:
            content = content[:_CONTEXT_CHARS_PER_HIT] + "…"
        doc_id = hit.get("id", "")
        doc_type = hit.get("doc_type", "")
        blocks.append(f"[{i}] (id={doc_id}, type={doc_type})\n{content}")
    return "\n\n".join(blocks)


@router.post(
    "",
    response_model=AskResponse,
    summary="Ask a question grounded in the indexed documents (RAG)",
)
async def ask(body: AskRequest):
    """Retrieve top-k passages from Chroma and ask the LLM to answer."""
    from documind.services import factory

    try:
        svc = factory.get_search_service()
        hits = svc.semantic_search(
            query=body.question,
            top=body.top,
            filters=f"c.doc_type = '{body.doc_type}'" if body.doc_type else None,
        )
    except Exception as exc:
        logger.exception("RAG retrieval failed")
        raise HTTPException(status_code=500, detail="Retrieval failed.") from exc

    if not hits:
        return AskResponse(
            question=body.question,
            answer="No indexed documents are available yet. Upload a document first.",
            citations=[],
        )

    prompt = _PROMPT_TEMPLATE.format(
        context=_build_context(hits),
        question=body.question.strip(),
    )

    try:
        call_llm = factory.get_llm_text_caller()
        answer = call_llm(prompt).strip()
    except Exception as exc:
        logger.exception("RAG generation failed")
        raise HTTPException(status_code=502, detail=f"LLM call failed: {exc}") from exc

    citations = [
        AskCitation(
            id=hit.get("id", ""),
            doc_type=hit.get("doc_type", ""),
            score=float(hit.get("score", 0.0)),
            preview=((hit.get("content") or "").strip()[:_PREVIEW_CHARS]),
        )
        for hit in hits
    ]
    return AskResponse(question=body.question, answer=answer, citations=citations)
