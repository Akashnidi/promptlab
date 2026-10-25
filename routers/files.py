import os
import re
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from config import settings

router = APIRouter(prefix="/files", tags=["files"])

# Templates
templates = Jinja2Templates(directory="templates")

# Allowed extensions & max size
ALLOWED_EXTENSIONS = {".txt", ".j2", ".jinja2", ".yaml", ".yml", ".json", ".md"}
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1MB


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal, strip directories, and replace spaces."""
    if not filename:
        return "upload.txt"

    # Strip directory separators across Windows and Linux
    base = os.path.basename(filename.strip().replace("\\", "/"))
    base = base.replace(" ", "_")

    # Keep only safe alphanumeric, underscores, hyphens, and dots
    safe = re.sub(r"[^\w\.\-]", "", base)
    safe = safe.lstrip(".")

    if not safe:
        safe = "upload.txt"
    return safe


def get_upload_dir() -> Path:
    """Ensure upload directory exists and return resolved Path."""
    p = Path(settings.UPLOAD_DIR).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_files_metadata(upload_dir: Path) -> List[dict]:
    """Retrieve metadata list for all files in the upload directory."""
    if not upload_dir.exists():
        return []

    items = []
    for file_path in upload_dir.iterdir():
        if file_path.is_file():
            try:
                stat = file_path.stat()
                size_bytes = stat.st_size
                if size_bytes < 1024:
                    size_str = f"{size_bytes} B"
                else:
                    size_str = f"{size_bytes / 1024:.1f} KB"

                ext = file_path.suffix.lower()
                mod_time = datetime.fromtimestamp(stat.st_mtime).strftime("%b %d, %H:%M")

                items.append({
                    "filename": file_path.name,
                    "size_str": size_str,
                    "size_bytes": size_bytes,
                    "extension": ext,
                    "modified_time": mod_time,
                    "mtime": stat.st_mtime,
                })
            except OSError:
                continue

    # Sort newest first
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items


@router.get("/list", response_class=HTMLResponse)
async def list_files(request: Request):
    """Return HTML partial listing all uploaded template/prompt files."""
    upload_dir = get_upload_dir()
    files = get_files_metadata(upload_dir)

    return templates.TemplateResponse(
        request=request,
        name="partials/file_list.html",
        context={"files": files},
    )


@router.post("/upload", response_class=HTMLResponse)
async def upload_file(request: Request, file: UploadFile = File(...)):
    """Validate, sanitize, and save uploaded prompt/template file."""
    upload_dir = get_upload_dir()

    # 1. Sanitize filename
    safe_name = sanitize_filename(file.filename or "upload.txt")
    ext = Path(safe_name).suffix.lower()

    # 2. Validate extension
    if ext not in ALLOWED_EXTENSIONS:
        files = get_files_metadata(upload_dir)
        return templates.TemplateResponse(
            request=request,
            name="partials/file_list.html",
            context={
                "files": files,
                "error_message": f"Unsupported extension '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            },
        )

    # 3. Read and validate content size
    try:
        content_bytes = await file.read()
    except Exception as e:
        files = get_files_metadata(upload_dir)
        return templates.TemplateResponse(
            request=request,
            name="partials/file_list.html",
            context={
                "files": files,
                "error_message": f"Failed to read file: {str(e)}",
            },
        )

    if len(content_bytes) > MAX_FILE_SIZE:
        files = get_files_metadata(upload_dir)
        return templates.TemplateResponse(
            request=request,
            name="partials/file_list.html",
            context={
                "files": files,
                "error_message": "File exceeds the 1MB maximum size limit.",
            },
        )

    # 4. Validate UTF-8 encoding (reject binary)
    try:
        content_text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        files = get_files_metadata(upload_dir)
        return templates.TemplateResponse(
            request=request,
            name="partials/file_list.html",
            context={
                "files": files,
                "error_message": "File must be valid UTF-8 text (binary files are not permitted).",
            },
        )

    # 5. Handle duplicate filenames by appending counter
    target_path = upload_dir / safe_name
    stem = target_path.stem
    counter = 1
    while target_path.exists():
        target_path = upload_dir / f"{stem}_{counter}{ext}"
        counter += 1

    # Verify no path traversal outside upload_dir
    try:
        if not target_path.resolve().is_relative_to(upload_dir):
            raise HTTPException(status_code=400, detail="Invalid path traversal detected.")
    except (ValueError, AttributeError):
        if not str(target_path.resolve()).startswith(str(upload_dir)):
            raise HTTPException(status_code=400, detail="Invalid path traversal detected.")

    target_path.write_text(content_text, encoding="utf-8")

    files = get_files_metadata(upload_dir)
    return templates.TemplateResponse(
        request=request,
        name="partials/file_list.html",
        context={
            "files": files,
            "success_message": f"Successfully uploaded '{target_path.name}'",
        },
    )


@router.get("/content/{filename}")
async def get_file_content(filename: str):
    """Read text content of a sanitized file from upload directory."""
    safe_name = sanitize_filename(filename)
    upload_dir = get_upload_dir()
    file_path = (upload_dir / safe_name).resolve()

    try:
        is_safe = file_path.is_relative_to(upload_dir)
    except (ValueError, AttributeError):
        is_safe = str(file_path).startswith(str(upload_dir))

    if not is_safe or not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found.")

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")

    return JSONResponse(content={
        "filename": safe_name,
        "content": content,
        "extension": file_path.suffix.lower(),
    })


@router.delete("/{filename}", response_class=HTMLResponse)
async def delete_file(request: Request, filename: str):
    """Delete a sanitized file from upload directory."""
    safe_name = sanitize_filename(filename)
    upload_dir = get_upload_dir()
    file_path = (upload_dir / safe_name).resolve()

    try:
        is_safe = file_path.is_relative_to(upload_dir)
    except (ValueError, AttributeError):
        is_safe = str(file_path).startswith(str(upload_dir))

    if is_safe and file_path.exists() and file_path.is_file():
        try:
            file_path.unlink()
        except OSError:
            pass

    files = get_files_metadata(upload_dir)
    return templates.TemplateResponse(
        request=request,
        name="partials/file_list.html",
        context={"files": files},
    )
