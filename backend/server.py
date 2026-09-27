from fastapi import FastAPI, APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
import os
import json
import logging
import re
import httpx
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timedelta, timezone

from llm_provider import LlmChat, UserMessage
from ai_utils import extract_json
from razorpay_gateway import (
    RAZORPAY_KEY_ID,
    RAZORPAY_KEY_SECRET,
    create_order as razorpay_create_order,
    fetch_payment as razorpay_fetch_payment,
    is_configured as razorpay_is_configured,
    verify_payment_signature as razorpay_verify_payment_signature,
)
from cars_data import CARS_SEED, NEWS_SEED
from configurator_composition import mount_configurator_router
from configurator_production_audit_routes import make_configurator_production_audit_router
import security

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
CORS_ORIGINS = [origin.strip().rstrip("/") for origin in os.environ.get("CORS_ORIGINS", "*").split(",") if origin.strip()] or ["*"]
if security.APP_ENV == "production" and "*" in CORS_ORIGINS:
    raise RuntimeError("CORS_ORIGINS must be explicit when APP_ENV=production")
ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]
ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY')
CLAUDE_MODEL = ("anthropic", "claude-sonnet-4-6")
AI_MODELS = {
    "claude": {"provider": "anthropic", "model": "claude-sonnet-4-6", "label": "Claude Sonnet 4.6", "family": "Anthropic", "strength": "Balanced reasoning · unbiased"},
    "claude-opus": {"provider": "anthropic", "model": "claude-opus-4-7", "label": "Claude Opus 4.7", "family": "Anthropic", "strength": "Deepest reasoning · premium"},
    "claude-haiku": {"provider": "anthropic", "model": "claude-haiku-4-5-20251001", "label": "Claude Haiku 4.5", "family": "Anthropic", "strength": "Ultra-fast · lightweight"},
    "gpt-flagship": {"provider": "openai", "model": "gpt-5.4", "label": "GPT-5.4", "family": "OpenAI", "strength": "Flagship reasoning · versatile"},
    "gpt-mini": {"provider": "openai", "model": "gpt-5.4-mini", "label": "GPT-5.4 Mini", "family": "OpenAI", "strength": "Fast & efficient"},
    "gemini-pro": {"provider": "gemini", "model": "gemini-3.1-pro-preview", "label": "Gemini 3.1 Pro", "family": "Google", "strength": "Deep analysis · latest"},
    "gemini-flash": {"provider": "gemini", "model": "gemini-3.5-flash", "label": "Gemini 3.5 Flash", "family": "Google", "strength": "Blazing fast · concise"},
}
DEFAULT_CHAT_MODEL = "claude"
_DOCS_ENABLED = security.APP_ENV != "production"
app = FastAPI(title="Auto-AI India API", docs_url="/docs" if _DOCS_ENABLED else None, redoc_url="/redoc" if _DOCS_ENABLED else None, openapi_url="/openapi.json" if _DOCS_ENABLED else None)
api_router = APIRouter(prefix="/api")

@app.middleware("http")
async def request_security_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > 1_048_576:
                return JSONResponse(status_code=413, content={"detail": "Request body too large", "request_id": request_id})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length", "request_id": request_id})
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

PHONE_PATTERN = r"^\+?[0-9]{10,15}$"
ADMIN_PIN = os.environ.get("ADMIN_PIN", "").strip()
_rate_limiter = security.DistributedRateLimiter()

async def _rate_allowed(namespace: str, key: str, limit: int, window_seconds: int) -> bool:
    return await _rate_limiter.allow(namespace, key, limit, window_seconds)

def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"

def _bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization: return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip(): return None
    return token.strip()

async def optional_user_phone(authorization: Optional[str] = Header(None)) -> Optional[str]:
    token = _bearer_token(authorization)
    if not token: return None
    sess = await db.user_sessions.find_one({"token_hash": security.hash_secret(token)}, {"_id": 0})
    if not sess or security.is_expired(sess.get("expires_at")): return None
    return sess["phone"]

