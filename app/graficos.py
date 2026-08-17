"""Helpers de gráficos de Plotly compartidos -- portado de calculadora-periodistas/
app/graficos.py (Colombia.com), originalmente de calculadora-periodistas-bloomberglinea.
Sin esto, el tramo de proyección de cierre de mes quedaría repetido en cada gráfico
de línea del proyecto."""

import plotly.graph_objects as go

from calculos import formatear_numero


def agregar_proyeccion(fig: go.Figure, proyeccion: dict | None, x_actual, x_proyectado,
                        color: str = "#36BF58") -> None:
    """Agrega, si `proyeccion` no es None (ver datos_reales.proyeccion_fin_de_mes), un tramo
    punteado desde el último punto real hasta un punto de cierre proyectado. Nunca reemplaza ni
    oculta el dato real -- solo lo extiende con una lectura aparte, claramente distinta (línea
    punteada, marcador hueco, texto "(proy.)")."""
    if not proyeccion:
        return
    fig.add_trace(go.Scatter(
        x=[x_actual, x_proyectado],
        y=[proyeccion["valor_actual"], proyeccion["valor_proyectado"]],
        mode="lines+markers+text",
        line=dict(color=color, width=2, dash="dot"),
        marker=dict(size=[0, 12], symbol="diamond-open", color=color, line=dict(width=2, color=color)),
        text=["", formatear_numero(proyeccion["valor_proyectado"])],
        textposition="top center",
        hovertemplate=(
            f"Proyección de cierre de mes<br>con datos de {proyeccion['dias_transcurridos']} de "
            f"{proyeccion['dias_totales']} días<br>~%{{y:,.0f}}<extra></extra>"
        ),
        showlegend=False,
    ))


def texto_metodologia_proyeccion(proyeccion: dict) -> str:
    """Explica en una frase cómo sale el número proyectado, para que no se lea como una
    caja negra."""
    base = (
        f" El tramo punteado es una **proyección de cierre**: se toma el acumulado real de "
        f"los primeros {proyeccion['dias_transcurridos']} de {proyeccion['dias_totales']} días "
        f"del mes y se estira al mismo ritmo diario para lo que falta -- una regla de tres "
        f"simple, no un modelo. No es un dato confirmado: se recalcula solo cuando se "
        f"refrescan los datos."
    )
    if proyeccion.get("es_estimado") and proyeccion.get("ventana_ini") and proyeccion.get("ventana_fin"):
        base += (
            f" El export diario de GA4 trae una ventana móvil ({proyeccion['ventana_ini']:%d/%m}-"
            f"{proyeccion['ventana_fin']:%d/%m}) que arranca antes del día 1 del mes -- el "
            f"acumulado real ya viene prorrateado para excluir esa parte de fuera del mes, así "
            f"que no es un corte exacto día 1 -> hoy, es una estimación."
        )
    return base


def marcar_mes_parcial(fig: go.Figure, x_ultimo, y_ultimo) -> None:
    """Para gráficos donde NO tiene sentido proyectar (índices, posición promedio -- no crecen
    linealmente con los días del mes): solo avisa que el último punto es de un mes en curso, sin
    inventar un valor de cierre."""
    fig.add_annotation(
        x=x_ultimo, y=y_ultimo, text="mes en curso, dato parcial", showarrow=True, arrowhead=0,
        arrowcolor="#94A3B8", ax=0, ay=32, font=dict(size=10, color="#64748B"),
        bgcolor="rgba(255,255,255,0.92)", bordercolor="#94A3B8", borderwidth=1, borderpad=3,
    )
