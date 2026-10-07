"""
profile_scan.py: gera todos os painéis SVG do README no mesmo estilo (terminal verde neon).

Arquivos gerados em --outdir (padrão: dist/):
  header.svg          nome grande em matriz de caracteres
  card.svg            cartão com avatar, nome, cargo e tecnologias
  profile-scan.svg    avatar em ASCII + painel SYSTEM.INFO
  stack.svg           tecnologias separadas em front, back e ferramentas
  activity.svg        gráfico de contribuições do último ano
  title-*.svg         títulos das seções

Uso:
  python scripts/profile_scan.py --outdir dist
  python scripts/profile_scan.py --outdir preview --avatar foto.png   # teste local
"""

import argparse
import base64
import io
import json
import os
import re
import urllib.request
from datetime import date
from xml.sax.saxutils import escape

from PIL import Image, ImageEnhance, ImageOps

# ============================== CONFIGURAÇÃO ==============================
USERNAME = "EduMoridev"
HEADER_NAME = "EDUARDO"            # texto grande do topo (A-Z, 0-9, espaço, - . / :)

NAME = "Eduardo Morishita"
ROLE = "Desenvolvedor Front-end | Co-founder da Kronos"
CARD_PILLS = ["Next.js", "TypeScript", "React", "Spring Boot"]

STACK = [
    ("FRONT-END", ["Next.js", "TypeScript", "React", "Tailwind CSS", "JavaScript", "HTML", "CSS"]),
    ("BACK-END", ["Java", "Spring Boot", "Node.js"]),
    ("FERRAMENTAS", ["Git", "GitHub", "Docker", "Maven", "Vercel", "Figma", "Cursor",
                     "Antigravity", "Apidog", "Miro", "Trello", "Metodologia ágil"]),
]

# Painel SYSTEM.INFO do scan. "{repos}" vem da API do GitHub.
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

SECTION_TITLES = ["SOBRE", "PROJETOS", "STACK", "ATIVIDADE", "CONTATO"]

# Blocos de texto que aparecem sendo digitados, letra por letra.
# Cada item: nome do arquivo -> (comando do terminal, linhas).
# Linha vazia ("") vira um espaço em branco. Cuidado com o tamanho: cada linha
# cabe cerca de 88 caracteres. Se passar disso, o texto sai cortado.
TYPED = {
    "about.svg": (
        "cat sobre.txt",
        [
            "Sou co-founder e desenvolvedor front-end da Kronos, uma startup que está criando",
            "um software para unificar plataformas de agendamento.",
            "",
            "Trabalho principalmente com Next.js e TypeScript e, quando o projeto precisa,",
            "também desenvolvo no back-end com Java e Spring Boot.",
            "",
            "Fora da Kronos, faço landing pages e sites institucionais como freelancer,",
            "cuidando do layout até o deploy na Vercel. Estou cursando Engenharia de Software.",
        ],
    ),
    "contact.svg": (
        "./contato --disponibilidade",
        [
            "Estou disponível para vagas de desenvolvedor front-end júnior, CLT ou PJ.",
            "Me chame no LinkedIn ou por e-mail: edu.mori@hotmail.com",
        ],
    ),
}
TYPE_SPEED = 0.013   # segundos por caractere. Menor = digita mais rápido.

SHOW_CONTRIBUTION_COUNT = False   # mostra "N contribuições" no painel de atividade

# Scan do avatar
MODE = "ascii"            # "ascii" ou "pixel"
GRID = 56
INVERT = False
LOCAL_AVATAR = "assets/scan-avatar.png"   # se existir no repo, tem prioridade

# Paleta
BG = "#07110f"
PANEL = "#0a1a17"
ACCENT = "#2dd4bf"
DEEP = "#0f5f55"
TEXT = "#ccfbf1"
MUTED = "#5eead4"
# ==========================================================================

W = 880
MONO = "ui-monospace, 'SFMono-Regular', 'DejaVu Sans Mono', Menlo, Consolas, monospace"
SANS = "'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif"

