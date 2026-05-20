"""Step2API main application entry point."""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.config import config
from .core.pool import pool
from .core.exceptions import Step2APIError
from .api.routes import router, admin_router, health_router

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("step2api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Startup
    logger.info(f"Step2API v0.1.0 starting on {config.host}:{config.port}")

    # Load accounts into pool
    accounts = config.accounts
    if accounts:
        pool.load_accounts(accounts)
        logger.info(f"Loaded {len(accounts)} accounts")
    else:
        logger.warning("No accounts configured. Add accounts to config.json.")

    logger.info(f"API keys configured: {len(config.keys)}")
    logger.info(f"Account max inflight: {config.account_max_inflight}")
    logger.info(f"Account max queue: {config.account_max_queue}")

    yield

    # Shutdown
    logger.info("Step2API shutting down")


# Create FastAPI app
app = FastAPI(
    title="Step2API",
    description="OpenAI-compatible API wrapper for stepfun.com web chat",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware - allow all origins like ds2api
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)
app.include_router(admin_router)
app.include_router(health_router)


# Exception handlers
@app.exception_handler(Step2APIError)
async def step2api_error_handler(request: Request, exc: Step2APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"message": str(exc), "type": type(exc).__name__}},
    )


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": {"message": "Internal server error", "type": "server_error"}},
    )


# Root redirect / shortcut routes
@app.get("/models")
@app.get("/v1/models")
async def list_models_shortcut():
    from .api.routes import list_models
    return await list_models()


@app.post("/chat/completions")
@app.post("/v1/chat/completions")
async def chat_completions_shortcut(request: Request):
    from .api.routes import chat_completions, ChatCompletionRequest
    body = await request.json()
    req = ChatCompletionRequest(**body)
    return await chat_completions(request, req)


def main():
    """Entry point for running the server."""
    import uvicorn

    uvicorn.run(
        "step2api.main:app",
        host=config.host,
        port=config.port,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()
