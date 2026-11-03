"""EduPulse API entry point.  Run:  uvicorn app.main:app --reload
Interactive API docs: http://localhost:8000/docs (Swagger) and /redoc."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS
from .database import Base, engine
from .routers import admin, auth, dashboard, interventions, records, students

@asynccontextmanager
async def lifespan(_app):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="EduPulse API",
    version="1.1.0",
    description=("Response-adaptive academic intervention and learning analytics system. "
                 "Cycle: records -> Random Forest state -> eligibility rules -> linear Thompson sampling -> "
                 "intervention -> follow-up -> reward -> policy update -> state reassessment."),
)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

for r in (auth, students, records, interventions, dashboard, admin):
    app.include_router(r.router)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok"}
