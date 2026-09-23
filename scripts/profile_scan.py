"""
profile_scan.py — gera um SVG animado estilo "profile scan" para o README do GitHub.

- Lado esquerdo: seu avatar convertido em matriz ASCII (ou pixels), revelado por uma linha de scan.
- Lado direito: um painel SYSTEM.INFO que "digita" as informações linha por linha.
- Tudo é um único SVG com animação SMIL, que o GitHub renderiza dentro de <img>.

Uso:
    python scripts/profile_scan.py --out dist/profile-scan.svg
    python scripts/profile_scan.py --out preview.svg --avatar minha_foto.png   # teste local
"""

import argparse
import io
import json
import os
import urllib.request
from xml.sax.saxutils import escape

from PIL import Image, ImageOps, ImageEnhance

# ======================= CONFIGURAÇÃO — edite aqui =======================
USERNAME = "EduMoridev"

MODE = "ascii"          # "ascii" = matriz de caracteres | "pixel" = quadradinhos pixelados
GRID = 56               # resolução da matriz (56x56). Mais alto = mais detalhe, SVG maior.
INVERT = False          # True se o seu avatar tiver fundo claro e o rosto sumir

# Linhas do painel. "{repos}" é preenchido com dado real da API do GitHub.
# Deixei de fora stars/followers/contribuições de propósito: números baixos
# em destaque trabalham contra você. Coloque de volta quando eles forem bons.
INFO = [
    ("Subject",   "Eduardo Morishita"),
    ("Handle",    "@EduMoridev"),
    ("Role",      "Front-end Dev | Co-founder"),
    ("Company",   "Kronos"),
    ("Stack",     "Next.js · TypeScript · Spring"),
    ("Education", "Eng. de Software"),
    ("Repos",     "{repos} public"),
    ("Status",    "Open to work · Junior"),
    ("Contact",   "edu.mori@hotmail.com"),
]

# Paleta
BG        = "#07110f"
PANEL     = "#0a1a17"
ACCENT    = "#2dd4bf"
ACCENT_DIM = "#14b8a6"
TEXT      = "#ccfbf1"
MUTED     = "#5eead4"
# =========================================================================

W, H = 880, 470
LEFT_X, LEFT_Y, LEFT_W, LEFT_H = 28, 64, 372, 382
RIGHT_X, RIGHT_Y, RIGHT_W, RIGHT_H = 416, 64, 436, 382
SCAN_DUR = 2.6          # segundos da linha de scan no avatar
INFO_START = SCAN_DUR + 0.2
INFO_STEP = 0.32        # intervalo entre uma linha e outra do painel
FONT = "ui-monospace, 'SFMono-Regular', 'DejaVu Sans Mono', Menlo, Consolas, monospace"


def http_get(url, token=None):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-scan"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def load_avatar(path):
    if path:
        return Image.open(path)
    data = http_get(f"https://github.com/{USERNAME}.png?size=256")
    return Image.open(io.BytesIO(data))


def fetch_repos():
    token = os.environ.get("GITHUB_TOKEN")
    try:
        data = json.loads(http_get(f"https://api.github.com/users/{USERNAME}", token))
        return str(data.get("public_repos", "—"))
    except Exception:
        return "—"


def avatar_matrix(img):
    img = img.convert("L")
    img = ImageOps.fit(img, (GRID, GRID))
    img = ImageOps.autocontrast(img, cutoff=2)
    img = ImageEnhance.Contrast(img).enhance(1.3)
    if INVERT:
        img = ImageOps.invert(img)
    px = img.load()
    c = (GRID - 1) / 2
    r2 = (GRID / 2) ** 2
    rows = []
    for y in range(GRID):
        row = []
        for x in range(GRID):
            inside = (x - c) ** 2 + (y - c) ** 2 <= r2
            row.append(px[x, y] / 255 if inside else None)
        rows.append(row)
    return rows


