from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    bills,
    categorization,
    compliance,
    dashboards,
    intake,
    library,
    modules,
    projects,
    reference,
    reports,
    results,
    users,
)
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
app.include_router(library.router)
for module in (projects, intake, categorization, results, bills, modules, reference, compliance, dashboards, reports):
    app.include_router(module.router)


@app.exception_handler(psycopg.errors.RaiseException)
async def database_rule(_: Request, exc: psycopg.errors.RaiseException):
    """Business rules enforced by database triggers (locked projects, immutable factors ...)."""
    return JSONResponse(status_code=409, content={"detail": exc.diag.message_primary})


@app.exception_handler(psycopg.errors.InsufficientPrivilege)
async def database_privilege(_: Request, exc: psycopg.errors.InsufficientPrivilege):
    return JSONResponse(status_code=403, content={"detail": "You do not have permission to change this data."})


@app.get("/health")
def health():
    from app.db import transaction

    with transaction(None) as tx:
        tx.scalar("select 1")
    return {"status": "ok", "version": ENGINE_VERSION}
