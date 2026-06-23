import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from db.session_store import init_db
from routes.chat import router as chat_router
from routes.curriculum import router as curriculum_router
from routes.audit import router as audit_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Socratic Tutor API", lifespan=lifespan)

# ALLOWED_ORIGINS accepts a comma-separated list so both local and deployed
# frontend URLs can be whitelisted via a single env var.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/chat")
app.include_router(curriculum_router, prefix="/curriculum")
app.include_router(audit_router, prefix="/audit")


@app.get("/health")
async def health():
    return {"status": "ok"}
