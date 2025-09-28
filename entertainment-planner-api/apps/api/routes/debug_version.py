import sys, os, importlib, inspect, hashlib
from fastapi import APIRouter

router = APIRouter()

def fp(mod):
    try:
        m = importlib.import_module(mod)
        s = inspect.getsource(m)
        return {"file": getattr(m,"__file__",None), "md5": hashlib.md5(s.encode()).hexdigest()}
    except Exception as e:
        return {"error": repr(e)}

@router.get("/debug/version")
def version():
    mods = [
        "apps.api.routes.compose",
        "apps.places.services.search",
        "apps.places.schemas.vibes",
    ]
    return {
        "python": sys.version,
        "sys_path": sys.path,
        "fingerprints": {m: fp(m) for m in mods},
    }
