from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from services.template_engine import TemplateEngine

router = APIRouter(prefix="/templates", tags=["templates"])

# Template engine instance
template_engine = TemplateEngine()

# Templates directory
templates = Jinja2Templates(directory="templates")

PROMPT_TEMPLATES_DIR = Path("prompt_templates")

BUNDLED_TEMPLATES_METADATA = [
    {
        "id": "summarize",
        "filename": "summarize.j2",
        "title": "Text Summarizer",
        "description": "Summarize content with audience and bullet point count controls",
    },
    {
        "id": "chain_of_thought",
        "filename": "chain_of_thought.j2",
        "title": "Chain of Thought Problem Solver",
        "description": "Step-by-step reasoning with sub-problems and context",
    },
    {
        "id": "few_shot",
        "filename": "few_shot.j2",
        "title": "Few-Shot Sentiment Classifier",
        "description": "In-context demonstration examples for accurate classification",
    },
    {
        "id": "code_review",
        "filename": "code_review.j2",
        "title": "Code Review & Quality Analysis",
        "description": "Constructive feedback on security, performance, and readability",
    },
]


@router.post("/detect-variables", response_class=HTMLResponse)
async def detect_variables(
    request: Request,
    template_text: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
):
    """Scan template text and return dynamic variable input fields partial."""
    text = template_text if template_text is not None else (prompt or "")
    variables = template_engine.extract_variables(text)

    return templates.TemplateResponse(
        request=request,
        name="partials/template_vars.html",
        context={"variables": variables},
    )


@router.post("/preview", response_class=HTMLResponse)
async def preview_template(
    request: Request,
    template_text: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
):
    """Render template with submitted dynamic variables and return preview card partial."""
    form_data = await request.form()
    text = template_text if template_text is not None else (prompt or form_data.get("prompt") or "")

    # Extract dynamic variable fields prefixed with var_
    variables = {}
    for key, value in form_data.items():
        if key.startswith("var_"):
            var_name = key[4:]
            variables[var_name] = value

    rendered = template_engine.render(str(text), variables)

    return templates.TemplateResponse(
        request=request,
        name="partials/template_preview.html",
        context={"rendered_text": rendered},
    )


@router.get("/bundled")
async def list_bundled_templates():
    """Return catalog of available bundled templates."""
    return JSONResponse(content=BUNDLED_TEMPLATES_METADATA)


@router.get("/load/{name}", response_class=PlainTextResponse)
async def load_template_content(name: str):
    """Load and return the raw content of a bundled template file."""
    filename = name if name.endswith(".j2") else f"{name}.j2"
    file_path = PROMPT_TEMPLATES_DIR / filename

    if not file_path.exists():
        return PlainTextResponse(f"Template '{name}' not found.", status_code=404)

    content, _ = template_engine.load_from_file(str(file_path))
    return PlainTextResponse(content)
