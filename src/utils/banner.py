"""Startup banner and check summary for console output."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from src.utils.logging import BRIGHT, CYAN, DIM, GREEN, RED, RESET, YELLOW, use_color


@dataclass(frozen=True)
class StartupCheck:
    name: str
    status: str  # ok | warn | error
    detail: str | None = None


def _status_icon(status: str) -> tuple[str, str]:
    if not use_color():
        icons = {"ok": "+", "warn": "!", "error": "x"}
        return icons.get(status, "?"), ""
    mapping = {
        "ok": (f"{GREEN}✓{RESET}", GREEN),
        "warn": (f"{YELLOW}!{RESET}", YELLOW),
        "error": (f"{RED}✗{RESET}", RED),
    }
    icon, color = mapping.get(status, ("?", ""))
    return icon, color


def log_startup_banner(
    *,
    app_name: str,
    version: str,
    port: int,
    web_ui: str,
    web_mounted: bool,
    api_prefix: str,
    checks: list[StartupCheck],
    elapsed: float,
) -> None:
    """Print a ly-next / XRK-style startup summary to stdout."""
    stream = sys.stdout
    c = use_color()
    title = f"{CYAN}{BRIGHT}{app_name}{RESET}" if c else app_name
    dim = DIM if c else ""
    reset = RESET if c else ""

    border = "─" * 44
    stream.write("\n")
    stream.write(f"  {dim}┌{border}┐{reset}\n")
    stream.write(f"  {dim}│{reset}  {title}  {dim}·  本地 RAG 复习助手 v{version}{reset}\n")
    stream.write(f"  {dim}└{border}┘{reset}\n\n")

    stream.write(f"  {dim}组件{reset}\n")
    for check in checks:
        icon, _ = _status_icon(check.status)
        line = f"  {icon} {check.name:<10}"
        if check.detail:
            line += f"  {dim}{check.detail}{reset}" if c else f"  {check.detail}"
        stream.write(line + "\n")

    stream.write(f"\n  {dim}访问{reset}\n")
    if web_mounted:
        stream.write(f"  {GREEN if c else ''}→ 工作台{reset}   {web_ui}\n")
    else:
        stream.write(
            f"  {GREEN if c else ''}→ 工作台{reset}   http://127.0.0.1:{port}/"
            f"  {dim}(pnpm install && pnpm build 后重启){reset}\n",
        )
    stream.write(
        f"  {GREEN if c else ''}→ API{reset}      http://127.0.0.1:{port}{api_prefix}\n",
    )
    stream.write(
        f"  {GREEN if c else ''}→ 文档{reset}      http://127.0.0.1:{port}/docs\n",
    )
    stream.write(f"\n  {dim}就绪 {elapsed:.1f}s{reset}\n\n")
    stream.flush()
