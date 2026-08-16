"""CSS y helpers de presentación — paleta de Revista Mercado (revistamercado.do).

Texto/marca: #232020 (gris muy oscuro, sacado del propio sitio) en vez del azul
marino de Colombia.com. Acento de marca: #C72035 (rojo, el color dominante de
categorías/CTAs en revistamercado.do) usado SOLO en el borde de la topbar — nunca
en semáforo de estado, para no confundir "esto es de marca" con "esto es una
alerta crítica" (el rojo de estado ya significa 🔴 en toda la app)."""

import html

import streamlit as st

COLOR_ESTADO = {"green": "#16A34A", "blue": "#3457D5", "red": "#DC2626"}
BG_ESTADO = {"green": "#DCFCE7", "blue": "#DBEAFE", "red": "#FEE2E2"}
TXT_ESTADO = {"green": "#166534", "blue": "#1E40AF", "red": "#991B1B"}

BADGE_COLORS = {
    "purple": ("#EDE9FE", "#7C3AED"),
    "teal": ("#CCFBF1", "#0D9488"),
    "blue": ("#DBEAFE", "#2563EB"),
    "green": ("#DCFCE7", "#16A34A"),
}

CSS_GLOBAL = """
<style>
div[class*="st-key-card_"] {
    background: #FFFFFF;
    border-radius: 14px !important;
    border: 1px solid #E7EAF0 !important;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    padding: 6px 4px;
    height: 100%;
    box-sizing: border-box;
}
/* Tarjetas en la misma fila estiran a la misma altura, para que no se vean desordenadas. */
[data-testid="stColumn"]:has(div[class*="st-key-card_"]) {
    display: flex;
}
[data-testid="stColumn"] > [data-testid="stVerticalBlock"]:has(div[class*="st-key-card_"]),
[data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]:has(div[class*="st-key-card_"]),
[data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]:has(div[class*="st-key-card_"]) {
    height: 100%;
}
[data-testid="stMainBlockContainer"] {
    padding-top: 4rem;
    max-width: 1500px;
    margin: 0 auto;
}
.cp-topbar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 4px 0 14px 0; border-bottom: 2px solid #C72035; margin-bottom: 18px;
}
.cp-brand { display: flex; align-items: center; gap: 10px; }
.cp-brand-logo { font-weight: 700; font-size: 1.05rem; color: #232020; }
.cp-brand-logo-img { height: 40px; width: auto; }
.cp-brand-sep { color: #C7CDD9; }
.cp-brand-label { font-size: 0.72rem; letter-spacing: 0.06em; font-weight: 600; color: #64748B; }
.cp-breadcrumb { color: #64748B; font-size: 0.95rem; margin: 2px 0 14px 0; }
.cp-breadcrumb b { color: #232020; }

.cp-kpi-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 6px; }
.cp-kpi-card {
    background: #FFFFFF; border: 1px solid #E7EAF0; border-radius: 14px;
    padding: 16px 18px; box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
}
.cp-kpi-label { font-size: 0.95rem; color: #64748B; display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
.cp-kpi-value { font-size: 2.1rem; font-weight: 700; color: #232020; line-height: 1.1; }
.cp-kpi-delta { font-size: 0.92rem; font-weight: 600; margin-top: 5px; display: inline-block; }

.cp-pill {
    display: inline-block; padding: 3px 12px; border-radius: 999px;
    font-size: 0.88rem; font-weight: 700; letter-spacing: 0.02em;
}
.cp-delta {
    display: inline-flex; align-items: center; gap: 3px;
    font-size: 0.92rem; font-weight: 600;
}

.cp-metric-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; height: 100%; }
.cp-metric-card {
    background: #FFFFFF; border: 1px solid #E7EAF0; border-radius: 12px;
    padding: 14px 16px; box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    display: flex; flex-direction: column; justify-content: center;
}
.cp-metric-label { font-size: 0.9rem; color: #64748B; margin-bottom: 7px; line-height: 1.25; }
.cp-metric-value { font-size: 1.75rem; font-weight: 700; color: #232020; line-height: 1.15; }
.cp-metric-delta { font-size: 0.9rem; font-weight: 600; margin-top: 5px; }

.cp-icon-badge {
    width: 34px; height: 34px; border-radius: 9px; flex-shrink: 0;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 1.05rem; margin-bottom: 8px;
}
.cp-avatar-badge {
    width: 34px; height: 34px; border-radius: 50%; flex-shrink: 0;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 0.8rem; font-weight: 700; color: #FFFFFF; background: #334155;
}

.cp-card-title { font-size: 0.95rem; color: #64748B; margin-bottom: 6px; }
.cp-card-value { font-size: 1.9rem; font-weight: 700; color: #232020; line-height: 1.15; }
.cp-header-beat { font-size: 1.05rem; color: #334155; margin-top: 4px; font-weight: 500; }
.cp-card-desc { font-size: 1.05rem; color: #64748B; line-height: 1.4; margin-top: 2px; }

.cp-avatar-perfil {
    width: 112px !important; height: 112px !important; min-width: 112px !important;
    max-width: 112px !important; max-height: 112px !important;
    border-radius: 50% !important; object-fit: cover !important; flex-shrink: 0;
    border: 4px solid #FFFFFF; box-shadow: 0 4px 14px rgba(15, 23, 42, 0.18);
    display: block;
}

.cp-nota-list { display: flex; flex-direction: column; }
.cp-nota-row {
    display: flex; align-items: center; gap: 16px;
    padding: 12px 4px; border-bottom: 1px solid #F1F3F7;
}
.cp-nota-row:last-child { border-bottom: none; }
.cp-nota-rank {
    width: 30px; height: 30px; border-radius: 50%; flex-shrink: 0;
    background: #F1F5F9; color: #64748B; font-weight: 700; font-size: 0.9rem;
    display: flex; align-items: center; justify-content: center;
}
.cp-nota-rank.top { background: #DCFCE7; color: #166534; }
.cp-nota-info { flex: 1; min-width: 0; }
.cp-nota-titulo {
    font-weight: 600; color: #232020; font-size: 1rem;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.cp-nota-meta { font-size: 0.84rem; color: #64748B; margin-top: 2px; }
.cp-nota-bar-track { background: #F1F5F9; border-radius: 6px; height: 6px; margin-top: 7px; overflow: hidden; }
.cp-nota-bar-fill { height: 100%; border-radius: 6px; }
.cp-nota-trafico { text-align: right; flex-shrink: 0; min-width: 90px; }
.cp-nota-clics { font-weight: 700; color: #232020; font-size: 1.1rem; }
.cp-nota-pct { font-size: 0.8rem; color: #64748B; margin-top: 2px; }

@media (prefers-color-scheme: dark) {
    div[class*="st-key-card_"],
    .cp-kpi-card, .cp-metric-card { background: #10182B; border-color: #223052 !important; }
    .cp-kpi-value, .cp-metric-value, .cp-card-value { color: #E4E9F2; }
    .cp-topbar { border-color: #C72035; }
    .cp-brand-logo { color: #E4E9F2; }
    .cp-breadcrumb b { color: #E4E9F2; }
    .cp-nota-row { border-color: #223052; }
    .cp-nota-titulo { color: #E4E9F2; }
    .cp-nota-clics { color: #E4E9F2; }
    .cp-nota-bar-track { background: #223052; }
    .cp-nota-rank { background: #223052; color: #94A3B8; }
}
</style>
"""


