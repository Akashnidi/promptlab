from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create data/ and data/uploads/ directories on startup
    Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path("static").mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="PromptLab v1 (MAx Ops)",
    description="Enterprise Prompt Engineering Workbench by MAx Ops",
    lifespan=lifespan,
)

# CORS middleware allowing localhost only
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files mounted at /static
Path("static").mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 template rendering
templates = Jinja2Templates(directory="templates")

from routers import files as files_router
from routers import history as history_router
from routers import prompts as prompts_router
from routers import settings as settings_router
from routers import templates as templates_router

app.include_router(settings_router.router)
app.include_router(prompts_router.router)
app.include_router(history_router.router)
app.include_router(templates_router.router)
app.include_router(files_router.router)


@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"app_name": settings.APP_NAME},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
