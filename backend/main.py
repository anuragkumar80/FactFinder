"""FastAPI app: static UI + SSE endpoint that streams the live pipeline trace."""
import json
import queue
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from . import cache, config, service
from .errors import CheckFailed, InputError, QuotaExceeded, RateLimited
from .ratelimit import RateLimiter

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="Fact Finder", version="0.1.0")
# Open CORS: the Round 2 Chrome extension will call this API from another origin.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"],
                   allow_headers=["*"])
limiter = RateLimiter(config.RATE_LIMIT_CHECKS, config.RATE_LIMIT_WINDOW_SECONDS)


class CheckRequest(BaseModel):
    text: str


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return fwd or (request.client.host if request.client else "unknown")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@app.get("/")
def index():
    return FileResponse(ROOT / "frontend" / "index.html")


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/quota")
def quota():
    return cache.get_quota()


@app.get("/api/demo")
def demo():
    path = ROOT / "demo" / "claims.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


@app.post("/api/check")
def check(req: CheckRequest, request: Request):
    try:
        text = service.clean_input(req.text)
    except InputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    ip = _client_ip(request)

    def stream():
        q: queue.Queue = queue.Queue()
        t0 = time.time()

        def emit(stage, message):
            q.put(("trace", {"stage": stage, "message": message, "t": round(time.time() - t0, 1)}))

        def worker():
            try:
                q.put(("result", service.check(text, emit, rate_check=lambda: limiter.check(ip))))
            except RateLimited as e:
                q.put(("error", {"code": "rate_limited", "message": str(e)}))
            except QuotaExceeded as e:
                q.put(("error", {"code": "quota", "message": str(e)}))
            except CheckFailed as e:
                q.put(("error", {"code": "failed", "message": f"Live check failed ({e}). "
                                 "Try again in a minute or use a demo claim."}))
            except Exception as e:  # never leave the stream hanging
                q.put(("error", {"code": "internal", "message": f"Unexpected error: {type(e).__name__}"}))
            finally:
                q.put(None)

        threading.Thread(target=worker, daemon=True).start()
        while True:
            try:
                item = q.get(timeout=15)
            except queue.Empty:
                yield ": keepalive\n\n"  # stop proxies from closing an idle stream
                continue
            if item is None:
                break
            yield _sse(*item)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
