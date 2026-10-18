import os
from pathlib import Path
from typing import List, Optional

import yaml
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

BASE = Path(__file__).parent

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}
ALIASES = {"num_workers": "workers"}
INT_KEYS = {"port", "workers"}
BOOL_KEYS = {"debug"}

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def norm_key(k: str, strip_prefix: bool = True) -> str:
    k = k.strip().lower()
    if strip_prefix and k.startswith("app_"):
        k = k[4:]
    return ALIASES.get(k, k)


def coerce(key: str, value):
    if key in INT_KEYS:
        return int(str(value).strip())
    if key in BOOL_KEYS:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "yes", "on")
    return str(value)


def load_yaml(env: str) -> dict:
    p = BASE / f"config.{env}.yaml"
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text()) or {}
    return {norm_key(k, False): v for k, v in data.items()}


def load_dotenv() -> dict:
    p = BASE / ".env"
    out = {}
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[norm_key(k)] = v.strip().strip('"').strip("'")
    return out


def load_os_env() -> dict:
    return {norm_key(k): v for k, v in os.environ.items() if k.upper().startswith("APP_")}


def apply(cfg: dict, layer: dict):
    for k, v in layer.items():
        try:
            cfg[k] = coerce(k, v)
        except (ValueError, TypeError):
            pass  # ignore uncoercible values


@app.get("/effective-config")
def effective_config(set: Optional[List[str]] = Query(default=None)):
    env = os.environ.get("APP_ENV", "development")
    cfg = dict(DEFAULTS)
    apply(cfg, load_yaml(env))
    apply(cfg, load_dotenv())
    apply(cfg, load_os_env())
    cli = {}
    for item in set or []:
        if "=" in item:
            k, v = item.split("=", 1)
            cli[norm_key(k)] = v
    apply(cfg, cli)
    cfg["api_key"] = "****"
    return cfg
