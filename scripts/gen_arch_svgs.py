"""Generate Excalidraw-style architecture SVGs (+ optional .excalidraw sources).

ponytail: deterministic rough paths, no runtime deps beyond stdlib.
Regenerate: uv run python scripts/gen_arch_svgs.py
"""
from __future__ import annotations

import json
import math
import random
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "assets"
EXCAL = ROOT / "excalidraw"

# Excalidraw dark-mode palette (matches excalidraw.com defaults)
BG = "#121212"
INK = "#f5f5f5"
MUTED = "#868e96"
YELLOW = "#fab005"
PINK = "#f783ac"
CYAN = "#4dabf7"
FILL_PINK = "#862e9c33"

FONT_CSS = """
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Patrick+Hand&display=swap');
    text { font-family: 'Patrick Hand', 'Segoe Print', cursive; }
  </style>"""


def _rng(seed: int) -> random.Random:
    return random.Random(seed)


def rough_line(x1: float, y1: float, x2: float, y2: float, seed: int, wobble: float = 1.4) -> str:
    """Wobbly segment — Excalidraw-style imperfect stroke."""
    r = _rng(seed)
    mx, my = (x1 + x2) / 2 + r.uniform(-3, 3), (y1 + y2) / 2 + r.uniform(-3, 3)
    return (
        f"M {x1+r.uniform(-wobble,wobble):.1f},{y1+r.uniform(-wobble,wobble):.1f} "
        f"Q {mx:.1f},{my:.1f} {x2+r.uniform(-wobble,wobble):.1f},{y2+r.uniform(-wobble,wobble):.1f}"
    )


def rough_rect(x: float, y: float, w: float, h: float, seed: int, wobble: float = 1.8) -> str:
    r = _rng(seed)
    pts = [
        (x + r.uniform(-wobble, wobble), y + r.uniform(-wobble, wobble)),
        (x + w + r.uniform(-wobble, wobble), y + r.uniform(-wobble, wobble)),
        (x + w + r.uniform(-wobble, wobble), y + h + r.uniform(-wobble, wobble)),
        (x + r.uniform(-wobble, wobble), y + h + r.uniform(-wobble, wobble)),
    ]
    d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f}"
    for px, py in pts[1:]:
        d += f" L {px:.1f},{py:.1f}"
    return d + " Z"


def arrow(x1: float, y1: float, x2: float, y2: float, seed: int, color: str) -> str:
    """Curved arrow as SVG path group."""
    body = rough_line(x1, y1, x2, y2, seed)
    angle = math.atan2(y2 - y1, x2 - x1)
    ah = 9
    a1, a2 = angle + 2.6, angle - 2.6
    tip = f"M {x2:.1f},{y2:.1f} L {x2 - ah*math.cos(a1):.1f},{y2 - ah*math.sin(a1):.1f}"
    tip += f" M {x2:.1f},{y2:.1f} L {x2 - ah*math.cos(a2):.1f},{y2 - ah*math.sin(a2):.1f}"
    return (
        f'<path d="{body}" stroke="{color}" stroke-width="2" fill="none" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="{tip}" stroke="{color}" stroke-width="2" fill="none" '
        f'stroke-linecap="round"/>'
    )


def hachure_rect(x: float, y: float, w: float, h: float, seed: int, color: str, opacity: float = 0.18) -> str:
    """Diagonal hatch fill like Excalidraw hachure."""
    lines = []
    step = 7
    r = _rng(seed)
    for i in range(int((w + h) / step) + 2):
        sx = x + i * step + r.uniform(-1, 1)
        lines.append(rough_line(sx, y + h, sx - h, y, seed + i, 0.6))
    outline = rough_rect(x, y, w, h, seed + 99)
    hatch = "".join(
        f'<path d="{d}" stroke="{color}" stroke-width="1" opacity="{opacity}" fill="none"/>'
        for d in lines
    )
    return (
        f'<path d="{outline}" fill="{color}" fill-opacity="0.08" stroke="none"/>'
        f"{hatch}"
        f'<path d="{outline}" stroke="{color}" stroke-width="2" fill="none" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
    )


