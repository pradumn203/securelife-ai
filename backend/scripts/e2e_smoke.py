"""End-to-end smoke test against a running backend on :8000.

Exercises the five feature pillars in a single flow:

1. Create a chat session (POST /api/chat/sessions).
2. Stream a chat turn (POST /api/chat/stream) and consume the SSE events.
3. List leads (GET /api/leads) and confirm the new lead is there, then run
   the qualification agent (POST /api/leads/{id}/qualify).
4. Upload a PDF (POST /api/documents), run the document extractor agent
   (POST /api/documents/{id}/extract), and poll until EXTRACTED or FAILED.
5. Run the analysis agent (POST /api/analysis/generate) and read it back.
6. Fetch the lead detail (GET /api/leads/{id}) and confirm it's all present.

Run from `backend/`:
    uv run python scripts/e2e_smoke.py

Exit code 0 = all five pillars responded. The script DOES NOT require a live
Groq key — if the key is empty, document steps 2/4/5 will show their error
paths rather than their happy paths; the script still exits 0 as long as the
backend responded structurally. Use `--strict` to require happy-path success
instead (useful for a pre-Loom gate).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

DEFAULT_BASE = "http://127.0.0.1:8000"


class Smoke:
    def __init__(self, *, strict: bool, pdf_path: Path | None, base: str) -> None:
        self._strict = strict
        self._base = base
        self._pdf_path = pdf_path or (
            Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "sample.pdf"
        )
        self._client = httpx.AsyncClient(base_url=base, timeout=120)
        self._failures: list[str] = []

    async def close(self) -> None:
        await self._client.aclose()

    # --- helpers ------------------------------------------------------

    def _record(self, step: str, ok: bool, detail: str = "") -> None:
        tick = "[ok]  " if ok else "[warn]"
        print(f"{tick} {step}: {detail}")
        if not ok and self._strict:
            self._failures.append(f"{step}: {detail}")

    async def _get(self, path: str, **kw: Any) -> httpx.Response:
        return await self._client.get(path, **kw)

    async def _post(self, path: str, **kw: Any) -> httpx.Response:
        return await self._client.post(path, **kw)

    # --- 1. health ----------------------------------------------------

    async def health(self) -> None:
        r = await self._get("/api/health")
        self._record("health", r.status_code == 200, f"status={r.status_code}")

    # --- 2. chat session ---------------------------------------------

    async def start_session(self) -> str:
        r = await self._post("/api/chat/sessions", json={"source": "WEB"})
        if r.status_code != 200:
            self._record("chat.sessions", False, f"status={r.status_code} body={r.text[:200]}")
            return ""
        data = r.json()
        lead_id = data["lead_id"]
        greeting = data["greeting"]
        self._record(
            "chat.sessions",
            True,
            f"lead_id={lead_id} greeting_len={len(greeting)}",
        )
        return lead_id

    # --- 3. chat stream ---------------------------------------------

    async def stream_turn(self, lead_id: str) -> None:
        if not lead_id:
            self._record("chat.stream", False, "no lead_id")
            return
        # Covers every core fact so the qualification agent's gate opens.
        body = {
            "lead_id": lead_id,
            "message": (
                "Hi, I'm Smoke Test from Mumbai, smoke.test@example.com. I'd like to review "
                "my existing family health policy and get it sorted this month."
            ),
        }
        async with self._client.stream(
            "POST", "/api/chat/stream", json=body, headers={"Accept": "text/event-stream"}
        ) as r:
            if r.status_code != 200:
                body_text = await r.aread()
                self._record(
                    "chat.stream",
                    False,
                    f"status={r.status_code} body={body_text[:200]!r}",
                )
                return
            token_count = 0
            done = False
            error: str | None = None
            buf = ""
            async for chunk in r.aiter_text():
                buf += chunk
                parts = buf.split("\n\n")
                buf = parts.pop() if parts else ""
                for frame in parts:
                    if not frame.startswith("data:"):
                        continue
                    payload = json.loads(frame[5:].strip())
                    kind = payload.get("type")
                    if kind == "token":
                        token_count += 1
                    elif kind == "done":
                        done = True
                    elif kind == "error":
                        error = payload.get("error")
            if error is not None:
                self._record(
                    "chat.stream",
                    False,
                    f"backend emitted error: {error[:120]}",
                )
            else:
                self._record(
                    "chat.stream",
                    True,
                    f"tokens={token_count} done={done}",
                )

    # --- 4. list leads -----------------------------------------------

    async def list_leads(self) -> None:
        r = await self._get("/api/leads")
        if r.status_code != 200:
            self._record("leads.list", False, f"status={r.status_code}")
            return
        leads = r.json()
        self._record("leads.list", True, f"count={len(leads)}")

    # --- 4b. qualification agent ----------------------------------------

    async def qualify(self, lead_id: str) -> None:
        if not lead_id:
            self._record("leads.qualify", False, "no lead_id")
            return
        # The chat extractor agent runs in the background after `done`; give
        # it a moment to record the core facts before the gate checks them.
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            lead = (await self._get(f"/api/leads/{lead_id}")).json()
            if lead.get("extracted_fields", {}).get("timeline"):
                break
            await asyncio.sleep(1.0)
        r = await self._post(f"/api/leads/{lead_id}/qualify")
        if r.status_code == 400:
            missing = r.json().get("detail", {}).get("missing", [])
            self._record("leads.qualify", not self._strict, f"gate closed, missing={missing}")
            return
        if r.status_code != 200:
            self._record("leads.qualify", False, f"status={r.status_code} body={r.text[:200]}")
            return
        q = r.json()
        verified = sum(1 for d in q["dimensions"] if d["evidence_verified"])
        status = (await self._get(f"/api/leads/{lead_id}")).json().get("status")
        self._record(
            "leads.qualify",
            status == "IN_PROGRESS" or not self._strict,
            f"verdict={q['verdict']} score={q['score']} verified_quotes={verified}/5 status={status}",
        )

    # --- 5. upload + poll --------------------------------------------

    async def upload_and_poll(self, lead_id: str) -> str | None:
        if not lead_id:
            self._record("documents.upload", False, "no lead_id")
            return None
        if not self._pdf_path.exists():
            self._record("documents.upload", False, f"fixture missing: {self._pdf_path}")
            return None
        with self._pdf_path.open("rb") as fh:
            files = {"file": (self._pdf_path.name, fh, "application/pdf")}
            data = {"lead_id": lead_id}
            r = await self._post("/api/documents", data=data, files=files)
        if r.status_code != 200:
            self._record("documents.upload", False, f"status={r.status_code} body={r.text[:200]}")
            return None
        doc_id = r.json()["document_id"]
        self._record("documents.upload", True, f"doc_id={doc_id}")

        # Extraction is broker-triggered, not automatic on upload.
        r = await self._post(f"/api/documents/{doc_id}/extract")
        if r.status_code != 200:
            self._record("documents.extract", False, f"status={r.status_code} body={r.text[:200]}")
            return doc_id
        self._record("documents.extract", True, f"status={r.json()['status']}")

        # Poll
        deadline = time.monotonic() + 90
        last_status = "UPLOADED"
        while time.monotonic() < deadline:
            r = await self._get(f"/api/documents/{doc_id}")
            if r.status_code != 200:
                self._record("documents.poll", False, f"status={r.status_code}")
                return doc_id
            doc = r.json()
            last_status = doc["status"]
            if last_status in {"EXTRACTED", "FAILED"}:
                break
            await asyncio.sleep(1.5)
        happy = last_status == "EXTRACTED"
        self._record(
            "documents.poll",
            happy or not self._strict,
            f"final_status={last_status}",
        )
        return doc_id

    # --- 6. analysis --------------------------------------------------

    async def generate_analysis(self, lead_id: str) -> None:
        if not lead_id:
            self._record("analysis.generate", False, "no lead_id")
            return
        r = await self._post("/api/analysis/generate", json={"lead_id": lead_id})
        if r.status_code == 400:
            self._record(
                "analysis.generate",
                not self._strict,  # expected if no extraction yet
                f"400: {r.json().get('detail', '')[:120]}",
            )
            return
        if r.status_code != 200:
            self._record("analysis.generate", False, f"status={r.status_code}")
            return
        analysis = r.json()
        self._record(
            "analysis.generate",
            True,
            f"gaps={len(analysis.get('coverage_gaps', []))} "
            f"risks={len(analysis.get('risk_flags', []))} "
            f"conf={analysis.get('confidence')}",
        )

    # --- 7. lead detail ----------------------------------------------

    async def lead_detail(self, lead_id: str) -> None:
        if not lead_id:
            return
        r = await self._get(f"/api/leads/{lead_id}")
        if r.status_code != 200:
            self._record("leads.detail", False, f"status={r.status_code}")
            return
        lead = r.json()
        self._record(
            "leads.detail",
            True,
            f"status={lead.get('status')} "
            f"msgs={len(lead.get('messages', []))} "
            f"docs={len(lead.get('documents', []))} "
            f"has_analysis={lead.get('latest_analysis') is not None}",
        )

    # --- orchestrate --------------------------------------------------

    async def run(self) -> int:
        print(f"[..] Running e2e smoke against {self._base}")
        await self.health()
        lead_id = await self.start_session()
        await self.stream_turn(lead_id)
        await self.list_leads()
        await self.qualify(lead_id)
        await self.upload_and_poll(lead_id)
        await self.generate_analysis(lead_id)
        await self.lead_detail(lead_id)
        print()
        if self._failures:
            print("FAILED:")
            for f in self._failures:
                print(f"  - {f}")
            return 1
        print("[done] All steps responded.")
        return 0


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="Fail on non-happy-paths.")
    parser.add_argument("--pdf", type=Path, help="Path to a PDF to upload.")
    parser.add_argument("--base", default=DEFAULT_BASE, help="Backend base URL.")
    args = parser.parse_args()
    smoke = Smoke(strict=args.strict, pdf_path=args.pdf, base=args.base)
    try:
        return await smoke.run()
    finally:
        await smoke.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
