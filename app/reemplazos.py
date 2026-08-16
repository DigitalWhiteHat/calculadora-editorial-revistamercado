"""Vista Reemplazos — para cada periodista, quién del resto del equipo podría cubrir
su sección principal si falta (vacaciones, incapacidad, permiso), justificado con
especialización real de 7 meses (data/especializacion_periodista_seccion.csv). No
depende del selector de periodo: es una herramienta de planeación de todo el equipo,
igual que el simulador de escenarios de la pestaña Secciones.

Adaptado de calculadora-periodistas/app/reemplazos.py (Colombia.com), con
seccion_raw (subsección incluida, ej. "empresas/sport-business") en vez del
"seccion" plano de Colombia.com -- RM ya usa esa granularidad en el resto de
la app."""

import pandas as pd
import streamlit as st

import datos_reales as dr
from avatares import avatar_data_uri
from estilos import kpi_card
from secciones import LABELS_SECCION

_CACHE_TTL_REEMPLAZOS = 300

ICONO_CONFIANZA = {"alta": "🟢", "media": "🟡", "baja": "⚪"}
ORDEN_CONFIANZA = {"alta": 0, "media": 1, "baja": 2}
MAX_CANDIDATOS = 3


def _label_seccion(seccion_raw: str) -> str:
    return LABELS_SECCION.get(seccion_raw, dr.seccion_label(seccion_raw) or str(seccion_raw).title())


@st.cache_data(ttl=_CACHE_TTL_REEMPLAZOS)
def _cargar_especializacion() -> pd.DataFrame:
    try:
        return pd.read_csv("data/especializacion_periodista_seccion.csv")
    except FileNotFoundError:
        return pd.DataFrame()


def _color_cobertura(ratio: float) -> tuple[str, str]:
    """Qué tan comparable es la eficiencia del candidato frente al titular en la MISMA
    sección -- >=90% se considera cobertura equivalente (no solo "mejor que nada"),
    60-89% aceptable con caída esperada, <60% respaldo débil."""
    if ratio >= 0.9:
        return "green", "Cobertura equivalente o mejor"
    if ratio >= 0.6:
        return "blue", "Cobertura aceptable, con caída esperada"
    return "red", "Cobertura débil — el tráfico caería de forma notoria"


def _candidatos(esp: pd.DataFrame, titular: str, seccion_raw: str, eficiencia_titular) -> pd.DataFrame:
    candidatos = esp[(esp["seccion"] == seccion_raw) & (esp["autor"] != titular)].copy()
    if candidatos.empty:
        return candidatos
    tiene_baseline = eficiencia_titular is not None and eficiencia_titular > 0
    candidatos["ratio_eficiencia"] = (
        candidatos["trafico_por_nota"] / eficiencia_titular if tiene_baseline else float("nan")
    )
    candidatos["orden_confianza"] = candidatos["confianza"].map(ORDEN_CONFIANZA)
    candidatos = candidatos.sort_values(
        ["orden_confianza", "ratio_eficiencia", "trafico_por_nota"], ascending=[True, False, False]
    )
    return candidatos


def _nivel_respaldo(candidatos: pd.DataFrame) -> tuple[str, str, str]:
    if candidatos.empty:
        return "🔴", "red", "Sin candidato con experiencia en esta sección"
    mejores = candidatos[candidatos["confianza"].isin(["alta", "media"])]
    if mejores.empty:
        return "🟡", "blue", "Solo candidatos con experiencia mínima (⚪ baja confianza)"
    if (mejores["ratio_eficiencia"] >= 0.9).any() or mejores["ratio_eficiencia"].isna().all():
        return "🟢", "green", "Respaldo con experiencia consolidada en la sección"
    return "🟡", "blue", "Respaldo con experiencia, eficiencia por debajo del titular"