def box(x: float, y: float, w: float, h: float, seed: int, label: str, *, stroke: str = INK, accent: bool = False) -> str:
    s = YELLOW if accent else stroke
    sw = "2.5" if accent else "2"
    outline = rough_rect(x, y, w, h, seed)
    # ponytail: double-stroke mimics Excalidraw sketch redraw
    inner = rough_rect(x + 1.5, y + 1.5, w - 3, h - 3, seed + 7, wobble=0.8)
    txt = (
        f'<text x="{x + 12}" y="{y + h/2 + 5}" fill="{s}" font-size="14">{label}</text>'
        if label
        else ""
    )
    return (
        f'<path d="{outline}" stroke="{s}" stroke-width="{sw}" fill="none" '
        f'stroke-linecap="round" stroke-linejoin="round" opacity="0.95"/>'
        f'<path d="{inner}" stroke="{s}" stroke-width="1" fill="none" opacity="0.35"/>'
        f"{txt}"
    )


def label(x: float, y: float, text: str, *, color: str = INK, size: int = 18) -> str:
    return f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}">{text}</text>'


def svg_open(w: int, h: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" fill="none">'
        f"{FONT_CSS}"
        f'<rect width="{w}" height="{h}" fill="{BG}"/>'
        "<g>"
    )


SVG_CLOSE = "</g></svg>"


def pipelines_svg() -> str:
    parts = [svg_open(920, 230)]
    parts.append(label(24, 38, "【入库】", color=YELLOW))
    parts.append(label(24, 132, "【查询】", color=PINK))
    steps_ingest = ["上传/扫描", "解析", "分块", "向量化", "Chroma + SQLite"]
    xs = [108, 228, 306, 386, 484]
    ws = [90, 50, 50, 70, 156]
    for i, (sx, sw, name) in enumerate(zip(xs, ws, steps_ingest)):
        parts.append(box(sx, 18, sw, 42, 100 + i, name, accent=(i == 4)))
    for i in range(4):
        x1, x2 = xs[i] + ws[i], xs[i + 1]
        c = YELLOW if i == 3 else PINK
        parts.append(arrow(x1 + 4, 40, x2 - 4, 40, 200 + i, c))
    steps_query = ["提问+course", "检索 top_k", "阈值过滤", "LLM 生成", "答案 + citations"]
    qxs = [108, 228, 326, 444, 542]
    qws = [90, 80, 80, 70, 156]
    for i, (sx, sw, name) in enumerate(zip(qxs, qws, steps_query)):
        parts.append(box(sx, 108, sw, 42, 300 + i, name, accent=(i >= 3)))
    for i in range(4):
        x1, x2 = qxs[i] + qws[i], qxs[i + 1]
        c = YELLOW if i >= 2 else PINK
        parts.append(arrow(x1 + 4, 130, x2 - 4, 130, 400 + i, c))
    parts.append(label(326, 158, "score &lt; 阈值", color=PINK, size=11))
    parts.append(
        rough_line(372, 152, 330, 188, 501)
        .replace("M", '<path d="M', 1)
        + f'" stroke="{PINK}" stroke-width="2" stroke-dasharray="5 4" fill="none"/>'
    )
    parts.append(hachure_rect(300, 182, 92, 32, 502, PINK))
    parts.append(label(312, 204, "拒答", color=PINK, size=13))
    parts.append(label(378, 204, "grounded:false", color=PINK, size=11))
    parts.append(label(418, 122, "≥ 阈值", color=YELLOW, size=10))
    parts.append(SVG_CLOSE)
    return "".join(parts)