def render_ascii(matrix, x0, y0, size):
    ramp = " .:-=+*#%@"
    cell = size / GRID
    out = []
    for yi, row in enumerate(matrix):
        y = y0 + (yi + 0.85) * cell
        tspans, cur_lvl, buf = [], None, ""
        for v in row:
            if v is None:
                ch, lvl = " ", 0
            else:
                ch = ramp[min(len(ramp) - 1, int(v * len(ramp)))]
                lvl = min(3, int(v * 4))
            if lvl != cur_lvl and buf:
                tspans.append((cur_lvl, buf))
                buf = ""
            cur_lvl = lvl
            buf += ch
        if buf:
            tspans.append((cur_lvl, buf))
        inner = "".join(
            f'<tspan fill-opacity="{0.35 + 0.22 * l:.2f}">{escape(t)}</tspan>' for l, t in tspans
        )
        out.append(
            f'<text x="{x0}" y="{y:.1f}" textLength="{size}" lengthAdjust="spacingAndGlyphs" '
            f'xml:space="preserve" font-size="{cell * 1.15:.1f}">{inner}</text>'
        )
    return f'<g fill="{ACCENT}" font-family="{FONT}">' + "".join(out) + "</g>"


def render_pixel(matrix, x0, y0, size):
    cell = size / GRID
    out = []
    for yi, row in enumerate(matrix):
        for xi, v in enumerate(row):
            if v is None or v < 0.08:
                continue
            out.append(
                f'<rect x="{x0 + xi * cell:.1f}" y="{y0 + yi * cell:.1f}" '
                f'width="{cell * 0.86:.1f}" height="{cell * 0.86:.1f}" fill-opacity="{0.15 + 0.85 * v:.2f}"/>'
            )
    return f'<g fill="{ACCENT}">' + "".join(out) + "</g>"


def build_svg(avatar, repos):
    matrix = avatar_matrix(avatar)
    art_size = 330
    ax = LEFT_X + (LEFT_W - art_size) / 2
    ay = LEFT_Y + 38
    art = render_ascii(matrix, ax, ay, art_size) if MODE == "ascii" else render_pixel(matrix, ax, ay, art_size)

    # ---------- painel de info ----------
    rows_svg, clips = [], []
    label_x = RIGHT_X + 22
    value_x = RIGHT_X + 150
    row_y0 = RIGHT_Y + 64
    row_h = 34
    for i, (label, value) in enumerate(INFO):
        value = value.replace("{repos}", repos)
        y = row_y0 + i * row_h
        t = INFO_START + i * INFO_STEP
        vw = len(value) * 7.4 + 12
        clips.append(
            f'<clipPath id="v{i}"><rect x="{value_x}" y="{y - 14}" height="20" width="0">'
            f'<animate attributeName="width" from="0" to="{vw:.0f}" begin="{t + 0.12:.2f}s" dur="0.45s" fill="freeze"/>'
            f'</rect></clipPath>'
        )
        rows_svg.append(
            f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{t:.2f}s" dur="0.2s" fill="freeze"/>'
            f'<text x="{label_x}" y="{y}" fill="{MUTED}" font-size="12.5">{escape(label)}</text>'
            f'<text x="{value_x}" y="{y}" fill="{TEXT}" font-size="12.5" clip-path="url(#v{i})">{escape(value)}</text>'
            f'<line x1="{label_x}" y1="{y + 11}" x2="{RIGHT_X + RIGHT_W - 22}" y2="{y + 11}" stroke="{ACCENT}" stroke-opacity="0.08"/>'
            f"</g>"
        )
    end_t = INFO_START + len(INFO) * INFO_STEP + 0.4
    cursor_y = row_y0 + len(INFO) * row_h - 4
    cursor = (
        f'<rect x="{label_x}" y="{cursor_y - 12}" width="8" height="15" fill="{ACCENT}" opacity="0">'
        f'<animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.01;0.5;0.51;1" '
        f'dur="1s" begin="{end_t:.2f}s" repeatCount="indefinite"/></rect>'
    )

    title = f"{USERNAME.lower()}@github ~ $ ./profile-scan --live"

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Profile scan de {escape(INFO[0][1])}">
<defs>
  <filter id="glow" x="-10%" y="-10%" width="120%" height="120%">
    <feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">
    <rect width="4" height="1" fill="#ffffff" fill-opacity="0.025"/>
  </pattern>
  <linearGradient id="beam" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{ACCENT}" stop-opacity="0"/>
    <stop offset="0.85" stop-color="{ACCENT}" stop-opacity="0.35"/>
    <stop offset="1" stop-color="#ffffff" stop-opacity="0.9"/>
  </linearGradient>
  <clipPath id="reveal">
    <rect x="{LEFT_X}" y="{ay}" width="{LEFT_W}" height="0">
      <animate attributeName="height" from="0" to="{art_size + 4}" dur="{SCAN_DUR}s" fill="freeze"/>
    </rect>
  </clipPath>
  {''.join(clips)}