def _tarjeta_candidato(row, rank: int, recomendado: bool):
    color_key, texto_cobertura = (
        _color_cobertura(row["ratio_eficiencia"]) if row["ratio_eficiencia"] == row["ratio_eficiencia"] else ("blue", "Sin base de comparación (titular sin datos en esta sección)")
    )
    bg, fg = {"green": ("#DCFCE7", "#166534"), "blue": ("#DBEAFE", "#1E40AF"), "red": ("#FEE2E2", "#991B1B")}[color_key]
    ratio_txt = f"{row['ratio_eficiencia'] * 100:.0f}% de la eficiencia del titular" if row["ratio_eficiencia"] == row["ratio_eficiencia"] else "—"
    etiqueta_rank = "★ Reemplazo recomendado" if recomendado else f"Opción {rank}"
    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:14px;'
        f'background:{bg};border-radius:12px;padding:12px 16px;margin-bottom:8px">'
        f'<div style="min-width:0">'
        f'<div style="font-weight:700;font-size:1.05rem;color:#232020">{etiqueta_rank} — {row["autor"]}</div>'
        f'<div style="font-size:0.95rem;color:#475569;margin-top:2px">'
        f'{ICONO_CONFIANZA.get(row["confianza"], "⚪")} confianza {row["confianza"]} · '
        f'{int(row["notas"])} notas en 7 meses · {row["trafico_por_nota"]:,.0f} tráfico/nota'
        f'</div></div>'
        f'<div style="text-align:right;flex-shrink:0">'
        f'<div style="font-weight:700;color:{fg};font-size:0.92rem;letter-spacing:0.02em">{texto_cobertura.upper()}</div>'
        f'<div style="font-size:0.9rem;color:#64748B;margin-top:2px">{ratio_txt}</div>'
        f'</div></div>'.replace(",", "."),
        unsafe_allow_html=True,
    )


def _tarjeta_titular(meta, tabla, esp):
    fila = tabla[tabla["slug"] == meta["slug"]]
    eficiencia_titular = None
    fila_esp_propia = esp[(esp["autor"] == meta["autor_original"]) & (esp["seccion"] == meta["seccion_raw"])]
    if not fila_esp_propia.empty:
        eficiencia_titular = float(fila_esp_propia.iloc[0]["trafico_por_nota"])

    candidatos = _candidatos(esp, meta["autor_original"], meta["seccion_raw"], eficiencia_titular)
    icono_nivel, _, texto_nivel = _nivel_respaldo(candidatos)
    label_seccion = _label_seccion(meta["seccion_raw"])

    with st.container(border=True, key=f"card_reemplazo_{meta['slug']}"):
        col_foto, col_info = st.columns([1, 6], vertical_alignment="center")
        with col_foto:
            st.markdown(
                f'<img class="cp-avatar-perfil" style="width:56px !important;height:56px !important;'
                f'min-width:56px !important;max-width:56px !important;max-height:56px !important" '
                f'src="{avatar_data_uri(meta["nombre"], "#334155", 120)}">',
                unsafe_allow_html=True,
            )
        with col_info:
            notas_mes = f"{int(fila.iloc[0]['notas'])} notas este mes" if not fila.empty else "sin notas este mes"
            st.markdown(f"**{meta['nombre']}** — sección principal: **{label_seccion}** ({notas_mes})")
            st.caption(f"{icono_nivel} {texto_nivel}")

        if candidatos.empty:
            st.warning(
                f"Ningún otro periodista tiene notas registradas en {label_seccion} en los últimos 7 "
                "meses — no hay candidato con experiencia directa para justificar un reemplazo sin curva "
                "de aprendizaje."
            )
            return

        top = candidatos.head(MAX_CANDIDATOS)
        for i, (_, row) in enumerate(top.iterrows(), start=1):
            _tarjeta_candidato(row, i, recomendado=(i == 1))


def _color_desempeno_seccion(ratio: float) -> tuple[str, str]:
    """Qué tan bien le rinde a este candidato la sección frente a la mediana real de
    quienes YA escriben ahí (columna mediana_seccion_otros) -- mismo criterio de cortes
    que _color_cobertura, pero comparado contra la sección, no contra un titular puntual."""
    if ratio != ratio:
        return "blue", "Sin mediana de sección para comparar"
    if ratio >= 0.9:
        return "green", "Rendimiento igual o mejor que la mediana de la sección"
    if ratio >= 0.6:
        return "blue", "Rendimiento por debajo de la mediana, con experiencia real"
    return "red", "Rendimiento bajo en esta sección hasta ahora"


