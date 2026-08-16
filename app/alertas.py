"""Vista Alertas — señales de estado actual (SEO, canibalización, CTR, eficiencia)
que ya se pueden medir con un solo mes de datos. Las alertas de TENDENCIA (ej.
"4+ semanas con eficiencia baja") siguen bloqueadas hasta acumular varios periodos
— eso no ha cambiado y se explica en la propia vista."""

import streamlit as st

from estilos import kpi_card

COLOR_SEVERIDAD = {"CRÍTICO": ("#FEE2E2", "#991B1B", "🔴"), "ATENCIÓN": ("#FEF3C7", "#92400E", "🟡")}
ICONO_TIPO = {"SEO": "🧭", "Canibalización": "🔁", "CTR": "🎯", "Eficiencia": "📉"}


def _kpis(tabla):
    n_criticos = int(tabla["en_alerta"].sum())
    n_con_alertas = int((tabla["alertas"].apply(len) > 0).sum())
    total_alertas = int(tabla["alertas"].apply(len).sum())
    limpios = int((tabla["alertas"].apply(len) == 0).sum())

    tarjetas = [
        kpi_card("🔴", "Periodistas con alerta crítica", f"{n_criticos}"),
        kpi_card("🟡", "Periodistas con alguna alerta", f"{n_con_alertas}"),
        kpi_card("📋", "Total de alertas activas", f"{total_alertas}"),
        kpi_card("✅", "Periodistas sin alertas", f"{limpios}"),
    ]
    st.markdown(f'<div class="cp-kpi-row">{"".join(tarjetas)}</div>', unsafe_allow_html=True)


def _tarjeta_periodista(fila):
    alertas = sorted(fila["alertas"], key=lambda a: a["severidad"] != "CRÍTICO")
    if not alertas:
        return
    n_criticas = sum(1 for a in alertas if a["severidad"] == "CRÍTICO")
    borde = "#DC2626" if n_criticas else "#F59E0B"
    with st.container(border=True, key=f"alerta_{fila['slug']}"):
        col_nombre, col_boton = st.columns([3, 1])
        col_nombre.markdown(f"**{fila['periodista']}** · {fila['seccion']}")
        if col_boton.button("Ver perfil →", key=f"btn_alerta_{fila['slug']}", width="stretch"):
            st.session_state.periodista_slug = fila["slug"]
            st.session_state.vista = "individual"
            st.rerun()
        for a in alertas:
            bg, fg, icono_sev = COLOR_SEVERIDAD[a["severidad"]]
            icono_tipo = ICONO_TIPO.get(a["tipo"], "•")
            st.markdown(
                f'<div style="background:{bg};color:{fg};border-radius:8px;padding:8px 12px;'
                f'margin-top:6px;font-size:0.92rem">{icono_sev} {icono_tipo} <b>{a["tipo"]}</b> — {a["mensaje"]}</div>',
                unsafe_allow_html=True,
            )


def render(tabla):
    st.subheader("Alertas — estado actual del equipo")
    st.info(
        "⚠️ Estas alertas son de **estado actual** (cumplimiento SEO, canibalización, CTR, eficiencia "
        "relativa al equipo) — todas medibles con los datos de este mes. Las alertas de **tendencia** "
        "(ej. \"4+ semanas seguidas con eficiencia baja\") siguen bloqueadas hasta que acumulemos varios "
        "meses de historial — con un solo periodo no hay tendencia que medir.",
        icon="ℹ️",
    )
    _kpis(tabla)
    st.write("")

    ordenado = tabla.copy()
    ordenado["n_alertas"] = ordenado["alertas"].apply(len)
    ordenado["n_criticas"] = ordenado["alertas"].apply(lambda al: sum(1 for a in al if a["severidad"] == "CRÍTICO"))
    ordenado = ordenado.sort_values(["n_criticas", "n_alertas"], ascending=False)

    con_alertas = ordenado[ordenado["n_alertas"] > 0]
    sin_alertas = ordenado[ordenado["n_alertas"] == 0]

    if con_alertas.empty:
        st.success("Ningún periodista tiene alertas activas este periodo.")
    else:
        for _, fila in con_alertas.iterrows():
            _tarjeta_periodista(fila)

    if not sin_alertas.empty:
        st.write("")
        st.caption("Sin alertas activas: " + ", ".join(sin_alertas["periodista"].tolist()))
