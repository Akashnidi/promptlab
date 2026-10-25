import asyncio
import html
import re
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config import settings
from routers.settings import get_master_password
from services.ai_provider import PROVIDER_MODELS, GroqProvider, get_provider
from services.history import HistoryManager
from services.template_engine import TemplateEngine
from services.vault import Vault

router = APIRouter(prefix="/prompt", tags=["prompt"])

# Inject vault, history, and template engine instances
vault = Vault(settings.VAULT_FILE)
history_manager = HistoryManager(settings.HISTORY_FILE)
template_engine = TemplateEngine()

# Templates
templates = Jinja2Templates(directory="templates")


def format_ai_content(text: str) -> str:
    """Format markdown code blocks into styled <pre><code> tags and convert newlines."""
    if not text:
        return ""

    pattern = r"(```[\w-]*\n[\s\S]*?```)"
    tokens = re.split(pattern, text)
    formatted_parts = []

    for token in tokens:
        if token.startswith("```") and token.endswith("```"):
            lines = token.split("\n", 1)
            first_line = lines[0][3:].strip()
            lang = first_line if first_line else "code"
            code_body = lines[1][:-3] if len(lines) > 1 else ""
            escaped_code = html.escape(code_body.rstrip())
            block = (
                f'<div class="code-container my-3 overflow-hidden rounded-lg border border-slate-800 bg-slate-950 shadow-md">'
                f'  <div class="flex items-center justify-between border-b border-slate-800 bg-slate-900/90 px-3 py-1.5 text-[11px] font-mono text-slate-400">'
                f'    <span>{lang}</span>'
                f'    <button type="button" onclick="navigator.clipboard.writeText(this.closest(\'.code-container\').querySelector(\'code\').innerText); this.innerText=\'Copied!\'; setTimeout(() => this.innerText=\'Copy\', 1500);" class="hover:text-white transition-colors">Copy</button>'
                f'  </div>'
                f'  <pre class="overflow-x-auto p-3 text-xs font-mono text-slate-100"><code>{escaped_code}</code></pre>'
                f'</div>'
            )
            formatted_parts.append(block)
        else:
            escaped_text = html.escape(token)
            escaped_text = escaped_text.replace("\n", "<br>")
            formatted_parts.append(escaped_text)

    return "".join(formatted_parts)


@router.get("/models/{provider}", response_class=HTMLResponse)
@router.get("/models", response_class=HTMLResponse)
async def get_models_for_provider(request: Request, provider: str = "groq"):
    """Return HTML <option> tags for the given provider's supported models."""
    prov_key = provider.strip().lower()

    if prov_key == "groq":
        master_password = get_master_password(request)
        api_key = None
        error_msg = None

        if not master_password:
            error_msg = "Vault is locked. No active session."
        elif not vault.is_initialized():
            error_msg = "Vault is not initialized."
        elif not vault.verify_master_password(master_password):
            error_msg = "Vault master password verification failed."
        else:
            try:
                api_key = vault.get_secret(master_password, "groq")
                if not api_key:
                    error_msg = "No Groq API key found in vault."
            except Exception as e:
                error_msg = f"Vault read error: {e}"

        models: list[str] = []
        if api_key and not error_msg:
            try:
                groq_prov = GroqProvider(api_key=api_key)
                models = await groq_prov.list_available_models()
            except Exception as e:
                error_msg = str(e)

        if error_msg or not models:
            e = error_msg or "Empty model list returned"
            print(f"[Model Sync] Failed: {e}")
            fallback_models = GroqProvider.DEFAULT_FALLBACK_MODELS
            options = ["<option disabled>⚠️ Could not sync (check vault/API key)</option>"]
            for idx, m in enumerate(fallback_models):
                selected = " selected" if idx == 0 else ""
            return HTMLResponse(content="\n".join(options), headers={"HX-Trigger": "modelsSynced"})

        # Successfully synced models
        default_model = "allam-2-7b" if "allam-2-7b" in models else (models[0] if models else "")
        options = []
        for m in models:
            if m == default_model:
                options.append(f'<option value="{m}" selected>{m}</option>')
            else:
                options.append(f'<option value="{m}">{m}</option>')

        return HTMLResponse(content="\n".join(options), headers={"HX-Trigger": "modelsSynced"})

    else:
        models = PROVIDER_MODELS.get(prov_key, [])
        if not models:
            return HTMLResponse("<option value=''>No models found</option>")

        default_model = models[0] if models else ""
        options = []
        for m in models:
            if m == default_model:
                options.append(f'<option value="{m}" selected>{m}</option>')
            else:
                options.append(f'<option value="{m}">{m}</option>')

        return HTMLResponse(content="\n".join(options))


