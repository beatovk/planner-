from __future__ import annotations

import copy
import logging
import os
import threading
import time
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)
_CACHE: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()


def load_yaml_cached(
    path: str,
    *,
    default: Optional[Dict[str, Any]] = None,
    ttl_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """Read YAML once per TTL; return a defensive copy and fall back to default on errors."""
    from apps.core.config import settings

    ttl = ttl_seconds if ttl_seconds is not None else settings.config_cache_ttl_s
    abs_path = os.path.abspath(path)
    try:
        mtime = os.path.getmtime(abs_path)
    except FileNotFoundError:
        mtime = None
    now = time.time()

    with _LOCK:
        cached = _CACHE.get(abs_path)
        if cached:
            is_fresh = ttl is None or (now - cached["loaded_at"] <= ttl)
            if is_fresh and cached["mtime"] == mtime:
                return copy.deepcopy(cached["payload"])

        try:
            with open(abs_path, "r", encoding="utf-8") as fh:
                payload = yaml.safe_load(fh) or {}
        except FileNotFoundError:
            logger.debug("YAML config %s not found; using default", abs_path)
            payload = default or {}
        except Exception as exc:
            logger.warning("Failed to load YAML %s: %s", abs_path, exc)
            payload = default or {}

        _CACHE[abs_path] = {"payload": payload, "mtime": mtime, "loaded_at": now}
        return copy.deepcopy(payload)