def agent_svg() -> str:
    parts = [svg_open(720, 360)]
    parts.append(box(48, 42, 180, 120, 600, "", stroke=INK))
    parts.append(label(88, 72, "浏览器 UI", color=YELLOW, size=17))
    parts.append(label(68, 98, "www/sz · sz-docs · sz-cfg", size=12))
    parts.append(label(78, 122, "对话 · 资料 · 设置", size=13))
    parts.append(label(108, 148, "只调 API", color=MUTED, size=12))
    parts.append(arrow(232, 102, 352, 102, 610, YELLOW))
    parts.append(label(262, 88, "HTTP", color=YELLOW, size=13))
    parts.append(label(252, 118, "/api/v1/*", size=12))
    parts.append(box(358, 42, 304, 126, 620, "", stroke=INK))
    parts.append(label(388, 78, "本地 FastAPI", color=YELLOW, size=17))
    parts.append(label(368, 108, "入库 · 检索 · 生成 · 拒答", size=14))
    parts.append(label(378, 132, "llm_providers · embedding", size=12))
    parts.append(label(448, 152, "services/", color=MUTED, size=12))
    parts.append(arrow(508, 172, 508, 248, 630, PINK))
    parts.append(
        f'<ellipse cx="508" cy="272" rx="118" ry="20" stroke="{INK}" stroke-width="2" fill="none"/>'
    )
    parts.append(
        f'<path d="M390,272 C388,302 390,310 390,310 L626,312 C628,284 626,272 626,272" '
        f'stroke="{INK}" stroke-width="2" fill="none" stroke-linecap="round"/>'
    )
    parts.append(
        f'<ellipse cx="508" cy="312" rx="118" ry="20" stroke="{INK}" stroke-width="2" '
        f'fill="{CYAN}" fill-opacity="0.15"/>'
    )
    parts.append(f'<path d="M390,272 L390,312 M626,272 L626,312" stroke="{INK}" stroke-width="2"/>')
    parts.append(label(418, 298, "Chroma + SQLite", color=YELLOW, size=15))
    parts.append(label(398, 318, "course_id 隔离", color=MUTED, size=11))
    parts.append(label(48, 340, "UI 不写 RAG；按课程过滤向量与文档", color=MUTED, size=12))
    parts.append(SVG_CLOSE)
    return "".join(parts)


def layers_svg() -> str:
    parts = [svg_open(480, 430)]
    parts.append(box(72, 24, 336, 56, 690, "", stroke=CYAN, accent=False))
    parts.append(label(108, 48, "www/", color=CYAN, size=16))
    parts.append(label(108, 68, "sz · sz-docs · sz-cfg", size=12))
    parts.append(arrow(248, 84, 248, 112, 695, PINK))
    parts.append(box(72, 118, 336, 64, 700, "", stroke=YELLOW, accent=True))
    parts.append(label(108, 144, "apis/v1/", color=YELLOW, size=16))
    parts.append(label(108, 166, "路由 · 校验 · Depends", size=12))
    parts.append(arrow(248, 186, 248, 220, 710, PINK))
    parts.append(box(88, 228, 304, 72, 720, "", stroke=INK))
    parts.append(label(124, 256, "services/", size=16))
    parts.append(label(104, 280, "ingestion · query · retrieval · llm", color=MUTED, size=11))
    parts.append(arrow(248, 304, 248, 338, 730, PINK))
    parts.append(hachure_rect(64, 348, 352, 64, 740, PINK))
    parts.append(label(108, 378, "storage/", color=PINK, size=16))
    parts.append(label(88, 400, "Chroma · SQLite · knowledge · providers", size=11))
    parts.append(SVG_CLOSE)
    return "".join(parts)


def flow_svg() -> str:
    parts = [svg_open(880, 370)]
    parts.append(label(28, 32, "入库流水线", color=YELLOW, size=15))
    parts.append(label(28, 200, "查询流水线", color=PINK, size=15))
    ingest = ["上传/扫描", "解析", "分块", "向量化", "Chroma + SQLite"]
    ixs, iws = [28, 118, 186, 256, 336], [70, 50, 50, 60, 112]
    for i, (x, w, n) in enumerate(zip(ixs, iws, ingest)):
        parts.append(box(x, 52, w, 38, 800 + i, n, accent=(i == 4)))
    for i in range(4):
        parts.append(arrow(ixs[i] + iws[i] + 2, 72, ixs[i + 1] - 2, 72, 810 + i, YELLOW if i == 3 else PINK))
    query = ["提问+course", "检索 top_k", "阈值", "LLM 生成", "答案 + citations"]
    qxs, qws = [28, 118, 206, 286, 386], [70, 70, 60, 80, 120]
    for i, (x, w, n) in enumerate(zip(qxs, qws, query)):
        parts.append(box(x, 216, w, 38, 820 + i, n, accent=(i >= 3)))
    for i in range(4):
        parts.append(arrow(qxs[i] + qws[i] + 2, 236, qxs[i + 1] - 2, 236, 830 + i, YELLOW if i >= 2 else PINK))
    parts.append(hachure_rect(286, 268, 90, 34, 840, PINK))
    parts.append(label(312, 290, "拒答", color=PINK, size=13))
    parts.append(label(196, 268, "score &lt; 阈值", color=PINK, size=10))
    parts.append(label(228, 228, "score ≥ 阈值", color=YELLOW, size=10))
    parts.append(
        rough_line(392, 92, 248, 168, 850)
        .replace("M", '<path d="M', 1)
        + f'" stroke="{MUTED}" stroke-width="1.5" stroke-dasharray="5 4" fill="none" opacity="0.6"/>'
    )
    parts.append(label(300, 148, "向量库", color=MUTED, size=11))
    parts.append(SVG_CLOSE)
    return "".join(parts)