def _dominantes_en_seccion(periodistas_meta, seccion_raw: str) -> set:
    return {m["autor_original"] for m in periodistas_meta if m["seccion_raw"] == seccion_raw}


def _candidatos_para_seccion(esp: pd.DataFrame, seccion_raw: str, excluir: set) -> pd.DataFrame:
    candidatos = esp[(esp["seccion"] == seccion_raw) & (~esp["autor"].isin(excluir))].copy()
    if candidatos.empty:
        return candidatos
    mediana = candidatos["mediana_seccion_otros"].iloc[0] if "mediana_seccion_otros" in candidatos else float("nan")
    candidatos["ratio_mediana"] = candidatos["trafico_por_nota"] / mediana if mediana and mediana == mediana else float("nan")
    candidatos["orden_confianza"] = candidatos["confianza"].map(ORDEN_CONFIANZA)
    candidatos = candidatos.sort_values(
        ["orden_confianza", "trafico_por_nota"], ascending=[True, False]
    )
    return candidatos


def _sin_experiencia_en_seccion(periodistas_meta, esp: pd.DataFrame, seccion_raw: str, excluir: set) -> list:
    con_datos = set(esp[esp["seccion"] == seccion_raw]["autor"]) | excluir
    return sorted(
        m["nombre"] for m in periodistas_meta if m["autor_original"] not in con_datos
    )


def _tarjeta_candidato_seccion(row, rank: int):
    color_key, texto = _color_desempeno_seccion(row["ratio_mediana"])
    bg, fg = {"green": ("#DCFCE7", "#166534"), "blue": ("#DBEAFE", "#1E40AF"), "red": ("#FEE2E2", "#991B1B")}[color_key]
    ratio_txt = f"{row['ratio_mediana'] * 100:.0f}% de la mediana de la sección" if row["ratio_mediana"] == row["ratio_mediana"] else "—"
    etiqueta_rank = "★ Mejor opción" if rank == 1 else f"Opción {rank}"
    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:14px;'
        f'background:{bg};border-radius:12px;padding:12px 16px;margin-bottom:8px">'
        f'<div style="min-width:0">'
        f'<div style="font-weight:700;font-size:1.05rem;color:#232020">{etiqueta_rank} — {row["autor"]}</div>'
        f'<div style="font-size:0.95rem;color:#475569;margin-top:2px">'
        f'{ICONO_CONFIANZA.get(row["confianza"], "⚪")} confianza {row["confianza"]} · '
        f'{int(row["notas"])} notas en 7 meses · {row["trafico_por_nota"]:,.0f} tráfico/nota'
        f'</div></div>'
        f'<div style="text-align:right;flex-shrink:0">'
        f'<div style="font-weight:700;color:{fg};font-size:0.92rem;letter-spacing:0.02em">{texto.upper()}</div>'
        f'<div style="font-size:0.9rem;color:#64748B;margin-top:2px">{ratio_txt}</div>'
        f'</div></div>'.replace(",", "."),
        unsafe_allow_html=True,
    )