KNOWN_ARENA_MODELS = {
    "allam-2-7b": {
        "label": "Allam 2 7B",
        "badge": "FAST",
        "badge_class": "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
        "description": "High-efficiency multilingual language model",
    },
    "qwen/qwen3.8-27b": {
        "label": "Qwen 3.8 27B",
        "badge": "REASONING",
        "badge_class": "bg-purple-500/10 text-purple-400 border border-purple-500/20",
        "description": "Advanced reasoning and mathematical reasoning model",
    },
    "openai/gpt-oss-20b": {
        "label": "GPT OSS 20B",
        "badge": "GENERAL",
        "badge_class": "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20",
        "description": "Open weights general instruction model",
    },
    "openai/gpt-oss-120b": {
        "label": "GPT OSS 120B",
        "badge": "FLAGSHIP",
        "badge_class": "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20",
        "description": "Flagship 120B reasoning and synthesis model",
    },
}


def get_arena_model_meta(model_id: str) -> dict:
    if model_id in KNOWN_ARENA_MODELS:
        meta = dict(KNOWN_ARENA_MODELS[model_id])
        meta["id"] = model_id
        return meta
    clean_label = model_id.replace("-", " ").title()
    return {
        "id": model_id,
        "label": clean_label,
        "badge": "CHAT",
        "badge_class": "bg-amber-500/10 text-amber-400 border border-amber-500/20",
        "description": f"Active model ({model_id})",
    }


@router.get("/arena-models", response_class=HTMLResponse)
async def get_arena_models(request: Request):
    """Return HTML partial of model checkboxes for the LLM Arena."""
    master_password = get_master_password(request)
    api_key = None
    if master_password and vault.is_initialized() and vault.verify_master_password(master_password):
        try:
            api_key = vault.get_secret(master_password, "groq")
        except Exception:
            api_key = None

    models = []
    if api_key:
        try:
            groq_prov = GroqProvider(api_key=api_key)
            models = await groq_prov.list_available_models()
        except Exception:
            models = []

    if not models:
        models = GroqProvider.DEFAULT_FALLBACK_MODELS

    core_order = [
        "allam-2-7b",
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
    ]
    ordered_models = []
    for cm in core_order:
        if cm in models:
            ordered_models.append(cm)
    for m in models:
        if m not in ordered_models and not any(x in m.lower() for x in ["whisper", "tts", "audio", "guard"]):
            ordered_models.append(m)

    if not ordered_models:
        ordered_models = core_order

    arena_models = [get_arena_model_meta(m) for m in ordered_models]

    return templates.TemplateResponse(
        request=request,
        name="partials/arena_checkboxes.html",
        context={"arena_models": arena_models},
    )


@router.get("/providers", response_class=HTMLResponse)
async def list_prompt_providers(request: Request):
    """Return an HTML partial listing providers and whether their keys are configured."""
    master_pwd = get_master_password(request)
    configured_providers = set(vault.list_providers()) if vault.is_initialized() else set()

    items = []
    for prov, models in PROVIDER_MODELS.items():
        has_key = prov in configured_providers
        items.append({
            "name": prov,
            "has_key": has_key,
            "models_count": len(models),
        })

    return templates.TemplateResponse(
        request=request,
        name="partials/provider_status.html",
        context={"providers": items},
    )


