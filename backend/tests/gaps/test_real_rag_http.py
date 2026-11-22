"""RAG over HTTP with the REAL embedding model and REAL pgvector search, behind a real login.

Covers what the module suites could not: upload -> extraction -> chunking -> embedding -> storage -> similarity search
through the real routers and RBAC, then the agent's `retrieve_hospital_protocol` tool using that real retrieval and its
citation check accepting only pages that were actually retrieved. Only the LLM is a scripted fake.
"""
import json
import time
from pathlib import Path

import pytest

from tests.agentdb import ScriptedLlm, reply, tool_messages
from tests.e2e.conftest import ADMIN_PASSWORD, VIEWER_PASSWORD, login
from tests.e2e.test_acceptance_http import FACTS, POLICY, apply

SAMPLE_DIR = Path("/sample_docs")
pytestmark = pytest.mark.skipif(not SAMPLE_DIR.is_dir(), reason="sample_docs is not mounted in this environment")

EXPECTED_TITLES = {
    "Emergency Department Workflow SOP", "Patient Registration and Admission Policy",
    "Investigation Workflow Guidelines", "Hospital Escalation Procedures",
    "Patient Discharge Coordination SOP", "Resource Management Guidelines",
}


@pytest.fixture()
def admin(real_rag_client):
    """Overrides the shared `admin` fixture, which depends on `client` and would patch in a FAKE policy search."""
    return login(real_rag_client, "demo_admin", ADMIN_PASSWORD)


def wait_until_indexed(client, headers, expected, timeout=240):
    deadline = time.time() + timeout
    items = []
    while time.time() < deadline:
        items = client.get("/api/knowledge/documents?limit=50", headers=headers).json()["items"]
        if len(items) >= expected and all(d["status"] in ("indexed", "failed") for d in items):
            return items
        time.sleep(1)
    raise AssertionError(f"documents not indexed in time: {[(d['name'], d['status']) for d in items]}")


@pytest.fixture()
def indexed_samples(real_rag_client, admin):
    r = real_rag_client.post("/api/knowledge/documents/load-samples", headers=admin)
    assert r.status_code in (200, 201), r.text
    docs = wait_until_indexed(real_rag_client, admin, expected=6)
    return docs


def test_samples_are_ingested_and_indexed_with_real_embeddings(real_rag_client, admin, indexed_samples):
    assert {d["name"] for d in indexed_samples} >= EXPECTED_TITLES
    for d in indexed_samples:
        assert d["status"] == "indexed", (d["name"], d["error_message"])
        assert d["chunk_count"] >= 3 and d["page_count"] >= 1 and d["is_sample"] is True


def test_similarity_search_returns_cited_ranked_results(real_rag_client, admin, indexed_samples):
    r = real_rag_client.post("/api/rag/search", headers=admin, json={
        "query": "average waiting time 75 minutes, 38 patients waiting and only 1 bed available: escalation threshold",
        "k": 5})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "MiniLM" in body["embedding_model"]
    results = body["results"]
    assert 1 <= len(results) <= 5
    assert results[0]["document_name"] == "Hospital Escalation Procedures"
    scores = [x["score"] for x in results]
    assert scores == sorted(scores, reverse=True) and all(0 < s <= 1.0 for s in scores)
    for x in results:
        assert x["page_number"] >= 1 and x["excerpt"].strip() and x["injection_flagged"] is False
    assert "UNTRUSTED" in body["llm_context"].upper() or "untrusted" in body["llm_context"].lower()


def test_different_questions_retrieve_different_documents(real_rag_client, admin, indexed_samples):
    def ranking(query):
        r = real_rag_client.post("/api/rag/search", headers=admin, json={"query": query, "k": 4}).json()
        return [(x["document_name"], x["page_number"], round(x["score"], 3)) for x in r["results"]]

    escalation = ranking("when must the duty manager escalate a long average wait to hospital management")
    discharge = ranking("how are patient discharges coordinated and beds released after discharge")
    assert escalation[0][0] == "Hospital Escalation Procedures", escalation
    assert discharge[0][0] == "Patient Discharge Coordination SOP", discharge


def test_search_and_upload_are_rbac_protected_and_validated(real_rag_client, admin, indexed_samples):
    anonymous = real_rag_client.post("/api/rag/search", json={"query": "x", "k": 3})
    assert anonymous.status_code == 401
    viewer = login(real_rag_client, "demo_viewer", VIEWER_PASSWORD)
    pdf = next(SAMPLE_DIR.glob("*.pdf")).read_bytes()
    assert real_rag_client.post("/api/knowledge/documents", headers=viewer,
                                files={"file": ("x.pdf", pdf, "application/pdf")}).status_code == 403
    bad = real_rag_client.post("/api/knowledge/documents", headers=admin,
                               files={"file": ("notes.txt", b"hello", "text/plain")})
    assert bad.status_code in (400, 415, 422) and "error" in bad.json()
    fake_pdf = real_rag_client.post("/api/knowledge/documents", headers=admin,
                                    files={"file": ("fake.pdf", b"not really a pdf", "application/pdf")})
    assert fake_pdf.status_code in (400, 415, 422) and "error" in fake_pdf.json()
    for k in (0, 1000):
        assert real_rag_client.post("/api/rag/search", headers=admin, json={"query": "ok", "k": k}).status_code == 422


def test_agent_uses_real_retrieval_and_only_real_pages_verify_as_citations(real_rag_client, admin, indexed_samples,
                                                                          llm_holder):
    apply(real_rag_client, admin, "surge")

    def cite_what_was_retrieved(request):
        policy = next(p for p in tool_messages(request) if "results" in p or "chunks" in p or "policies" in p)
        chunks = policy.get("results") or policy.get("chunks") or policy.get("policies")
        first = chunks[0]
        name = first.get("document_name") or first.get("document")
        page = first.get("page") or first.get("page_number")
        return reply(f"Waiting is high. [Source: {name}, p.{page}] Also [Source: Invented Handbook, p.9].")

    llm_holder.use(ScriptedLlm([reply(tool_calls=FACTS), reply(tool_calls=[POLICY]), cite_what_was_retrieved]))
    r = real_rag_client.post("/api/agent/demo-run", json={"provider": "ollama", "model": "fake"}, headers=admin)
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["status"] == "completed"
    docs = {p["document_name"] for p in run["retrieved_policies"]}
    assert docs and docs <= EXPECTED_TITLES  # only real sample documents, with real page numbers
    assert all(p["page"] >= 1 and p["excerpt"] and 0 < p["score"] <= 1 for p in run["retrieved_policies"])
    queries = {p["matched_query"] for p in run["retrieved_policies"]}
    assert len(queries) >= 2  # targeted queries per topic, not one broad query
    check = json.dumps(run["citation_check"]).lower()
    assert "invented handbook" in check  # the fabricated citation is reported, not silently accepted
    assert run["answer"] and "Invented Handbook" in run["answer"]  # reported, never rewritten
