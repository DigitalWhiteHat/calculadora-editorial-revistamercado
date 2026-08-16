"""Extrae la foto real (Gravatar) y el cargo de cada periodista desde la caja
de autor (.author-box) que revistamercado.do muestra al pie de cada nota —
verificado en vivo 2026-08-06. NO existe en el JSON-LD, solo en el HTML.

La URL de Gravatar SIEMPRE resuelve con HTTP 200 (por defecto cae al ícono
genérico "mystery man" con d=mm) — para saber si el autor tiene foto real
subida hay que pedir la miniatura con d=404 y ver si responde 200 (foto real)
o 404 (no tiene, no descargar el genérico).

Uso: python3 data/extraer_fotos_autor.py <sufijo_fecha>
Lee data/notas_con_autor_<sufijo>.csv (toma la URL de mayor tráfico por autor)
Escribe assets/fotos_periodistas/{slug}.jpg (solo para autores con foto real)
        data/fotos_autor_<sufijo>.csv (autor, slug, cargo, tiene_foto)
"""

import re
import sys

import pandas as pd
import requests

BASE = "https://revistamercado.do"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
EXCLUIR_AUTOR = {"revistamercado", "SIN_AUTOR"}


def slugify(nombre: str) -> str:
    s = str(nombre).lower()
    s = s.translate(str.maketrans("áéíóúñ", "aeioun"))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def extraer_avatar_y_cargo(ruta: str) -> dict:
    r = requests.get(BASE + ruta, headers=HEADERS, timeout=20)
    r.raise_for_status()
    html = r.text
    m_img = re.search(r'<img\s+src="(https://secure\.gravatar\.com/avatar/[a-f0-9]+)[^"]*"\s+class="author-avatar"', html)
    m_cargo = re.search(r'<div class="author-role">\s*([^<]*?)\s*</div>', html)
    return {
        "gravatar_base": m_img.group(1) if m_img else None,
        "cargo": m_cargo.group(1).strip() if m_cargo else None,
    }


def main(sufijo: str):
    df = pd.read_csv(f"data/notas_con_autor_{sufijo}.csv")
    df = df[~df["autor"].isin(EXCLUIR_AUTOR)]
    rep = df.sort_values("vistas", ascending=False).drop_duplicates("autor")

    filas = []
    for _, row in rep.iterrows():
        autor, ruta = row["autor"], row["ruta"]
        slug = slugify(autor)
        print(f"{autor} -> {ruta}")
        try:
            info = extraer_avatar_y_cargo(ruta)
        except Exception as e:
            print(f"  ERROR: {e}")
            filas.append({"autor": autor, "slug": slug, "cargo": None, "tiene_foto": False})
            continue

        tiene_foto = False
        if info["gravatar_base"]:
            # d=404 fuerza que devuelva 404 si NO hay foto real subida, en vez
            # del ícono genérico "mystery man" (d=mm) — así no se descarga un
            # placeholder como si fuera la foto real del periodista.
            check_url = f"{info['gravatar_base']}?s=240&d=404"
            resp = requests.get(check_url, headers=HEADERS, timeout=15)
            if resp.status_code == 200 and resp.content:
                with open(f"assets/fotos_periodistas/{slug}.jpg", "wb") as f:
                    f.write(resp.content)
                tiene_foto = True
                print("  foto real descargada")
            else:
                print("  sin foto real (Gravatar genérico) — se usa iniciales")

        filas.append({"autor": autor, "slug": slug, "cargo": info["cargo"], "tiene_foto": tiene_foto})

    out = pd.DataFrame(filas)
    out.to_csv(f"data/fotos_autor_{sufijo}.csv", index=False)
    print(f"\n{len(out)} autores -> data/fotos_autor_{sufijo}.csv")
    print(f"Con foto real: {out['tiene_foto'].sum()} / {len(out)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 data/extraer_fotos_autor.py <sufijo_fecha>")
        sys.exit(1)
    main(sys.argv[1])