FONT_5x7 = {
    "A": [" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "B": ["#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "],
    "C": [" ### ", "#   #", "#    ", "#    ", "#    ", "#   #", " ### "],
    "D": ["#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "],
    "E": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"],
    "F": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "],
    "G": [" ### ", "#   #", "#    ", "# ###", "#   #", "#   #", " ####"],
    "H": ["#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "I": [" ### ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    "J": ["  ###", "   # ", "   # ", "   # ", "   # ", "#  # ", " ##  "],
    "K": ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"],
    "M": ["#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"],
    "N": ["#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "P": ["#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "],
    "Q": [" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"],
    "R": ["#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"],
    "S": [" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    "U": ["#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "V": ["#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "],
    "W": ["#   #", "#   #", "#   #", "# # #", "# # #", "# # #", " # # "],
    "X": ["#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"],
    "Y": ["#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "],
    "Z": ["#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"],
    "0": [" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "],
    "1": ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    "2": [" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"],
    "3": ["#####", "   # ", "  #  ", "   # ", "    #", "#   #", " ### "],
    "4": ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "],
    "5": ["#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "],
    "6": ["  ## ", " #   ", "#    ", "#### ", "#   #", "#   #", " ### "],
    "7": ["#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "],
    "8": [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
    "9": [" ### ", "#   #", "#   #", " ####", "    #", "   # ", " ##  "],
    " ": ["     "] * 7,
    "-": ["     ", "     ", "     ", "#####", "     ", "     ", "     "],
    ".": ["     ", "     ", "     ", "     ", "     ", "     ", "  #  "],
    "/": ["    #", "    #", "   # ", "  #  ", " #   ", "#    ", "#    "],
    ":": ["     ", "  #  ", "     ", "     ", "     ", "  #  ", "     "],
}


# ------------------------------ utilidades ------------------------------
def http_get(url, token=None):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-scan"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def load_avatar(path):
    if path:
        return Image.open(path)
    if os.path.exists(LOCAL_AVATAR):
        print(f"usando {LOCAL_AVATAR}")
        return Image.open(LOCAL_AVATAR)
    try:
        return Image.open(io.BytesIO(http_get(f"https://github.com/{USERNAME}.png?size=256")))
    except Exception as e:
        print(f"::warning::avatar não baixou ({e}); usando imagem de fallback")
        return Image.radial_gradient("L").resize((256, 256))


def fetch_repos():
    try:
        data = json.loads(http_get(f"https://api.github.com/users/{USERNAME}", os.environ.get("GITHUB_TOKEN")))
        return str(data.get("public_repos", "—"))
    except Exception:
        return "—"


def fetch_contributions():
    """Retorna (grid[semana][dia] = nível 0-4, total ou None)."""
    try:
        html = http_get(f"https://github.com/users/{USERNAME}/contributions").decode("utf-8", "ignore")
    except Exception as e:
        print(f"::warning::contribuições não baixaram ({e})")
        return [[0] * 7 for _ in range(53)], None
    cells = {}
    for m in re.finditer(r'<td[^>]*id="contribution-day-component-(\d)-(\d+)"[^>]*data-level="(\d)"', html):
        d, w, lvl = int(m.group(1)), int(m.group(2)), int(m.group(3))
        cells[(w, d)] = lvl
    weeks = max((w for w, _ in cells), default=52) + 1
    grid = [[cells.get((w, d), -1) for d in range(7)] for w in range(weeks)]
    m = re.search(r"([\d,.]+)\s+contributions?\s+in the last year", html)
    total = m.group(1) if m else None
    return grid, total


def frame(h, title=None, live=False):
    """Janela de terminal padrão: fundo, borda com brilho, bolinhas e título."""
    t = ""
    if title:
        t = (f'<circle cx="28" cy="30" r="5.5" fill="#ff5f57"/><circle cx="46" cy="30" r="5.5" fill="#febc2e"/>'
             f'<circle cx="64" cy="30" r="5.5" fill="#28c840"/>'
             f'<text x="{W / 2}" y="34" text-anchor="middle" fill="{MUTED}" font-family="{MONO}" font-size="12" '
             f'fill-opacity="0.8">{escape(title)}</text>')
    if live:
        t += (f'<g font-family="{MONO}" font-size="11" fill="{ACCENT}">'
              f'<circle cx="{W - 70}" cy="30" r="4" fill="#ef4444"><animate attributeName="opacity" values="1;0.2;1" dur="1.4s" repeatCount="indefinite"/></circle>'
              f'<text x="{W - 60}" y="34">LIVE</text></g>')
    return f"""<defs>
  <filter id="glow" x="-10%" y="-10%" width="120%" height="120%">
    <feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="softglow" x="-20%" y="-50%" width="140%" height="200%">
    <feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <pattern id="crt" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#fff" fill-opacity="0.025"/></pattern>
</defs>
<rect width="{W}" height="{h}" rx="16" fill="{BG}"/>
<rect x="6" y="6" width="{W - 12}" height="{h - 12}" rx="13" fill="none" stroke="{ACCENT}" stroke-opacity="0.55" stroke-width="1.5" filter="url(#glow)"/>
{t}"""


def svg(h, body, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" '
            f'role="img" aria-label="{escape(label)}">{body}</svg>')


def text_width(s, size, mono=False):
    return len(s) * size * (0.6 if mono else 0.56)


def dotmatrix(text, x, y, cw, ch, sub, gid):
    """Texto grande desenhado com caracteres '#', no estilo matriz de pontos, com sombra."""
    rows = [""] * (7 * sub)
    for i, c in enumerate(text.upper()):
        glyph = FONT_5x7.get(c, FONT_5x7[" "])
        for r in range(7):
            line = "".join(("#" if p == "#" else " ") * sub for p in glyph[r])
            if i < len(text) - 1:
                line += " " * sub
            for s in range(sub):
                rows[r * sub + s] += line
    width = len(rows[0]) * cw
    fs = ch * 1.05

    def layer(dx, dy, fill, extra=""):
        out = []
        for i, row in enumerate(rows):
            out.append(f'<text x="{x + dx:.1f}" y="{y + dy + (i + 0.85) * ch:.1f}" textLength="{width:.1f}" '
                       f'lengthAdjust="spacingAndGlyphs" xml:space="preserve">{escape(row)}</text>')
        return f'<g fill="{fill}" font-family="{MONO}" font-size="{fs:.1f}" font-weight="700" {extra}>{"".join(out)}</g>'

    grad = (f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="0" y1="{y}" x2="0" y2="{y + 7 * sub * ch}">'
            f'<stop offset="0" stop-color="#f0fdfa"/><stop offset="0.55" stop-color="{TEXT}"/>'
            f'<stop offset="1" stop-color="{ACCENT}"/></linearGradient>')
    return grad + layer(3, 3, DEEP, 'fill-opacity="0.9"') + layer(0, 0, f"url(#{gid})", 'filter="url(#softglow)"'), width, 7 * sub * ch


# ------------------------------ painéis ------------------------------
def build_header():
    h = 210
    cw, ch, sub = 8.4, 8.6, 2
    cols = (len(HEADER_NAME) * 6 - 1) * sub
    tw = cols * cw
    x = (W - tw) / 2
    art, width, height = dotmatrix(HEADER_NAME, x, 70, cw, ch, sub, "hg")
    body = frame(h, f"{USERNAME.lower()}@github ~ $ ./hello --name")
    body += (f'<clipPath id="rv"><rect x="{x - 4}" y="60" width="0" height="{height + 20}">'
             f'<animate attributeName="width" from="0" to="{width + 12}" dur="1.6s" fill="freeze"/></rect></clipPath>'
             f'<g clip-path="url(#rv)">{art}</g>'
             f'<rect x="{x + width + 14}" y="{70 + height - 22}" width="12" height="22" fill="{ACCENT}" opacity="0">'
             f'<animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.01;0.5;0.51;1" dur="1s" begin="1.6s" repeatCount="indefinite"/></rect>'
             f'<rect width="{W}" height="{h}" rx="16" fill="url(#crt)"/>')
    return svg(h, body, HEADER_NAME)


def build_card(avatar):
    h = 250
    av = ImageOps.fit(avatar.convert("RGB"), (160, 160))
    buf = io.BytesIO()
    av.save(buf, "JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()
    cx, cy, r = 110, 118, 64

    pills, px = [], 210
    for i, p in enumerate(CARD_PILLS):
        pw = text_width(p, 13) + 30
        pills.append(
            f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{0.9 + i * 0.12:.2f}s" dur="0.3s" fill="freeze"/>'
            f'<rect x="{px}" y="176" width="{pw:.0f}" height="30" rx="15" fill="{PANEL}" stroke="{ACCENT}" stroke-opacity="0.7"/>'
            f'<text x="{px + pw / 2:.0f}" y="196" text-anchor="middle" fill="{TEXT}" font-family="{SANS}" font-size="13" font-weight="600">{escape(p)}</text></g>')
        px += pw + 10

    body = frame(h)
    body += f"""
<defs><clipPath id="av"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath></defs>
<circle cx="{cx}" cy="{cy}" r="{r + 5}" fill="none" stroke="{ACCENT}" stroke-width="2" filter="url(#glow)"/>
<image href="data:image/jpeg;base64,{b64}" x="{cx - r}" y="{cy - r}" width="{2 * r}" height="{2 * r}" clip-path="url(#av)" preserveAspectRatio="xMidYMid slice"/>
<g opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.6s" fill="freeze"/>
<animateTransform attributeName="transform" type="translate" from="-12 0" to="0 0" dur="0.6s" fill="freeze"/>
  <text x="210" y="62" fill="{ACCENT}" font-family="{MONO}" font-size="14">@{escape(USERNAME)}</text>
  <text x="208" y="112" fill="#f0fdfa" font-family="{SANS}" font-size="44" font-weight="800" filter="url(#softglow)">{escape(NAME)}</text>
  <text x="210" y="148" fill="{MUTED}" font-family="{SANS}" font-size="16">{escape(ROLE)}</text>
</g>
{''.join(pills)}
<g text-anchor="end" opacity="0"><animate attributeName="opacity" from="0" to="1" begin="0.4s" dur="0.6s" fill="freeze"/>
  <text x="{W - 36}" y="92" fill="{ACCENT}" font-family="{SANS}" font-size="40" font-weight="800" filter="url(#softglow)">OPEN</text>
  <text x="{W - 36}" y="116" fill="{MUTED}" font-family="{MONO}" font-size="12" letter-spacing="3">TO WORK</text>
</g>
<circle cx="{W - 118}" cy="112" r="4.5" fill="#22c55e"><animate attributeName="opacity" values="1;0.25;1" dur="1.6s" repeatCount="indefinite"/></circle>
<rect width="{W}" height="{h}" rx="16" fill="url(#crt)"/>"""
    return svg(h, body, f"{NAME}, {ROLE}")


def build_title(text):
    h = 92
    cw, ch, sub = 6.2, 7.0, 1
    art, width, height = dotmatrix(text, 34, 16, cw, ch, sub, f"tg{text}")
    body = (f'<defs><filter id="softglow" x="-20%" y="-50%" width="140%" height="200%">'
            f'<feGaussianBlur stdDeviation="1.6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
            f'<linearGradient id="ln" x1="0" x2="1"><stop offset="0" stop-color="{ACCENT}" stop-opacity="0.9"/>'
            f'<stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></linearGradient></defs>'
            f'<text x="6" y="{16 + height * 0.75:.0f}" fill="{ACCENT}" font-family="{MONO}" font-size="22" font-weight="700">&gt;</text>'
            f'<clipPath id="rv"><rect x="30" y="0" width="0" height="{h}"><animate attributeName="width" from="0" to="{width + 20}" dur="0.9s" fill="freeze"/></rect></clipPath>'
            f'<g clip-path="url(#rv)">{art}</g>'
            f'<rect x="6" y="{h - 14}" width="{W - 12}" height="1.5" fill="url(#ln)"/>')
    return svg(h, body, text.title())


def build_typed(command, lines):
    """Bloco de texto que aparece sendo digitado, no mesmo estilo do painel SYSTEM.INFO."""
    fs, lh = 14.0, 26
    y0 = 74
    h = y0 + len(lines) * lh + 34
    out, clips, t = [], [], 0.5
    for i, line in enumerate(lines):
        y = y0 + i * lh
        if not line.strip():
            t += 0.18
            continue
        w = len(line) * fs * 0.6 + 8
        dur = max(0.25, len(line) * TYPE_SPEED)
        clips.append(f'<clipPath id="tl{i}"><rect x="34" y="{y - 14}" height="{lh}" width="0">'
                     f'<animate attributeName="width" from="0" to="{w:.0f}" begin="{t:.2f}s" dur="{dur:.2f}s" fill="freeze"/>'
                     f'</rect></clipPath>')
        out.append(f'<text x="34" y="{y}" fill="{TEXT}" font-family="{MONO}" font-size="{fs}" '
                   f'xml:space="preserve" clip-path="url(#tl{i})">{escape(line)}</text>')
        # cursor que acompanha a digitação desta linha
        out.append(f'<rect y="{y - 12}" width="8" height="16" fill="{ACCENT}" opacity="0">'
                   f'<animate attributeName="x" from="34" to="{34 + w:.0f}" begin="{t:.2f}s" dur="{dur:.2f}s" fill="freeze"/>'
                   f'<animate attributeName="opacity" values="1;1;0" keyTimes="0;0.97;1" begin="{t:.2f}s" dur="{dur:.2f}s" fill="freeze"/></rect>')
        t += dur + 0.12
    # cursor piscando no fim
    out.append(f'<rect x="34" y="{y0 + len(lines) * lh - 12}" width="8" height="16" fill="{ACCENT}" opacity="0">'
               f'<animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.01;0.5;0.51;1" dur="1s" '
               f'begin="{t:.2f}s" repeatCount="indefinite"/></rect>')
    body = frame(h, f"{USERNAME.lower()}@github ~ $ {command}") + "".join(clips) + "".join(out)
    body += f'<rect width="{W}" height="{h}" rx="16" fill="url(#crt)"/>'
    return svg(h, body, " ".join(l for l in lines if l.strip()))


def build_stack():
    rows_svg, y = [], 76
    t = 0.2
    for label, items in STACK:
        rows_svg.append(f'<text x="36" y="{y + 20}" fill="{MUTED}" font-family="{MONO}" font-size="12" letter-spacing="2">{escape(label)}</text>')
        x = 190
        for it in items:
            pw = text_width(it, 13) + 30
            if x + pw > W - 32:
                x, y = 190, y + 42
            rows_svg.append(
                f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{t:.2f}s" dur="0.3s" fill="freeze"/>'
                f'<rect x="{x}" y="{y}" width="{pw:.0f}" height="30" rx="15" fill="{PANEL}" stroke="{ACCENT}" stroke-opacity="0.7"/>'
                f'<text x="{x + pw / 2:.0f}" y="{y + 20}" text-anchor="middle" fill="{TEXT}" font-family="{SANS}" font-size="13" font-weight="600">{escape(it)}</text></g>')
            x += pw + 10
            t += 0.06
        y += 56
    h = y + 8
    return svg(h, frame(h, f"{USERNAME.lower()}@github ~ $ cat stack.json") + "".join(rows_svg)
               + f'<rect width="{W}" height="{h}" rx="16" fill="url(#crt)"/>', "Stack")


def build_activity(grid, total):
    weeks = len(grid)
    cell, gap = 12, 3
    gw = weeks * (cell + gap) - gap
    x0 = (W - gw) / 2
    y0 = 92
    h = y0 + 7 * (cell + gap) + 30
    colors = ["#12302b", "#115e52", "#14b8a6", "#2dd4bf", "#99f6e4"]
    cells = []
    for w, col in enumerate(grid):
        for d, lvl in enumerate(col):
            if lvl < 0:
                continue
            x, y = x0 + w * (cell + gap), y0 + d * (cell + gap)
            begin = 0.3 + w * 0.025
            anim = f'<animate attributeName="opacity" from="0" to="1" begin="{begin:.2f}s" dur="0.25s" fill="freeze"/>'
            if lvl >= 3:  # dias mais ativos pulsam
                anim += (f'<animate attributeName="fill" values="{colors[lvl]};#f0fdfa;{colors[lvl]}" '
                         f'dur="2.4s" begin="{begin + 1.5:.2f}s" repeatCount="indefinite"/>')
            filt = ' filter="url(#softglow)"' if lvl >= 2 else ""
            cells.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{cell}" height="{cell}" rx="2.5" fill="{colors[lvl]}" opacity="0"{filt}>{anim}</rect>')
    legend = "".join(f'<rect x="{W - 128 + i * 15}" y="59" width="11" height="11" rx="2" fill="{c}"/>' for i, c in enumerate(colors))
    sub = f"{total} contribuições no último ano" if (SHOW_CONTRIBUTION_COUNT and total) else "último ano no GitHub"
    body = frame(h) + f"""
<text x="36" y="52" fill="#f0fdfa" font-family="{SANS}" font-size="22" font-weight="800" filter="url(#softglow)">Contribution Activity</text>
<text x="36" y="72" fill="{ACCENT}" font-family="{SANS}" font-size="13" font-weight="600">{escape(sub)}</text>
<text x="{W - 134}" y="68" text-anchor="end" fill="{MUTED}" font-family="{MONO}" font-size="10">menos</text>{legend}
<text x="{W - 46}" y="68" fill="{MUTED}" font-family="{MONO}" font-size="10">mais</text>
{''.join(cells)}
<rect width="{W}" height="{h}" rx="16" fill="url(#crt)"/>"""
    return svg(h, body, "Atividade de contribuições")


def build_scan(avatar, repos):
    H = 470
    LX, LY, LW, LH = 28, 64, 372, 382
    RX, RY, RW, RH = 416, 64, 436, 382
    SCAN, START, STEP = 2.6, 2.8, 0.32

    img = ImageOps.fit(avatar.convert("L"), (GRID, GRID))
    img = ImageEnhance.Contrast(ImageOps.autocontrast(img, cutoff=2)).enhance(1.3)
    if INVERT:
        img = ImageOps.invert(img)
    px = img.load()
    c, r2 = (GRID - 1) / 2, (GRID / 2) ** 2
    matrix = [[px[x, y] / 255 if (x - c) ** 2 + (y - c) ** 2 <= r2 else None for x in range(GRID)] for y in range(GRID)]

    size = 330
    ax, ay = LX + (LW - size) / 2, LY + 38
    cell = size / GRID
    if MODE == "ascii":
        ramp, out = " .:-=+*#%@", []
        for yi, row in enumerate(matrix):
            spans, cur, buf = [], None, ""
            for v in row:
                ch_, lvl = (" ", 0) if v is None else (ramp[min(9, int(v * 10))], min(3, int(v * 4)))
                if lvl != cur and buf:
                    spans.append((cur, buf)); buf = ""
                cur, buf = lvl, buf + ch_
            spans.append((cur, buf))
            inner = "".join(f'<tspan fill-opacity="{0.35 + 0.22 * l:.2f}">{escape(t)}</tspan>' for l, t in spans)
            out.append(f'<text x="{ax}" y="{ay + (yi + 0.85) * cell:.1f}" textLength="{size}" lengthAdjust="spacingAndGlyphs" '
                       f'xml:space="preserve" font-size="{cell * 1.15:.1f}">{inner}</text>')
        art = f'<g fill="{ACCENT}" font-family="{MONO}">{"".join(out)}</g>'
    else:
        art = f'<g fill="{ACCENT}">' + "".join(
            f'<rect x="{ax + xi * cell:.1f}" y="{ay + yi * cell:.1f}" width="{cell * .86:.1f}" height="{cell * .86:.1f}" fill-opacity="{.15 + .85 * v:.2f}"/>'
            for yi, row in enumerate(matrix) for xi, v in enumerate(row) if v is not None and v >= .08) + "</g>"

    rows, clips = [], []
    lx, vx, y0, rh = RX + 22, RX + 150, RY + 64, 34
    for i, (label, value) in enumerate(INFO):
        value = value.replace("{repos}", repos)
        y, t = y0 + i * rh, START + i * STEP
        clips.append(f'<clipPath id="v{i}"><rect x="{vx}" y="{y - 14}" height="20" width="0">'
                     f'<animate attributeName="width" from="0" to="{len(value) * 7.4 + 12:.0f}" begin="{t + .12:.2f}s" dur="0.45s" fill="freeze"/></rect></clipPath>')
        rows.append(f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{t:.2f}s" dur="0.2s" fill="freeze"/>'
                    f'<text x="{lx}" y="{y}" fill="{MUTED}" font-size="12.5">{escape(label)}</text>'
                    f'<text x="{vx}" y="{y}" fill="{TEXT}" font-size="12.5" clip-path="url(#v{i})">{escape(value)}</text>'
                    f'<line x1="{lx}" y1="{y + 11}" x2="{RX + RW - 22}" y2="{y + 11}" stroke="{ACCENT}" stroke-opacity="0.08"/></g>')
    end_t = START + len(INFO) * STEP + .4
    cy = y0 + len(INFO) * rh - 4
    cursor = (f'<rect x="{lx}" y="{cy - 12}" width="8" height="15" fill="{ACCENT}" opacity="0">'
              f'<animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.01;0.5;0.51;1" dur="1s" begin="{end_t:.2f}s" repeatCount="indefinite"/></rect>')

    body = frame(H, f"{USERNAME.lower()}@github ~ $ ./profile-scan --live", live=True) + f"""
<defs>
  <linearGradient id="beam" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{ACCENT}" stop-opacity="0"/>
    <stop offset="0.85" stop-color="{ACCENT}" stop-opacity="0.35"/><stop offset="1" stop-color="#fff" stop-opacity="0.9"/></linearGradient>
  <clipPath id="reveal"><rect x="{LX}" y="{ay}" width="{LW}" height="0"><animate attributeName="height" from="0" to="{size + 4}" dur="{SCAN}s" fill="freeze"/></rect></clipPath>
  {''.join(clips)}
</defs>
<rect x="{LX}" y="{LY}" width="{LW}" height="{LH}" rx="10" fill="{PANEL}" stroke="{ACCENT}" stroke-opacity="0.35"/>
<text x="{LX + 16}" y="{LY + 22}" fill="{MUTED}" font-family="{MONO}" font-size="11" letter-spacing="2">VISUAL.MAP</text>
<g clip-path="url(#reveal)">{art}</g>
<rect x="{LX + 4}" y="{ay - 26}" width="{LW - 8}" height="28" fill="url(#beam)" opacity="0">
  <animate attributeName="y" values="{ay - 26};{ay + size - 26}" dur="{SCAN}s" fill="freeze"/>
  <animate attributeName="opacity" values="1;1;0" keyTimes="0;0.9;1" dur="{SCAN}s" fill="freeze"/></rect>
<rect x="{LX + 4}" y="{ay}" width="{LW - 8}" height="2" fill="{ACCENT}" opacity="0">
  <animate attributeName="y" values="{ay};{ay + size}" dur="4s" begin="{SCAN + 1}s" repeatCount="indefinite"/>
  <animate attributeName="opacity" values="0;0.5;0.5;0" keyTimes="0;0.05;0.9;1" dur="4s" begin="{SCAN + 1}s" repeatCount="indefinite"/></rect>
<rect x="{RX}" y="{RY}" width="{RW}" height="{RH}" rx="10" fill="{PANEL}" stroke="{ACCENT}" stroke-opacity="0.35"/>
<text x="{RX + 16}" y="{RY + 22}" fill="{MUTED}" font-family="{MONO}" font-size="11" letter-spacing="2">SYSTEM.INFO</text>
<text x="{RX + RW - 16}" y="{RY + 22}" text-anchor="end" fill="{ACCENT}" font-family="{MONO}" font-size="11">● LIVE</text>
<g font-family="{MONO}">{''.join(rows)}{cursor}</g>
<rect width="{W}" height="{H}" rx="16" fill="url(#crt)"/>"""
    return svg(H, body, f"Profile scan de {NAME}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="dist")
    ap.add_argument("--avatar", help="imagem local, para testar sem internet")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    avatar = load_avatar(args.avatar)
    grid, total = fetch_contributions()
    files = {
        "header.svg": build_header(),
        "card.svg": build_card(avatar),
        "profile-scan.svg": build_scan(avatar, fetch_repos()),
        "stack.svg": build_stack(),
        "activity.svg": build_activity(grid, total),
    }
    for name, (command, lines) in TYPED.items():
        files[name] = build_typed(command, lines)
    for t in SECTION_TITLES:
        files[f"title-{t.lower()}.svg"] = build_title(t)
    for name, content in files.items():
        with open(os.path.join(args.outdir, name), "w", encoding="utf-8") as f:
            f.write(content)
        print(f"ok -> {name} ({len(content) // 1024} KB)")


if __name__ == "__main__":
    main()
