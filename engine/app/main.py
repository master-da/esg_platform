from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import users
from app.config import get_settings
from app.db import close_pool, pool

ENGINE_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(_: FastAPI):
    pool()
    yield
    close_pool()


app = FastAPI(title="Carbon & ESG engine", version=ENGINE_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
)

app.include_router(users.router)


@app.get("/health")
def health():
    from app.db import transaction

    with transaction(None) as tx:
        tx.scalar("select 1")
    return {"status": "ok", "version": ENGINE_VERSION}
