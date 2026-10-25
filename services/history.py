import json
import os
import tempfile
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class HistoryManager:
    def __init__(self, history_file: str):
        self.history_path = Path(history_file)

    def _load(self) -> List[Dict[str, Any]]:
        """Read history from JSON file safely. Return [] if empty, missing or corrupt."""
        if not self.history_path.exists():
            return []
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return []
                data = json.loads(content)
                if isinstance(data, list):
                    return data
                return []
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, entries: List[Dict[str, Any]]) -> None:
        """Write safely to file using an atomic write approach."""
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write via temp file in the same directory to avoid half-written files
        temp_file = tempfile.NamedTemporaryFile(
            "w",
            dir=str(self.history_path.parent),
            delete=False,
            encoding="utf-8",
        )
        try:
            json.dump(entries, temp_file, indent=2, ensure_ascii=False)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_file.close()
            os.replace(temp_file.name, str(self.history_path))
        except Exception:
            if os.path.exists(temp_file.name):
                os.remove(temp_file.name)
            raise

    def add_entry(
        self,
        prompt: str,
        response: str,
        model: str,
        provider: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        usage: Optional[Dict[str, int]] = None,
        latency_ms: float = 0.0,
        tags: Optional[List[str]] = None,
        prompt_type: str = "simple",
        template_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new history entry, prepend to list (newest first), save, and return entry."""
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt": prompt,
            "response": response,
            "system_prompt": system_prompt,
            "model": model,
            "provider": provider,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "usage": usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "latency_ms": latency_ms,
            "tags": tags or [],
            "prompt_type": prompt_type,
            "template_name": template_name,
            "rating": None,  # 1-5 integer or None
        }

        entries = self._load()
        entries.insert(0, entry)
        self._save(entries)
        return entry

    def get_all(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return the most recent entries up to limit."""
        entries = self._load()
        return entries[:limit]

    def get_by_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Find and return an entry by its ID."""
        entries = self._load()
        for e in entries:
            if e.get("id") == entry_id:
                return e
        return None

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Case-insensitive search matching prompt, response, model, or tags."""
        if not query or not query.strip():
            return self.get_all(50)

        q = query.strip().lower()
        entries = self._load()
        matches = []
        for e in entries:
            prompt_match = q in e.get("prompt", "").lower()
            response_match = q in e.get("response", "").lower()
            model_match = q in e.get("model", "").lower()
            tags_match = any(q in str(t).lower() for t in e.get("tags", []))
            if prompt_match or response_match or model_match or tags_match:
                matches.append(e)
        return matches

    def delete_entry(self, entry_id: str) -> bool:
        """Remove entry by ID and save. Return True if deleted."""
        entries = self._load()
        original_len = len(entries)
        entries = [e for e in entries if e.get("id") != entry_id]
        if len(entries) < original_len:
            self._save(entries)
            return True
        return False

    def clear_all(self) -> None:
        """Clear all history entries."""
        self._save([])

    def update_rating(self, entry_id: str, rating: int) -> bool:
        """Update rating (1-5) and save."""
        if rating < 1 or rating > 5:
            return False
        entries = self._load()
        updated = False
        for e in entries:
            if e.get("id") == entry_id:
                e["rating"] = rating
                updated = True
                break
        if updated:
            self._save(entries)
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Compute summary statistics across all prompt executions."""
        entries = self._load()
        total_prompts = len(entries)
        total_tokens = sum(e.get("usage", {}).get("total_tokens", 0) for e in entries)
        total_latency = sum(e.get("latency_ms", 0.0) for e in entries)
        avg_latency_ms = round(total_latency / total_prompts, 2) if total_prompts > 0 else 0.0

        models = [e.get("model") for e in entries if e.get("model")]
        favorite_model = Counter(models).most_common(1)[0][0] if models else "None"

        return {
            "total_prompts": total_prompts,
            "total_tokens": total_tokens,
            "avg_latency_ms": avg_latency_ms,
            "favorite_model": favorite_model,
        }