# --- Excalidraw source (editable in excalidraw.com) ---

def _el_id() -> str:
    return uuid.uuid4().hex[:12]


def excal_rect(x: float, y: float, w: float, h: float, *, stroke: str, bg: str = "transparent", seed: int = 1) -> dict:
    return {
        "id": _el_id(),
        "type": "rectangle",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "angle": 0,
        "strokeColor": stroke,
        "backgroundColor": bg,
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "seed": seed,
        "version": 141,
        "versionNonce": seed,
        "isDeleted": False,
        "groupIds": [],
        "boundElements": None,
        "link": None,
        "locked": False,
        "roundness": {"type": 3},
    }


def excal_text(x: float, y: float, text: str, *, color: str, size: int = 20) -> dict:
    return {
        "id": _el_id(),
        "type": "text",
        "x": x,
        "y": y,
        "width": len(text) * size * 0.55,
        "height": size * 1.25,
        "angle": 0,
        "strokeColor": color,
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
        "seed": 1,
        "version": 141,
        "versionNonce": 1,
        "isDeleted": False,
        "groupIds": [],
        "boundElements": None,
        "link": None,
        "locked": False,
        "text": text,
        "fontSize": size,
        "fontFamily": 5,
        "textAlign": "left",
        "verticalAlign": "top",
        "containerId": None,
        "originalText": text,
        "lineHeight": 1.25,
    }


def excal_arrow(x1: float, y1: float, x2: float, y2: float, *, color: str, seed: int) -> dict:
    return {
        "id": _el_id(),
        "type": "arrow",
        "x": x1,
        "y": y1,
        "width": x2 - x1,
        "height": y2 - y1,
        "angle": 0,
        "strokeColor": color,
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "seed": seed,
        "version": 141,
        "versionNonce": seed,
        "isDeleted": False,
        "groupIds": [],
        "boundElements": None,
        "link": None,
        "locked": False,
        "points": [[0, 0], [x2 - x1, y2 - y1]],
        "lastCommittedPoint": None,
        "startBinding": None,
        "endBinding": None,
        "startArrowhead": None,
        "endArrowhead": "arrow",
    }


def agent_excalidraw() -> dict:
    els = [
        excal_rect(48, 42, 180, 120, stroke=INK, seed=10),
        excal_text(88, 72, "浏览器 UI", color=YELLOW, size=20),
        excal_text(62, 102, "sz · sz-docs · sz-cfg", color=INK, size=14),
        excal_rect(358, 42, 304, 126, stroke=INK, seed=20),
        excal_text(388, 72, "本地 FastAPI", color=YELLOW, size=20),
        excal_text(368, 102, "入库 · 检索 · 生成 · 拒答", color=INK, size=16),
        excal_arrow(232, 102, 352, 102, color=YELLOW, seed=30),
        excal_text(262, 78, "HTTP /api/v1/*", color=YELLOW, size=14),
        excal_arrow(508, 172, 508, 248, color=PINK, seed=40),
        excal_rect(390, 258, 236, 54, stroke=INK, bg=f"{CYAN}33", seed=50),
        excal_text(418, 278, "Chroma + SQLite", color=YELLOW, size=18),
    ]
    return {
        "type": "excalidraw",
        "version": 2,
        "source": "exam-rag gen_arch_svgs.py",
        "elements": els,
        "appState": {
            "viewBackgroundColor": BG,
            "gridSize": None,
        },
        "files": {},
    }


SVGS = {
    "architecture-pipelines.svg": pipelines_svg,
    "architecture-agent.svg": agent_svg,
    "architecture-layers.svg": layers_svg,
    "architecture-flow.svg": flow_svg,
}


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    EXCAL.mkdir(parents=True, exist_ok=True)
    for name, fn in SVGS.items():
        (ROOT / name).write_text(fn(), encoding="utf-8")
        print(f"wrote {name}")
    excal_path = EXCAL / "architecture-agent.excalidraw"
    excal_path.write_text(json.dumps(agent_excalidraw(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote excalidraw/{excal_path.name}")


if __name__ == "__main__":
    main()