SCRIPT_NOINDEX = """
<script>
(function() {
    if (!document.querySelector('meta[name="robots"]')) {
        const meta = document.createElement('meta');
        meta.name = 'robots';
        meta.content = 'noindex, nofollow';
        document.head.appendChild(meta);
    }
})();
</script>
"""


def inyectar_css():
    st.html(CSS_GLOBAL)
    # Datos por periodista con nombre propio -- nunca debe indexarse, sin importar el hosting.
    st.html(SCRIPT_NOINDEX)


def pill(texto: str, color_key: str) -> str:
    return (f'<span class="cp-pill" style="background:{BG_ESTADO[color_key]};'
            f'color:{TXT_ESTADO[color_key]}">{html.escape(texto)}</span>')


def pill(texto: str, color_key: str) -> str:
    return (f'<span class="cp-pill" style="background:{BG_ESTADO[color_key]};'
            f'color:{TXT_ESTADO[color_key]}">{html.escape(texto)}</span>')


def icon_badge(icono: str, color_key: str = "blue") -> str:
    bg, fg = BADGE_COLORS.get(color_key, BADGE_COLORS["blue"])
    return f'<div class="cp-icon-badge" style="background:{bg};color:{fg}">{icono}</div>'


def avatar_badge(nombre: str) -> str:
    partes = nombre.split()
    iniciales = (partes[0][0] + partes[-1][0]).upper() if len(partes) > 1 else partes[0][:2].upper()
    return f'<div class="cp-avatar-badge">{html.escape(iniciales)}</div>'


