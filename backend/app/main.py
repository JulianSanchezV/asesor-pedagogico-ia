from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.routers import auth, evaluations, labs, reports, rubrics, settings as settings_router, submissions
from app.services.seed import seed_initial_data
from app.services.storage import ensure_local_upload_dir

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_local_upload_dir()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Plataforma web inteligente para evaluación, retroalimentación y fortalecimiento de competencias en IA.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list + ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(labs.router)
app.include_router(rubrics.router)
app.include_router(submissions.router)
app.include_router(evaluations.router)
app.include_router(reports.router)
app.include_router(settings_router.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "sandbox_mode": settings.SANDBOX_MODE}