@router.post("/execute", response_class=HTMLResponse)
async def execute_prompt(
    request: Request,
    prompt: str = Form(...),
    system_prompt: str = Form(""),
    provider: str = Form("groq"),
    model: str = Form("llama-3.3-70b-versatile"),
    temperature: float = Form(0.7),
    max_tokens: int = Form(1024),
    prompt_mode: Optional[str] = Form(None),
    template_name: Optional[str] = Form(None),
):
    """Execute a prompt against the selected AI provider, rendering templates if dynamic variables are present."""
    timestamp = int(time.time() * 1000)

    # a. Check master password / vault lock
    master_password = get_master_password(request)
    if not master_password or not vault.verify_master_password(master_password):
        return templates.TemplateResponse(
            request=request,
            name="partials/error.html",
            context={
                "error_message": "🔒 Vault is locked. Please unlock in Settings before executing prompts.",
                "timestamp": timestamp,
            },
        )

    # b. Retrieve provider API key from vault
    try:
        api_key = vault.get_secret(master_password, provider)
    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="partials/error.html",
            context={
                "error_message": f"Vault retrieval error: {str(e)}",
                "timestamp": timestamp,
            },
        )

    if not api_key:
        return templates.TemplateResponse(
            request=request,
            name="partials/error.html",
            context={
                "error_message": f"No API key found for {provider.capitalize()}. Please add it in Settings.",
                "timestamp": timestamp,
            },
        )

    # c. Instantiate provider
    try:
        provider_instance = get_provider(provider, api_key)
    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="partials/error.html",
            context={
                "error_message": f"Failed to initialize provider: {str(e)}",
                "timestamp": timestamp,
            },
        )

    # d. Handle template mode and variable rendering
    form_data = await request.form()
    variables = {}
    for key, val in form_data.items():
        if key.startswith("var_"):
            variables[key[4:]] = val

    is_template = (prompt_mode == "template") or bool(variables)
    template_raw = None
    effective_prompt = prompt

    if is_template:
        template_raw = prompt
        effective_prompt = template_engine.render(template_raw, variables)

    # e. Generate response
    try:
        result = await provider_instance.generate(
            prompt=effective_prompt,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="partials/error.html",
            context={
                "error_message": str(e),
                "timestamp": timestamp,
            },
        )

    # f. Save execution entry to history
    try:
        history_entry = history_manager.add_entry(
            prompt=effective_prompt,
            response=result.get("content", ""),
            model=model,
            provider=provider,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            usage=result.get("usage"),
            latency_ms=result.get("latency_ms", 0.0),
            prompt_type="template" if is_template else "simple",
            template_name=template_name,
        )
        history_id = history_entry.get("id")
    except Exception:
        history_id = None

    # g. Format and render response
    formatted_content = format_ai_content(result.get("content", ""))
    created_at_time = datetime.now().strftime("%I:%M:%S %p")

    return templates.TemplateResponse(
        request=request,
        name="partials/response.html",
        context={
            "content": result.get("content", ""),
            "formatted_content": formatted_content,
            "provider": result.get("provider", provider),
            "model": result.get("model", model),
            "usage": result.get("usage", {}),
            "latency_ms": result.get("latency_ms", 0),
            "timestamp": timestamp,
            "created_at_time": created_at_time,
            "history_id": history_id,
        },
        headers={"HX-Trigger": "historyUpdated"},
    )