</defs>

<rect x="0" y="0" width="{W}" height="{H}" rx="16" fill="{BG}"/>
<rect x="6" y="6" width="{W - 12}" height="{H - 12}" rx="13" fill="none" stroke="{ACCENT}" stroke-opacity="0.55" stroke-width="1.5" filter="url(#glow)"/>

<!-- barra de título -->
<circle cx="28" cy="30" r="5.5" fill="#ff5f57"/><circle cx="46" cy="30" r="5.5" fill="#febc2e"/><circle cx="64" cy="30" r="5.5" fill="#28c840"/>
<text x="{W / 2}" y="34" text-anchor="middle" fill="{MUTED}" font-family="{FONT}" font-size="12" fill-opacity="0.8">{escape(title)}</text>
<g font-family="{FONT}" font-size="11" fill="{ACCENT}">
  <circle cx="{W - 70}" cy="30" r="4" fill="#ef4444"><animate attributeName="opacity" values="1;0.2;1" dur="1.4s" repeatCount="indefinite"/></circle>
  <text x="{W - 60}" y="34">LIVE</text>
</g>

<!-- painel esquerdo -->
<rect x="{LEFT_X}" y="{LEFT_Y}" width="{LEFT_W}" height="{LEFT_H}" rx="10" fill="{PANEL}" stroke="{ACCENT}" stroke-opacity="0.35"/>
<text x="{LEFT_X + 16}" y="{LEFT_Y + 22}" fill="{MUTED}" font-family="{FONT}" font-size="11" letter-spacing="2">VISUAL.MAP</text>
<g clip-path="url(#reveal)">{art}</g>
<rect x="{LEFT_X + 4}" y="{ay - 26}" width="{LEFT_W - 8}" height="28" fill="url(#beam)" opacity="0">
  <animate attributeName="y" values="{ay - 26};{ay + art_size - 26}" dur="{SCAN_DUR}s" fill="freeze"/>
  <animate attributeName="opacity" values="1;1;0" keyTimes="0;0.9;1" dur="{SCAN_DUR}s" fill="freeze"/>
</rect>
<rect x="{LEFT_X + 4}" y="{ay}" width="{LEFT_W - 8}" height="2" fill="{ACCENT}" opacity="0">
  <animate attributeName="y" values="{ay};{ay + art_size}" dur="4s" begin="{SCAN_DUR + 1}s" repeatCount="indefinite"/>
  <animate attributeName="opacity" values="0;0.5;0.5;0" keyTimes="0;0.05;0.9;1" dur="4s" begin="{SCAN_DUR + 1}s" repeatCount="indefinite"/>
</rect>

<!-- painel direito -->
<rect x="{RIGHT_X}" y="{RIGHT_Y}" width="{RIGHT_W}" height="{RIGHT_H}" rx="10" fill="{PANEL}" stroke="{ACCENT}" stroke-opacity="0.35"/>
<text x="{RIGHT_X + 16}" y="{RIGHT_Y + 22}" fill="{MUTED}" font-family="{FONT}" font-size="11" letter-spacing="2">SYSTEM.INFO</text>
<text x="{RIGHT_X + RIGHT_W - 16}" y="{RIGHT_Y + 22}" text-anchor="end" fill="{ACCENT}" font-family="{FONT}" font-size="11">● LIVE</text>
<g font-family="{FONT}">{''.join(rows_svg)}{cursor}</g>

<rect x="0" y="0" width="{W}" height="{H}" rx="16" fill="url(#scan)" pointer-events="none"/>
</svg>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist/profile-scan.svg")
    ap.add_argument("--avatar", help="caminho de uma imagem local (para testar sem internet)")
    args = ap.parse_args()

    svg = build_svg(load_avatar(args.avatar), fetch_repos())
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"ok -> {args.out} ({len(svg) // 1024} KB)")


if __name__ == "__main__":
    main()
