from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.database import create_tables
from app.routers import employees, field_definitions, policies
from app.services.policy_engine import PolicyConflictError


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_tables()
    yield


app = FastAPI(title="Policy Assignment System", version="1.0.0", lifespan=lifespan)
app.include_router(employees.router)
app.include_router(field_definitions.router)
app.include_router(policies.router)


@app.exception_handler(PolicyConflictError)
async def policy_conflict_handler(_: Request, exc: PolicyConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.get("/")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "policy-assignment-system"}
