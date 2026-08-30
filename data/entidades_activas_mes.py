"""Entidades/temas ACTIVOS en el mes en curso, por periodista, basado en impresiones
REALES de Search Console -- portado de calculadora-periodistas/data/
entidades_activas_agosto.py (Colombia.com), pedido explícito de Edwin, 19-ago-2026:
"necesito saber qué entidades activas hay en agosto para cada uno de los periodistas
basado en impresiones... si una entidad no es constante en agosto, que se fue a cero...
no es una entidad válida que yo le pueda presentar."

Por qué esto es DISTINTO de "En qué secciones/temas le rinde" (tarjeta ya existente):
esa tarjeta es tráfico PROMEDIO de TODO el histórico acumulado (ene-jul + mes en
curso), sin ninguna señal de vigencia -- una entidad muerta hace semanas puede seguir
ahí arriba solo por el volumen de tráfico que ya generó.

PRIMER INTENTO (descartado): re-extraer entidades/temas y re-fusionar variantes desde
cero, solo sobre las notas del mes en curso (mismo patrón que Colombia.com). Falló en
la práctica: "juegos centroamericanos" (Elba) -- que YA está correctamente marcado
concluido en entidades_periodista.csv, ratio_tendencia_reciente=0.245, verificado
línea por línea contra las capturas reales de Edwin -- salía ACTIVA acá, porque
re-fusionar sobre un corpus mucho más chico (solo las notas de ESTE periodista en
ESTE mes) arma un grupo de rutas distinto al de la fusión sobre el histórico
completo, y la serie de esa sub-selección de rutas puede no ser monótona aunque la
serie del grupo completo sí lo sea con claridad.

Arreglo real: en vez de re-clasificar desde cero, REUSA el veredicto ya validado de
entidades_periodista.csv (misma fusión, mismas 4 señales, ya verificado contra datos
reales) y solo filtra a las entidades/temas que tienen a fondo AL MENOS UNA nota
publicada en el mes en curso -- "¿sigue siendo un tema vigente que además se está
escribiendo este mes?", no una reclasificación paralela con su propio riesgo de
fragmentación.

Uso: python3 data/entidades_activas_mes.py <mes AAAA-MM>
Escribe: data/entidades_activas_<mes>.csv
"""

import sys
from pathlib import Path

import pandas as pd

DIR = Path(__file__).parent


def _motivo(fila) -> str:
    # ratio_tendencia_reciente/ratio_declive_impresiones llegan como NaN (float),
    # no None, cuando pandas relee la columna del CSV -- "is not None" nunca los
    # detecta como faltantes. Bug real encontrado 21-ago-2026 revisando la salida:
    # "precio del dólar" (sin señal de tendencia reciente, correcto) mostraba
    # "estable/creciente (nan% vs. hace unos días)" en vez de caer al siguiente caso.
    tiene_reciente = pd.notna(fila["ratio_tendencia_reciente"])
    tiene_mensual = pd.notna(fila["ratio_declive_impresiones"])
    if tiene_reciente and fila["es_evento_concluido"]:
        # Único caso donde el ratio es un número acotado y legible (<30% por
        # definición del umbral de declive) -- en los demás casos (estable o
        # creciente) el mismo ratio puede salir negativo o por encima de 100%
        # según cómo oscilen los aportes, así que no se muestra como cifra.
        return f"aporte diario de impresiones cayó a {fila['ratio_tendencia_reciente']:.0%} de su nivel de hace unos días"
    if tiene_reciente:
        return "aporte diario de impresiones estable o al alza en los últimos días"
    if tiene_mensual and fila["es_evento_concluido"]:
        return f"impresiones del mes en {fila['ratio_declive_impresiones']:.0%} de su pico mensual histórico"
    if tiene_mensual:
        return f"sigue en {fila['ratio_declive_impresiones']:.0%} de su pico mensual histórico"
    if fila["es_evento_concluido"]:
        return "sin nota nueva o notas ya antiguas (señal de volumen/silencio, sin dato de impresiones)"
    return "sin señal de declive detectada"


def main(mes: str):
    notas = pd.read_csv(DIR / f"notas_{mes}.csv")
    rutas_del_mes = set(notas["ruta"].dropna())
    print(f"Notas de {mes}: {len(notas)} ({len(rutas_del_mes)} rutas únicas)")

    entidades = pd.read_csv(DIR / "entidades_periodista.csv")
    entidades["rutas_set"] = entidades["rutas"].apply(lambda s: set(str(s).split("|")))
    entidades["notas_mes"] = entidades["rutas_set"].apply(lambda rs: len(rs & rutas_del_mes))
    activas_este_mes = entidades[entidades["notas_mes"] >= 1].copy()
    print(f"Entidades/temas con al menos 1 nota en {mes}: {len(activas_este_mes)} de {len(entidades)} totales")

    sin_datos = activas_este_mes["ratio_declive_impresiones"].isna() & activas_este_mes["ratio_tendencia_reciente"].isna()
    activas_este_mes["estado"] = sin_datos.map({True: "SIN_DATOS"}).fillna(
        activas_este_mes["es_evento_concluido"].map({True: "CONCLUIDA", False: "ACTIVA"}))
    activas_este_mes["motivo"] = activas_este_mes.apply(_motivo, axis=1)

    salida = activas_este_mes.rename(columns={"forma": "entidad"})[
        ["autor", "entidad", "tipo", "notas_mes", "estado", "motivo",
         "ratio_declive_impresiones", "ratio_tendencia_reciente"]]
    salida = salida.sort_values(["autor", "estado", "notas_mes"], ascending=[True, True, False])
    out_path = DIR / f"entidades_activas_{mes}.csv"
    salida.to_csv(out_path, index=False)

    n_activas = int((salida["estado"] == "ACTIVA").sum())
    n_concluidas = int((salida["estado"] == "CONCLUIDA").sum())
    n_sindatos = int((salida["estado"] == "SIN_DATOS").sum())
    print(f"-> {out_path} ({len(salida)} filas): {n_activas} ACTIVAS, "
          f"{n_concluidas} CONCLUIDAS, {n_sindatos} SIN_DATOS")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python3 data/entidades_activas_mes.py <mes AAAA-MM>")
        sys.exit(1)
    main(sys.argv[1])
