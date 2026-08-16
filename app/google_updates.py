"""Registro de updates de algoritmo de Google confirmados en 2026, para cruzar
contra la línea de tráfico y detectar si una caída/subida coincide con un
algoritmo. Fechas verificadas vía búsqueda (no inventadas) — actualizar cuando
Google confirme uno nuevo.

Fuentes: Search Engine Land, Search Engine Journal, Search Engine Roundtable
(agosto 2026).
"""

from datetime import date

UPDATES_2026 = [
    {"nombre": "Discover Core Update", "tipo": "Discover", "inicio": date(2026, 2, 5), "fin": date(2026, 2, 27)},
    {"nombre": "March 2026 Spam Update", "tipo": "Spam", "inicio": date(2026, 3, 1), "fin": date(2026, 3, 2)},
    {"nombre": "March 2026 Core Update", "tipo": "Core", "inicio": date(2026, 3, 27), "fin": date(2026, 4, 8)},
    {"nombre": "May 2026 Core Update", "tipo": "Core", "inicio": date(2026, 5, 21), "fin": date(2026, 6, 2)},
    {"nombre": "June 2026 Spam Update", "tipo": "Spam", "inicio": date(2026, 6, 24), "fin": date(2026, 6, 26)},
    {"nombre": "August 2026 Core Update", "tipo": "Core", "inicio": date(2026, 8, 26), "fin": None},
]


def updates_en_rango(fecha_ini: date, fecha_fin: date) -> list[dict]:
    """Updates cuyo rango se solapa con [fecha_ini, fecha_fin]."""
    salida = []
    for u in UPDATES_2026:
        fin_u = u["fin"] or u["inicio"]
        if fin_u >= fecha_ini and u["inicio"] <= fecha_fin:
            salida.append(u)
    return salida
