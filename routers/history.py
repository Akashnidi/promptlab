from typing import Optional
from pathlib import Path

from fastapi import APIRouter, Form, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from config import settings
from services.history import HistoryManager

router = APIRouter(prefix="/history", tags=["history"])

# Instantiate HistoryManager
history_manager = HistoryManager(settings.HISTORY_FILE)

# Templates
templates = Jinja2Templates(directory="templates")


@router.get("/sidebar", response_class=HTMLResponse)
async def get_sidebar_history(request: Request):
    """Return HTML partial of recent history items for the sidebar."""
    entries = history_manager.get_all(30)
    return templates.TemplateResponse(
        request=request,
        name="partials/history_list.html",
        context={"entries": entries},
    )


@router.get("/search", response_class=HTMLResponse)
async def search_history(request: Request, q: str = Query(default="")):
    """Search history by prompt, response, model, or tags and return partial."""
    if not q or not q.strip():
        entries = history_manager.get_all(30)
    else:
        entries = history_manager.search(q)

    return templates.TemplateResponse(
        request=request,
        name="partials/history_list.html",
        context={"entries": entries, "query": q},
    )


@router.get("/item/{entry_id}", response_class=HTMLResponse)
async def get_history_item(request: Request, entry_id: str):
    """Return detail card/modal partial for a specific history item."""
    entry = history_manager.get_by_id(entry_id)
    if not entry:
        return HTMLResponse(
            """<div class="p-4 text-xs text-red-400 bg-red-950/80 rounded-lg">
                History entry not found.
            </div>""",
            status_code=404,
        )

    # Format code blocks if prompt router's helper is available
    from routers.prompts import format_ai_content
    formatted_response = format_ai_content(entry.get("response", ""))

    return templates.TemplateResponse(
        request=request,
        name="partials/history_detail_modal.html",
        context={
            "entry": entry,
            "formatted_response": formatted_response,
        },
    )


@router.delete("/{entry_id}", response_class=HTMLResponse)
async def delete_history_item(request: Request, entry_id: str):
    """Delete a history item and return the refreshed sidebar list."""
    history_manager.delete_entry(entry_id)
    entries = history_manager.get_all(30)
    return templates.TemplateResponse(
        request=request,
        name="partials/history_list.html",
        context={"entries": entries},
    )


@router.post("/{entry_id}/rate", response_class=HTMLResponse)
async def rate_history_item(
    request: Request,
    entry_id: str,
    rating: int = Query(...),
):
    """Update 1-5 rating for a history entry and return refreshed sidebar list."""
    history_manager.update_rating(entry_id, rating)
    entries = history_manager.get_all(30)
    return templates.TemplateResponse(
        request=request,
        name="partials/history_list.html",
        context={"entries": entries},
    )


@router.post("/clear", response_class=HTMLResponse)
async def clear_history(request: Request):
    """Clear all history entries and return empty list partial."""
    history_manager.clear_all()
    return templates.TemplateResponse(
        request=request,
        name="partials/history_list.html",
        context={"entries": []},
    )


@router.get("/export")
async def export_history():
    """Export the history.json file as a downloadable attachment."""
    path = history_manager.history_path
    if not path.exists():
        history_manager.clear_all()

    return FileResponse(
        path=str(path),
        filename="promptlab_history.json",
        media_type="application/json",
    )