def _bloque_por_seccion(periodistas_meta, esp):
    st.subheader("¿Qué periodista podría tomar esta sección?")
    st.caption(
        "Vista inversa: eliges una sección (ej. porque necesita más cobertura) y ves quién del equipo, "
        "sin ser ya su titular, tiene mejor base real para asumirla — comparado contra la mediana de tráfico/nota "
        "de quienes ya escriben ahí. Quienes nunca han escrito en la sección se listan aparte, sin inventarles "
        "un número: son una opción exploratoria, no una comparación real."
    )
    secciones_disponibles = sorted(esp["seccion"].unique())
    with st.container(border=True, key="card_seccion_selector"):
        seccion_elegida = st.selectbox(
            "Sección que necesita más cobertura", secciones_disponibles,
            format_func=_label_seccion, key="reemplazo_seccion_elegida",
        )
    label_seccion = _label_seccion(seccion_elegida)
    dominantes = _dominantes_en_seccion(periodistas_meta, seccion_elegida)
    st.write("")

    with st.container(border=True, key="card_seccion_candidatos"):
        if dominantes:
            st.caption(f"Ya escriben {label_seccion} como su sección principal: {', '.join(sorted(dominantes))}.")
        candidatos = _candidatos_para_seccion(esp, seccion_elegida, dominantes)
        if candidatos.empty:
            st.info(f"Nadie más del equipo tiene notas registradas en {label_seccion} en los últimos 7 meses.")
        else:
            top = candidatos.head(MAX_CANDIDATOS)
            for i, (_, row) in enumerate(top.iterrows(), start=1):
                _tarjeta_candidato_seccion(row, i)

        sin_experiencia = _sin_experiencia_en_seccion(periodistas_meta, esp, seccion_elegida, dominantes)
        if sin_experiencia:
            st.caption(f"Sin experiencia registrada en {label_seccion} (opción exploratoria, sin dato para "
                       f"comparar): {', '.join(sin_experiencia)}.")


def _kpis(periodistas_meta, tabla, esp):
    niveles = []
    for meta in periodistas_meta:
        fila_esp_propia = esp[(esp["autor"] == meta["autor_original"]) & (esp["seccion"] == meta["seccion_raw"])]
        eficiencia_titular = float(fila_esp_propia.iloc[0]["trafico_por_nota"]) if not fila_esp_propia.empty else None
        candidatos = _candidatos(esp, meta["autor_original"], meta["seccion_raw"], eficiencia_titular)
        icono, _, _ = _nivel_respaldo(candidatos)
        niveles.append(icono)

    tarjetas = [
        kpi_card("👥", "Periodistas evaluados", f"{len(niveles)}"),
        kpi_card("🟢", "Con respaldo consolidado", f"{niveles.count('🟢')}"),
        kpi_card("🟡", "Con respaldo parcial", f"{niveles.count('🟡')}"),
        kpi_card("🔴", "Sin ningún respaldo", f"{niveles.count('🔴')}",
                  help_text="Nadie más del equipo tiene notas registradas en su sección principal en 7 meses"),
    ]
    st.markdown(f'<div class="cp-kpi-row">{"".join(tarjetas)}</div>', unsafe_allow_html=True)


def render(tabla_periodistas):
    st.subheader("¿Quién puede reemplazar a quién?")
    st.caption(
        "Para cubrir vacaciones, incapacidades o permisos sin afectar el tráfico de la sección: candidatos "
        "con experiencia REAL de 7 meses en la sección principal de cada periodista (ene-jul 2026), "
        "ranqueados por qué tan comparable es su tráfico/nota frente al del titular en esa misma sección. "
        "Confianza: 🟢 alta (≥10 notas) · 🟡 media (3-9) · ⚪ baja (<3, respaldo débil). No mide calidad "
        "editorial (SEO/EEAT) — solo si el candidato ya genera tráfico comparable ahí mismo."
    )
    esp = _cargar_especializacion()
    if esp.empty:
        st.info("El cruce periodista × sección todavía se está procesando.")
        return

    periodistas_meta = dr.cargar_periodistas_meta()
    _kpis(periodistas_meta, tabla_periodistas, esp)
    st.write("")

    nombres = sorted(p["nombre"] for p in periodistas_meta)
    with st.container(border=True, key="card_reemplazo_selector"):
        elegido = st.selectbox("Si esta persona falta, ¿quién la puede reemplazar?", nombres,
                                key="reemplazo_periodista_elegido")
    meta = next(p for p in periodistas_meta if p["nombre"] == elegido)
    st.write("")
    _tarjeta_titular(meta, tabla_periodistas, esp)

    st.write("")
    st.divider()
    _bloque_por_seccion(periodistas_meta, esp)