def delta_html(actual: float, anterior, decimales: int = 0, es_bueno_si_sube: bool = True) -> str:
    if anterior in (0, None) or (hasattr(anterior, "__len__") is False and anterior != anterior):
        return '<span class="cp-delta" style="color:#94A3B8">— sin dato previo</span>'
    delta = (actual - anterior) / abs(anterior) * 100
    sube = delta >= 0
    bueno = sube if es_bueno_si_sube else not sube
    color = "#16A34A" if bueno else "#DC2626"
    flecha = "▲" if sube else "▼"
    signo = "+" if delta >= 0 else ""
    return f'<span class="cp-delta" style="color:{color}">{flecha} {signo}{delta:.{decimales}f}%</span>'


def card_value(titulo: str, valor: str) -> str:
    return (f'<div class="cp-card-title">{html.escape(titulo)}</div>'
            f'<div class="cp-card-value">{html.escape(valor)}</div>')


def trafico_card(valor: str, delta_html_str: str, secundario: str) -> str:
    delta_block = delta_html_str or '<span class="cp-delta" style="color:#94A3B8">—</span>'
    return (f'<div class="cp-kpi-card" style="height:100%">'
            f'<div class="cp-kpi-label">📊 Tráfico del periodo</div>'
            f'<div class="cp-kpi-value">{html.escape(valor)}</div>'
            f'<div class="cp-kpi-delta">{delta_block}</div>'
            f'<div class="cp-metric-label" style="margin-top:8px;margin-bottom:0">{html.escape(secundario)}</div>'
            f'</div>')


def metrica_card(label: str, valor: str, delta_html_str: str = "", icono: str = "", color_key: str = "blue") -> str:
    delta_block = delta_html_str or '<span class="cp-delta" style="color:#94A3B8">—</span>'
    badge = icon_badge(icono, color_key) if icono else ""
    return (f'<div class="cp-metric-card">'
            f'{badge}'
            f'<div class="cp-metric-label">{html.escape(label)}</div>'
            f'<div class="cp-metric-value">{html.escape(valor)}</div>'
            f'<div class="cp-metric-delta">{delta_block}</div>'
            f'</div>')


SEMAFORO_COLOR = {"🟢": "#16A34A", "🟡": "#F59E0B", "🔴": "#DC2626"}


def nota_row(rank: int, titulo: str, meta: str, clics_txt: str, pct_txt: str,
             barra_pct: float, semaforo: str) -> str:
    rank_cls = "cp-nota-rank top" if rank == 1 else "cp-nota-rank"
    color_barra = SEMAFORO_COLOR.get(semaforo, "#3457D5")
    ancho = max(4, min(100, barra_pct))
    return (f'<div class="cp-nota-row">'
            f'<div class="{rank_cls}">{rank}</div>'
            f'<div class="cp-nota-info">'
            f'<div class="cp-nota-titulo">{html.escape(titulo)}</div>'
            f'<div class="cp-nota-meta">{html.escape(meta)} {semaforo}</div>'
            f'<div class="cp-nota-bar-track"><div class="cp-nota-bar-fill" '
            f'style="width:{ancho}%;background:{color_barra}"></div></div>'
            f'</div>'
            f'<div class="cp-nota-trafico">'
            f'<div class="cp-nota-clics">{html.escape(clics_txt)}</div>'
            f'<div class="cp-nota-pct">{html.escape(pct_txt)} del periodista</div>'
            f'</div>'
            f'</div>')


def kpi_card(icono: str, label: str, valor: str, delta_html_str: str = "", help_text: str = "") -> str:
    delta_block = delta_html_str or '<span class="cp-delta" style="color:#94A3B8">—</span>'
    label_seguro = html.escape(label)
    valor_seguro = html.escape(valor)
    if help_text:
        titulo = f'<span title="{html.escape(help_text)}">{label_seguro}</span>'
    else:
        titulo = label_seguro
    return (f'<div class="cp-kpi-card">'
            f'<div class="cp-kpi-label">{icono} {titulo}</div>'
            f'<div class="cp-kpi-value">{valor_seguro}</div>'
            f'<div class="cp-kpi-delta">{delta_block}</div>'
            f'</div>')