@router.post("/compare", response_class=HTMLResponse)
async def compare_prompts(
    request: Request,
    prompt: str = Form(...),
    system_prompt: str = Form(""),
    temperature: float = Form(0.7),
    max_tokens: int = Form(1024),
):
    """Execute a prompt concurrently across 2 to 3 chosen models in the LLM Arena."""
    timestamp = int(time.time() * 1000)

    # 1. Read form data to extract models list (supports multiple 'models' keys)
    form_data = await request.form()
    models = form_data.getlist("models")
    if not models and "models[]" in form_data:
        models = form_data.getlist("models[]")

    # Filter out empty or whitespace-only items
    models = [m.strip() for m in models if m and m.strip()]

    # Guardrails: Min 2, Max 3 models
    if len(models) < 2:
        return templates.TemplateResponse(
            request=request,
            name="partials/error.html",
            context={
                "error_message": "⚠️ Please select at least 2 models to compare in the LLM Arena.",
                "timestamp": timestamp,
            },
        )

    if len(models) > 3:
        return templates.TemplateResponse(
            request=request,
            name="partials/error.html",
            context={
                "error_message": "⚠️ Maximum 3 models can be compared at once to conserve tokens.",
                "timestamp": timestamp,
            },
        )

    if not prompt or not prompt.strip():
        return templates.TemplateResponse(
            request=request,
            name="partials/error.html",
            context={
                "error_message": "⚠️ Please enter a prompt to compare.",
                "timestamp": timestamp,
            },
        )

    # 2. Check master password / vault lock
    master_password = get_master_password(request)
    if not master_password or not vault.verify_master_password(master_password):
        return templates.TemplateResponse(
            request=request,
            name="partials/error.html",
            context={
                "error_message": "🔒 Vault is locked. Please unlock in Settings before running the Arena.",
                "timestamp": timestamp,
            },
        )

    # 3. Retrieve Groq API key from vault
    try:
        api_key = vault.get_secret(master_password, "groq")
    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="partials/error.html",
            context={
                "error_message": f"Vault retrieval error: {str(e)}",
                "timestamp": timestamp,
            },
        )

    if not api_key:
        return templates.TemplateResponse(
            request=request,
            name="partials/error.html",
            context={
                "error_message": "No Groq API key found in vault. Please add your Groq key in Settings.",
                "timestamp": timestamp,
            },
        )

    try:
        provider_instance = GroqProvider(api_key=api_key)
    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="partials/error.html",
            context={
                "error_message": f"Failed to initialize Groq provider: {str(e)}",
                "timestamp": timestamp,
            },
        )

    # 4. Define async worker for each model
    async def run_single_model(model_id: str):
        start_t = time.perf_counter()
        try:
            res = await provider_instance.generate(
                prompt=prompt,
                model=model_id,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return {
                "success": True,
                "model": model_id,
                "provider": "groq",
                "content": res.get("content", ""),
                "formatted_content": format_ai_content(res.get("content", "")),
                "usage": res.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
                "latency_ms": res.get("latency_ms", round((time.perf_counter() - start_t) * 1000, 2)),
                "error": None,
            }
        except Exception as ex:
            latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
            return {
                "success": False,
                "model": model_id,
                "provider": "groq",
                "content": "",
                "formatted_content": "",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "latency_ms": latency_ms,
                "error": str(ex),
            }

    # 5. Execute in parallel with asyncio.gather
    tasks = [run_single_model(m) for m in models]
    results = await asyncio.gather(*tasks)

    # 6. Compute badges: Fastest & Fewest Tokens
    successful_results = [r for r in results if r["success"]]
    if len(successful_results) >= 2:
        min_latency = min(r["latency_ms"] for r in successful_results)
        min_tokens = min(r["usage"]["total_tokens"] for r in successful_results)

        for r in results:
            if r["success"]:
                r["is_fastest"] = (r["latency_ms"] == min_latency)
                r["is_most_efficient"] = (r["usage"]["total_tokens"] == min_tokens)
            else:
                r["is_fastest"] = False
                r["is_most_efficient"] = False
    else:
        for r in results:
            r["is_fastest"] = False
            r["is_most_efficient"] = False

    # 7. Aggregate statistics
    combined_tokens = sum(r["usage"]["total_tokens"] for r in results if r["success"])
    total_prompt_tokens = sum(r["usage"]["prompt_tokens"] for r in results if r["success"])
    total_completion_tokens = sum(r["usage"]["completion_tokens"] for r in results if r["success"])
    max_latency_ms = max((r["latency_ms"] for r in results), default=0.0)
    created_at_time = datetime.now().strftime("%I:%M:%S %p")

    # 8. Save arena comparison record to history
    try:
        history_entry = history_manager.add_entry(
            prompt=prompt,
            response=f"⚖️ LLM Arena comparison across {len(models)} models: {', '.join(models)}",
            model=", ".join(models),
            provider="groq",
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            usage={
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": combined_tokens,
            },
            latency_ms=max_latency_ms,
            prompt_type="arena",
            tags=["arena", f"{len(models)}_models"],
        )
        history_id = history_entry.get("id")
    except Exception:
        history_id = None

    return templates.TemplateResponse(
        request=request,
        name="partials/comparison_results.html",
        context={
            "prompt": prompt,
            "system_prompt": system_prompt,
            "models": models,
            "results": results,
            "combined_tokens": combined_tokens,
            "model_count": len(models),
            "timestamp": timestamp,
            "created_at_time": created_at_time,
            "history_id": history_id,
        },
        headers={"HX-Trigger": "historyUpdated"},
    )



