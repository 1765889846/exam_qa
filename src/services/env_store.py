"""读写项目根目录 .env。"""

from __future__ import annotations

import os
import re
from pathlib import Path

from src.exceptions import BadRequestException

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"

MASKED_SECRET = "***"
_ENV_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

_env_created = False


def ensure_env_file() -> bool:
    """若 .env 不存在则从 .env.example 复制。返回是否新建。"""
    global _env_created
    if ENV_PATH.exists():
        return False
    if ENV_EXAMPLE_PATH.exists():
        ENV_PATH.write_text(
            ENV_EXAMPLE_PATH.read_text(encoding="utf-8"),
            encoding="utf-8",
            newline="\n",
        )
        _env_created = True
        return True
    return False


def env_was_created() -> bool:
    return _env_created


def env_file_writable() -> bool:
    path = ENV_PATH
    if path.exists():
        return os.access(path, os.W_OK)
    parent = path.parent
    return parent.exists() and os.access(parent, os.W_OK)


def _format_env_value(value: str) -> str:
    if value == "":
        return ""
    if any(ch in value for ch in " #\"'\\"):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def write_env_updates(updates: dict[str, str]) -> None:
    if not updates:
        return
    if not env_file_writable():
        raise BadRequestException("无法写入 .env，请检查文件权限")

    ensure_env_file()
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines and ENV_PATH.read_text(encoding="utf-8") == "":
        lines = []

    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            match = _ENV_KEY_RE.match(stripped)
            if match:
                key = match.group(1)
                if key in updates:
                    output.append(f"{key}={_format_env_value(updates[key])}\n")
                    seen.add(key)
                    continue
        output.append(line if line.endswith("\n") else f"{line}\n")

    for key, value in updates.items():
        if key not in seen:
            output.append(f"{key}={_format_env_value(value)}\n")

    ENV_PATH.write_text("".join(output), encoding="utf-8", newline="\n")
