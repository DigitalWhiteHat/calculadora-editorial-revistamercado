"""Orquesta el cierre de un mes: lo convierte de "parcial" (Rutina A,
actualizado a diario) a periodo FIJO nuevo, con el mismo nivel de detalle
que julio 2026 hoy (semáforo SEO censo, entidades/temas, canibalización).

ESTADO REAL (16-ago-2026) -- léelo antes de correr esto en automático:
De los 6 pasos de abajo, los 5 primeros ya son genéricos (corren sobre
cualquier mes sin tocar código). El sexto -- enriquecer con EEAT y con
tendencia_periodistas()/tendencia_secciones() -- SIGUE hardcodeado a
julio+enero-junio en eeat_periodista.py y enriquecer_periodistas_mes.py.
Este script NO llama esos dos por eso mismo: imprime un aviso explícito al
final y se detiene ahí, en vez de fingir que terminó. Generalizar esos 2
scripts (agregar el mes que cierra a la lista de fuentes que ya leen) es
trabajo pendiente antes de que el cierre sea 100% automático de punta a
punta -- avisarle a Edwin, no saltárselo en silencio.

Uso: python3 data/cerrar_mes.py <mes AAAA-MM>
Ej.: python3 data/cerrar_mes.py 2026-08

Requiere que ya existan en data/raw/ los exports crudos del mes completo
(ga4_<sufijo>.csv, gsc_search|discover|news_<sufijo>.csv) -- eso lo baja
Edwin del exportador de Search Console/GA4, no viene del export diario de
Drive (ese es solo ventana móvil, no sirve para un censo).
"""

import subprocess
import sys
from calendar import monthrange
from pathlib import Path

import pandas as pd

DIR = Path(__file__).parent


def sufijo_de_mes(mes: str) -> str:
    anio, m = mes.split("-")
    ultimo_dia = monthrange(int(anio), int(m))[1]
    return f"{mes}-01_{mes}-{ultimo_dia:02d}"


def _correr(descripcion: str, args: list[str]) -> None:
    print(f"\n=== {descripcion} ===")
    r = subprocess.run([sys.executable] + args, cwd=DIR.parent)
    if r.returncode != 0:
        print(f"FALLÓ: {descripcion} (código {r.returncode}) -- deteniendo la cadena, no sigue a ciegas.")
        sys.exit(1)


def _adaptar_notas_con_autor(mes: str, sufijo: str) -> None:
    """scrape_semaforo.py espera data/notas_con_autor_<sufijo>.csv (esquema de
    julio: autor,titulo,seccion,fecha,es_sindicado,error,ruta,vistas) -- la
    Rutina A produce data/notas_<mes>.csv con un esquema distinto (acumulado
    día a día por construir_notas_mes_actual.py). Este puente los concilia
    para que el resto de la cadena no necesite tocarse."""
    origen = DIR / f"notas_{mes}.csv"
    if not origen.exists():
        print(f"FALTA {origen} -- corre construir_notas_mes_actual.py + "
              f"construir_periodistas_mes.py para {mes} varias veces durante "
              f"el mes (la Rutina A diaria) antes de poder cerrarlo.")
        sys.exit(1)
    notas = pd.read_csv(origen)
    salida = pd.DataFrame({
        "autor": notas["autor"],
        "titulo": notas["titulo"],
        "seccion": notas["seccion"],
        "fecha": notas["fecha_real"],
        "es_sindicado": False,
        "error": None,
        "ruta": notas["ruta"],
        "vistas": notas["vistas"],
    })
    salida.to_csv(DIR / f"notas_con_autor_{sufijo}.csv", index=False)
    print(f"{len(salida)} notas -> notas_con_autor_{sufijo}.csv")


def main(mes: str):
    sufijo = sufijo_de_mes(mes)
    print(f"Cerrando {mes} (sufijo {sufijo})")

    _correr("1/6 Cruzar GA4+GSC por URL", ["data/procesar_exports.py", sufijo])
    _adaptar_notas_con_autor(mes, sufijo)
    _correr("3/6 Scrapear semáforo SEO (HTML real)", ["data/scrape_semaforo.py", sufijo])
    _correr("4/6 Calificar semáforo SEO (23 reglas)", ["data/semaforo_scoring.py", sufijo])
    _correr("5/6 Entidades/temas por periodista", ["data/entidades_periodista.py"])
    _correr("6/6 Detectar canibalización", ["data/detectar_canibalizacion.py", sufijo])

    print(f"""
{mes} cerrado hasta donde este script llega. FALTA A MANO todavía:
1. Agregar "{mes}": {{"tipo": "completo" o "historico", ...}} a PERIODOS en
   app/datos_reales.py (y quitarlo de ahí como periodo "parcial" si estaba).
2. eeat_periodista.py y enriquecer_periodistas_mes.py NO se corrieron -- están
   hardcodeados a julio+enero-junio, hay que generalizarlos para que incluyan
   "{mes}" antes de que el perfil de EEAT y la tendencia de 7+ meses lo reflejen.
   Sin este paso, {mes} queda con censo SEO completo pero sin EEAT ni entrar
   en las herramientas de "7 meses acumulados" (Reemplazos, simulador, etc.)
""")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python3 data/cerrar_mes.py <mes AAAA-MM>")
        sys.exit(1)
    main(sys.argv[1])