async def current_user_phone(phone: Optional[str] = Depends(optional_user_phone)) -> str:
    if not phone: raise HTTPException(status_code=401, detail="Authentication required")
    return phone

async def require_admin(authorization: Optional[str] = Header(None)) -> str:
    token = _bearer_token(authorization)
    if token:
        sess = await db.admin_sessions.find_one({"token_hash": security.hash_secret(token)}, {"_id": 0})
        if sess and not security.is_expired(sess.get("expires_at")): return "admin"
    raise HTTPException(status_code=401, detail="Admin authentication required")

def _admin_pin_valid(pin: str) -> bool:
    if not ADMIN_PIN: raise HTTPException(status_code=503, detail="Admin access is not configured")
    return security.constant_time_equals(pin, ADMIN_PIN)

class Car(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str; brand: str; model: str; variant: str; segment: str; fuel: str; transmission: str
    price_ex_showroom: int; price_on_road: int; mileage_kmpl: float; engine_cc: int; power_bhp: int
    seats: int; boot_litres: int; safety_rating: int; ground_clearance_mm: int; waiting_weeks: int; image: str
    tags: List[str] = []
class NewsItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str; title: str; summary: str; category: str; date: str; source: str; image: str
class CompareRequest(BaseModel):
    car_a: str = Field(max_length=120); car_b: str = Field(max_length=120); user_need: Optional[str] = Field(default="general family use", max_length=500)
class RecommendRequest(BaseModel):
    budget_min: int = Field(ge=0, le=1_000_000_000); budget_max: int = Field(ge=0, le=1_000_000_000)
    fuel: Optional[str] = Field(default="Any", max_length=40); seats: Optional[int] = Field(default=5, ge=1, le=20)
    usage: Optional[str] = Field(default="city", max_length=200); notes: Optional[str] = Field(default="", max_length=1000)
class ChatRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    session_id: str = Field(max_length=128); message: str = Field(min_length=1, max_length=4000)
    language: Optional[str] = Field(default="English", max_length=40); model: Optional[str] = Field(default=None, max_length=40)
class BookingRequest(BaseModel):
    idempotency_key: Optional[str] = Field(default=None, min_length=16, max_length=128)
    car_id: str = Field(max_length=80); name: str = Field(min_length=1, max_length=120); phone: str = Field(pattern=PHONE_PATTERN)
    email: Optional[str] = Field(default="", max_length=200); city: str = Field(min_length=1, max_length=80)
    preferred_date: Optional[str] = Field(default="", max_length=40); test_drive: bool = True; needs_loan: bool = False; needs_insurance: bool = False
    exchange_car: Optional[str] = Field(default="", max_length=120); notes: Optional[str] = Field(default="", max_length=2000)
class Booking(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str; car_id: str; car_name: str; name: str; phone: str; email: str = ""; city: str; preferred_date: str = ""
    test_drive: bool; needs_loan: bool; needs_insurance: bool; exchange_car: str = ""; notes: str = ""; status: str; dealer: str; eta_call_minutes: int; created_at: str
class EMIRequest(BaseModel):
    principal: float = Field(gt=0, le=1_000_000_000); annual_rate: float = Field(ge=0, le=100); tenure_months: int = Field(gt=0, le=480)

_IMAGE_CACHE: dict[str, tuple[bytes, str]] = {}
_IMAGE_CACHE_BYTES = 50 * 1024 * 1024
_IMAGE_CACHE_MAX_ITEM = 5 * 1024 * 1024
_IMAGE_CACHE_SIZE = 0

@app.on_event("startup")
async def seed_db():
    await db.command("ping")
    await _rate_limiter.connect()
    if await db.cars.estimated_document_count() == 0 and CARS_SEED:
        await db.cars.insert_many([dict(c) for c in CARS_SEED])
    if await db.news.estimated_document_count() == 0 and NEWS_SEED:
        await db.news.insert_many([dict(n) for n in NEWS_SEED])
    await db.otps.create_index("phone")
    await db.otps.create_index("expires_at", expireAfterSeconds=0)
    await db.user_sessions.create_index("token_hash", unique=True)
    await db.user_sessions.create_index("expires_at", expireAfterSeconds=0)
    await db.admin_sessions.create_index("token_hash", unique=True)
    await db.admin_sessions.create_index("expires_at", expireAfterSeconds=0)
    await db.bookings.create_index("phone")
    await db.bookings.create_index("idempotency_key", unique=True, sparse=True)
    await db.payment_transactions.create_index("order_id", unique=True)
    await db.payment_transactions.create_index("idempotency_key", unique=True, sparse=True)
    await db.payment_transactions.create_index("payment_id", unique=True, sparse=True)
    await db.entitlements.create_index([("phone", 1), ("plan_id", 1)], unique=True)
    await db.processed_payment_events.create_index("expires_at", expireAfterSeconds=0)
    await db.chat_sessions.create_index([("session_id", 1), ("phone", 1)], unique=True)
    await db.chat_messages.create_index([("session_id", 1), ("owner_phone", 1), ("ts", 1)])
    await db.configurations.create_index("config_id", unique=True)
    await db.configurations.create_index("share_token", unique=True, sparse=True)
    if not security.SECRET_KEY_CONFIGURED:
        logger.warning("SECRET_KEY is not configured — sessions and OTPs will be invalidated on restart.")
    if not ADMIN_PIN:
        logger.warning("ADMIN_PIN is not configured — the admin API will refuse all requests.")
    task = asyncio.create_task(_prewarm_images(), name="auto-ai-image-prewarm")
    task.add_done_callback(lambda completed: (completed.exception() if not completed.cancelled() else None))

async def _prewarm_images() -> None:
    global _IMAGE_CACHE_SIZE
    try:
        await _prewarm_images_impl()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Image prewarm failed")

async def _prewarm_images_impl() -> None:
    global _IMAGE_CACHE_SIZE
    urls_to_warm = [
        "https://imgd.aeplcdn.com/664x374/n/cw/ec/141867/nexon-exterior-right-front-three-quarter-79.png",
        "https://imgd.aeplcdn.com/664x374/n/cw/ec/106815/creta-exterior-right-front-three-quarter-6.png",
        "https://imgd.aeplcdn.com/664x374/n/cw/ec/159099/swift-exterior-right-front-three-quarter-31.png",
    ]
    for url in urls_to_warm:
        if url in _IMAGE_CACHE:
            continue
        try:
            data, content_type = await _fetch_image(url)
            if _IMAGE_CACHE_SIZE + len(data) <= _IMAGE_CACHE_BYTES:
                _IMAGE_CACHE[url] = (data, content_type)
                _IMAGE_CACHE_SIZE += len(data)
        except Exception:
            logger.debug("Image prewarm failed", exc_info=True)
        await asyncio.sleep(0.1)

async def get_chat(session_id: str, system_message: str, model_key: Optional[str] = None) -> LlmChat:
    if model_key is not None and model_key not in AI_MODELS:
        raise HTTPException(status_code=400, detail="Unsupported AI model")
    model = AI_MODELS[model_key] if model_key else AI_MODELS[DEFAULT_CHAT_MODEL]
    return LlmChat(api_key=None, session_id=session_id, system_message=system_message).with_model(model["provider"], model["model"])

async def find_car_by_name(name: str) -> Optional[dict]:
    normalized = name.strip().lower()
    cars = await db.cars.find({}, {"_id": 0}).to_list(500)
    for car in cars:
        full_name = f"{car['brand']} {car['model']}".lower()
        if normalized in full_name or full_name in normalized or car["model"].lower() == normalized:
            return car
    for car in cars:
        model_name = car["model"].lower()
        if model_name in normalized or any(token in model_name for token in normalized.split()):
            return car
    return None

_ALLOWED_HOSTS = ("upload.wikimedia.org", "commons.wikimedia.org", "images.unsplash.com", "images.pexels.com", "videos.pexels.com", "cdn.pixabay.com", "imgd.aeplcdn.com", "imgd-ct.aeplcdn.com", "stimg.cardekho.com", "i.ytimg.com")
_MAX_VIDEO_BYTES = 100 * 1024 * 1024

def _require_allowed_host(url: str) -> None:
    if not security.host_allowed(url, _ALLOWED_HOSTS):
        raise HTTPException(status_code=400, detail="Host not allowed")

async def _validate_proxy_url(url: str) -> None:
    _require_allowed_host(url)
    try:
        await asyncio.to_thread(security.validate_public_url, url, _ALLOWED_HOSTS)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

async def _fetch_image(url: str) -> tuple[bytes, str]:
    await _validate_proxy_url(url)
    timeout = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        async with client.stream("GET", url, headers={"User-Agent": "AutoAIIndia/1.0", "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*", "Referer": "https://www.carwale.com/"}) as response:
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Upstream fetch failed")
            await _validate_proxy_url(str(response.url))
            content_type = response.headers.get("content-type", "image/jpeg")
            if not content_type.lower().startswith("image/"):
                raise HTTPException(status_code=415, detail="Upstream resource is not an image")
            content_length = response.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > _IMAGE_CACHE_MAX_ITEM:
                        raise HTTPException(status_code=502, detail="Upstream payload too large")
                except ValueError:
                    pass
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                total += len(chunk)
                if total > _IMAGE_CACHE_MAX_ITEM:
                    raise HTTPException(status_code=502, detail="Upstream payload too large")
                chunks.append(chunk)
            return b"".join(chunks), content_type.split(";", 1)[0]

@app.get("/health")
async def health():
    return {"status": "ok", "service": "auto-ai-api"}

@app.get("/health/live")
async def health_live():
    return {"status": "ok"}

@app.get("/health/ready")
async def health_ready():
    checks: dict[str, str] = {}
    try:
        await db.command("ping")
        checks["mongodb"] = "ok"
    except Exception:
        logger.exception("MongoDB readiness check failed")
        checks["mongodb"] = "error"
    try:
        if security.REDIS_URL:
            if _rate_limiter._redis is None:
                checks["redis"] = "error"
            else:
                await _rate_limiter._redis.ping()
                checks["redis"] = "ok"
        else:
            checks["redis"] = "development-fallback"
    except Exception:
        logger.exception("Redis readiness check failed")
        checks["redis"] = "error"
    if any(value == "error" for value in checks.values()):
        return JSONResponse(status_code=503, content={"status": "not_ready", "checks": checks})
    return {"status": "ready", "checks": checks}

@app.get("/api/image-proxy")
async def image_proxy(url: str = Query(max_length=2000)):
    global _IMAGE_CACHE_SIZE
    if url in _IMAGE_CACHE:
        data, content_type = _IMAGE_CACHE[url]
    else:
        try:
            data, content_type = await _fetch_image(url)
        except HTTPException:
            raise
        except httpx.RequestError:
            logger.exception("image proxy upstream error")
            raise HTTPException(status_code=502, detail="Upstream error")
        if _IMAGE_CACHE_SIZE + len(data) <= _IMAGE_CACHE_BYTES:
            _IMAGE_CACHE[url] = (data, content_type)
            _IMAGE_CACHE_SIZE += len(data)
    return Response(content=data, media_type=content_type, headers={"Cache-Control": "public, max-age=604800", "Cross-Origin-Resource-Policy": "cross-origin"})

@app.api_route("/api/video-proxy", methods=["GET", "HEAD"])
async def video_proxy(request: Request, url: str = Query(max_length=2000)):
    from fastapi.responses import StreamingResponse
    await _validate_proxy_url(url)
    forward_headers = {"User-Agent": "AutoAIIndia/1.0", "Accept": "video/mp4,video/*,*/*", "Referer": "https://www.pexels.com/"}
    if request.headers.get("range"):
        forward_headers["Range"] = request.headers["range"]
    timeout = httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0)
    client = httpx.AsyncClient(timeout=timeout, follow_redirects=False)
    try:
        method = "HEAD" if request.method == "HEAD" else "GET"
        upstream = await client.send(client.build_request(method, url, headers=forward_headers), stream=True)
        if not security.host_allowed(str(upstream.url), _ALLOWED_HOSTS):
            await upstream.aclose(); await client.aclose()
            raise HTTPException(status_code=400, detail="Host not allowed")
        if upstream.status_code not in (200, 206):
            status = upstream.status_code
            await upstream.aclose(); await client.aclose()
            raise HTTPException(status_code=status, detail="Upstream fetch failed")
        content_length = upstream.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > _MAX_VIDEO_BYTES:
                    await upstream.aclose(); await client.aclose()
                    raise HTTPException(status_code=502, detail="Upstream video too large")
            except ValueError:
                pass
        content_type = upstream.headers.get("content-type", "video/mp4")
        response_headers = {"Cache-Control": "public, max-age=86400", "Cross-Origin-Resource-Policy": "cross-origin", "Accept-Ranges": "bytes"}
        for header in ("content-length", "content-range"):
            if header in upstream.headers:
                response_headers[header.title()] = upstream.headers[header]
        if request.method == "HEAD":
            await upstream.aclose(); await client.aclose()
            return Response(status_code=upstream.status_code, media_type=content_type, headers=response_headers)
        async def iterator():
            total = 0
            try:
                async for chunk in upstream.aiter_bytes(chunk_size=64 * 1024):
                    total += len(chunk)
                    if total > _MAX_VIDEO_BYTES:
                        raise HTTPException(status_code=502, detail="Upstream video too large")
                    yield chunk
            finally:
                await upstream.aclose(); await client.aclose()
        return StreamingResponse(iterator(), status_code=upstream.status_code, media_type=content_type, headers=response_headers)
    except HTTPException:
        await client.aclose(); raise
    except httpx.RequestError:
        await client.aclose(); logger.exception("video proxy upstream error")
        raise HTTPException(status_code=502, detail="Upstream error")

@api_router.get("/")
async def root(): return {"message": "Auto-AI India API - Unbiased Car Intelligence"}
@api_router.get("/cars", response_model=List[Car])
async def list_cars(q: Optional[str] = Query(None, max_length=120), segment: Optional[str] = Query(None, max_length=40), fuel: Optional[str] = Query(None, max_length=40), budget_max: Optional[int] = Query(None, ge=0, le=1_000_000_000)):
    query: dict = {}
    if segment: query["segment"] = segment
    if fuel and fuel != "Any": query["fuel"] = fuel
    if budget_max: query["price_ex_showroom"] = {"$lte": budget_max}
    cars = await db.cars.find(query, {"_id": 0}).to_list(500)
    if q: cars = [c for c in cars if q.lower() in f"{c['brand']} {c['model']}".lower()]
    return cars
@api_router.get("/cars/{car_id}", response_model=Car)
async def get_car(car_id: str):
    car = await db.cars.find_one({"id": car_id}, {"_id": 0})
    if not car: raise HTTPException(status_code=404, detail="Car not found")
    return car
@api_router.get("/news", response_model=List[NewsItem])
async def list_news(): return await db.news.find({}, {"_id": 0}).sort("date", -1).to_list(100)
@api_router.post("/emi/calculate")
async def calculate_emi(req: EMIRequest):
    r = req.annual_rate / 12 / 100; n = req.tenure_months
    emi = req.principal / n if r == 0 else req.principal * r * ((1 + r) ** n) / (((1 + r) ** n) - 1)
    total_payment = emi * n
    return {"emi": round(emi, 2), "total_payment": round(total_payment, 2), "total_interest": round(total_payment - req.principal, 2), "principal": req.principal, "tenure_months": n, "annual_rate": req.annual_rate}
COMPARE_SYSTEM = """You are 'Auto-AI India', an absolutely unbiased Indian automotive analyst.
Rules:
- Zero brand promotion. No marketing fluff.
- Base verdict strictly on the data provided (safety, mileage, power, space, waiting, price).
- Call out HIDDEN CONS brands don't advertise (e.g. low boot, weak safety, long waiting, thirsty engine).
- Output STRICT JSON only. No extra prose, no markdown fences.
JSON schema:
{
  "winner": "<exact name of winning car>", "headline": "<one punchy sentence, <= 18 words>",
  "verdict": "<2-3 sentence transparent reasoning, Indian buyer context>",
  "pros_a": ["<pro1>", "<pro2>", "<pro3>"], "cons_a": ["<con1>", "<con2>", "<con3>"],
  "pros_b": ["<pro1>", "<pro2>", "<pro3>"], "cons_b": ["<con1>", "<con2>", "<con3>"],
  "scores": { "value": {"a": <0-10>, "b": <0-10>}, "safety": {"a": <0-10>, "b": <0-10>}, "efficiency": {"a": <0-10>, "b": <0-10>}, "comfort": {"a": <0-10>, "b": <0-10>}, "performance": {"a": <0-10>, "b": <0-10>} },
  "best_for": "<who should buy the winner>"
}
"""
@api_router.post("/ai/compare")
async def ai_compare(req: CompareRequest, request: Request):
    if not await _rate_allowed("ai-compare-ip", _client_ip(request), 12, 300):
        raise HTTPException(status_code=429, detail="Too many AI comparison requests, try again later")
    car_a = await find_car_by_name(req.car_a); car_b = await find_car_by_name(req.car_b)
    if not car_a or not car_b: raise HTTPException(status_code=404, detail=f"Could not find one of the cars. a_found={bool(car_a)}, b_found={bool(car_b)}")
    prompt = f'''Compare these two Indian cars for a buyer whose need is: "{req.user_need}".\n\nCAR A:\n{json.dumps(car_a, indent=2)}\n\nCAR B:\n{json.dumps(car_b, indent=2)}\n\nReturn ONLY the JSON in the exact schema.'''
    try:
        response = await (await get_chat(f"compare-{uuid.uuid4()}", COMPARE_SYSTEM)).send_message(UserMessage(text=prompt)); parsed = extract_json(response)
        if not parsed: raise HTTPException(status_code=502, detail="AI did not return valid JSON")
        return {"car_a": car_a, "car_b": car_b, "analysis": parsed}
    except HTTPException: raise
    except Exception: logging.exception("compare failure"); raise HTTPException(status_code=502, detail="AI service unavailable")
RECOMMEND_SYSTEM = """You are 'Auto-AI India', unbiased Indian car recommender.
From the candidate list, pick the TOP 3 that best fit the buyer needs. No brand bias.
Output STRICT JSON only:
{"top_picks":[{"car_id":"<id>","score":<0-100>,"why":"<1-2 sentence transparent reasoning>","watchouts":"<one honest con>"}],"summary":"<2 sentence overall guidance>"}
"""
@api_router.post("/ai/recommend")
async def ai_recommend(req: RecommendRequest, request: Request):
    if not await _rate_allowed("ai-recommend-ip", _client_ip(request), 12, 300):
        raise HTTPException(status_code=429, detail="Too many AI recommendation requests, try again later")
    query: dict = {"price_ex_showroom": {"$gte": req.budget_min, "$lte": req.budget_max}}
    if req.fuel and req.fuel != "Any": query["fuel"] = req.fuel
    if req.seats: query["seats"] = {"$gte": req.seats}
    candidates = await db.cars.find(query, {"_id": 0}).to_list(200)
    if not candidates: return {"top_picks": [], "summary": "No cars match your criteria. Try widening the budget or seat filter.", "candidates": []}
    prompt = f'''Buyer profile:\n- Budget: ₹{req.budget_min:,} to ₹{req.budget_max:,}\n- Fuel: {req.fuel}\n- Seats needed: {req.seats}\n- Usage: {req.usage}\n- Notes: {req.notes}\n\nCandidate cars (JSON):\n{json.dumps(candidates, indent=2)}\n\nReturn ONLY the JSON in the exact schema.'''
    try:
        response = await (await get_chat(f"recommend-{uuid.uuid4()}", RECOMMEND_SYSTEM)).send_message(UserMessage(text=prompt)); parsed = extract_json(response)
        if not parsed: raise HTTPException(status_code=502, detail="AI did not return valid JSON")
        id_map = {c["id"]: c for c in candidates}
        for pick in parsed.get("top_picks", []): pick["car"] = id_map.get(pick.get("car_id"))
        return parsed
    except HTTPException: raise
    except Exception: logging.exception("recommend failure"); raise HTTPException(status_code=502, detail="AI service unavailable")
@api_router.get("/ai/models")
async def list_ai_models(): return {"default": DEFAULT_CHAT_MODEL, "models": [{"id": k, "label": v["label"], "family": v["family"], "strength": v["strength"]} for k, v in AI_MODELS.items()]}
TTS_VOICES = {"female": {"voice_id": "EXAVITQu4vr4xnSDxMaL", "label": "Sarah", "gender": "Female"}, "male": {"voice_id": "IKne3meq5aSn9XLyUdCD", "label": "Charlie", "gender": "Male"}}
DEFAULT_TTS_VOICE = "female"; _TTS_CHAR_LIMIT = 1200
@api_router.get("/tts/voices")
async def tts_list_voices(): return {"default": DEFAULT_TTS_VOICE, "voices": [{"id": k, "label": v["label"], "gender": v["gender"]} for k, v in TTS_VOICES.items()]}
class TTSRequest(BaseModel): text: str = Field(max_length=5000); voice: Optional[str] = Field(default=None, max_length=20)
@api_router.post("/tts/speak")
async def tts_speak(req: TTSRequest, request: Request):
    if not await _rate_allowed("tts-ip", _client_ip(request), 20, 300):
        raise HTTPException(status_code=429, detail="Too many TTS requests, try again later")
    if not ELEVENLABS_API_KEY: raise HTTPException(status_code=503, detail="TTS not configured")
    text = (req.text or "").strip()
    if not text: raise HTTPException(status_code=400, detail="Empty text")
    if len(text) > _TTS_CHAR_LIMIT: text = text[:_TTS_CHAR_LIMIT] + "…"
    voice_key = req.voice if req.voice in TTS_VOICES else DEFAULT_TTS_VOICE; voice_id = TTS_VOICES[voice_key]["voice_id"]
    try:
        from elevenlabs import ElevenLabs
        def synthesize() -> bytes:
            client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
            audio_iter = client.text_to_speech.convert(text=text, voice_id=voice_id, model_id="eleven_multilingual_v2", output_format="mp3_44100_128")
            return b"".join(chunk for chunk in audio_iter if chunk)
        audio_bytes = await asyncio.to_thread(synthesize)
        if not audio_bytes: raise HTTPException(status_code=502, detail="Empty audio from provider")
        if len(audio_bytes) > 10 * 1024 * 1024: raise HTTPException(status_code=502, detail="TTS response too large")
        return Response(content=audio_bytes, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=3600", "Cross-Origin-Resource-Policy": "cross-origin"})
    except HTTPException: raise
    except Exception: logging.exception("TTS failure"); raise HTTPException(status_code=502, detail="TTS service unavailable")
CHAT_SYSTEM = """You are 'Auto-AI India', a 24×7 AI concierge for Indian car buyers.
Core abilities:
1. Unbiased car advice, comparisons, EMI guidance (data-driven, no brand promotion).
2. CUSTOMER SUCCESS / CRM: if the user mentions "my booking", "track", "my order", "cancel", "confirmation", "SMS", "email", or gives a booking id — use the BOOKING CONTEXT block below. Respond with exact details (booking id, car, dealer, status, ETA call time). Promise the dealer will call; acknowledge cancellation or reschedule requests politely.
3. NOTIFICATIONS: tell the user you've logged their request in-app and that the AI will remind the dealer. DO NOT claim SMS/email have been sent unless BOOKING CONTEXT explicitly mentions that.
Style: Concise, warm, confident. Use short paragraphs and bullet points.
Length: Under 180 words unless a deep-dive is asked.
Language: Reply in {LANGUAGE}. Devanagari for Hindi, Tamil script for Tamil, etc. Keep technical terms (EMI, kmpl, bhp, ADAS) as-is.
BOOKING CONTEXT:\n{BOOKING_CONTEXT}
"""

def _format_booking_context(bookings: list) -> str:
    if not bookings:
        return "No booking records found."
    return "\n".join(f"- ID: {b.get('id','')}; Car: {b.get('car_name','')}; Dealer: {b.get('dealer','')}; Status: {b.get('status','')}; ETA: {b.get('eta_call_minutes','')} minutes; Created: {b.get('created_at','')}" for b in bookings)

@api_router.post("/chat")
async def chat(req: ChatRequest, request: Request, phone: Optional[str] = Depends(optional_user_phone)):
    if not await _rate_allowed("chat-ip", _client_ip(request), 30, 300):
        raise HTTPException(status_code=429, detail="Too many chat requests, try again later")
    if phone and not await _rate_allowed("chat-user", phone, 60, 300):
        raise HTTPException(status_code=429, detail="Too many chat requests, try again later")
    bookings = []
    if phone:
        bookings = await db.bookings.find({"phone": phone}, {"_id": 0}).sort("created_at", -1).to_list(20)
    language = req.language or "English"
    system_message = CHAT_SYSTEM.format(LANGUAGE=language, BOOKING_CONTEXT=_format_booking_context(bookings))
    try:
        response = await (await get_chat(req.session_id, system_message, req.model)).send_message(UserMessage(text=req.message))
        now = datetime.now(timezone.utc).isoformat()
        await db.chat_sessions.update_one({"session_id": req.session_id, "phone": phone}, {"$setOnInsert": {"session_id": req.session_id, "phone": phone, "created_at": now}, "$set": {"updated_at": now}}, upsert=True)
        await db.chat_messages.insert_one({"session_id": req.session_id, "owner_phone": phone, "role": "user", "content": req.message, "ts": now})
        await db.chat_messages.insert_one({"session_id": req.session_id, "owner_phone": phone, "role": "assistant", "content": response, "ts": now})
        return {"response": response, "model": req.model or DEFAULT_CHAT_MODEL}
    except HTTPException:
        raise
    except Exception:
        logging.exception("chat failure")
        raise HTTPException(status_code=502, detail="AI service unavailable")

@api_router.get("/chat/history/{session_id}")
async def chat_history(session_id: str, phone: Optional[str] = Depends(optional_user_phone)):
    messages = await db.chat_messages.find({"session_id": session_id, "owner_phone": phone}, {"_id": 0}).sort("ts", 1).to_list(200)
    return {"session_id": session_id, "messages": messages}

app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=ALLOW_CREDENTIALS, allow_methods=["*"], allow_headers=["*"])
app.include_router(api_router)
mount_configurator_router(app, db, optional_user_phone)
app.include_router(make_configurator_production_audit_router(db, require_admin))
