"""Core Web Vitals reales de revistamercado.do vía PageSpeed Insights API (mobile).
Adaptado de calculadora-periodistas/data/medir_core_web_vitals.py (colombia.com) --
misma lógica, mismo esquema de salida, solo cambian las páginas medidas.

Usa datos de campo (CrUX, tráfico real de usuarios) cuando la URL tiene volumen
suficiente; si PSI hace origin_fallback (URL específica sin tráfico suficiente en
CrUX), lo marca explícitamente -- no lo mezcla con datos de página real sin avisar.
Datos de laboratorio (Lighthouse) se guardan aparte como respaldo, nunca como
sustituto silencioso del dato de campo.

Requiere PAGESPEED_API_KEY en .env -- reutiliza la misma key que colombia.com
(PageSpeed Insights no restringe por dominio), confirmado con Edwin 16-ago-2026.
"""
import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

DIR = Path(__file__).parent
ENV_FILE = DIR.parent / ".env"

PAGINAS = [
    ("Home", "https://revistamercado.do/"),
    ("Actualidad", "https://revistamercado.do/actualidad/"),
    ("Money Invest", "https://revistamercado.do/money-invest/"),
    ("Lifestyle", "https://revistamercado.do/lifestyle/"),
]

UMBRALES = {
    "LARGEST_CONTENTFUL_PAINT_MS": {"bueno": 2500, "mejorable": 4000, "unidad": "ms"},
    "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"bueno": 10, "mejorable": 25, "unidad": "x0.01"},
    "INTERACTION_TO_NEXT_PAINT": {"bueno": 200, "mejorable": 500, "unidad": "ms"},
}


def _cargar_api_key() -> str:
    if ENV_FILE.exists():
        for linea in ENV_FILE.read_text().splitlines():
            if linea.startswith("PAGESPEED_API_KEY="):
                return linea.split("=", 1)[1].strip()
    raise SystemExit("Falta PAGESPEED_API_KEY en .env")


def _medir(url: str, api_key: str) -> dict:
    params = f"url={urllib.parse.quote(url, safe='')}&key={api_key}&strategy=mobile&category=performance"
    endpoint = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?{params}"
    with urllib.request.urlopen(endpoint, timeout=90) as resp:
        return json.load(resp)


def main():
    api_key = _cargar_api_key()
    filas = []
    for nombre, url in PAGINAS:
        print(f"Midiendo {nombre} ({url})...")
        try:
            try:
                data = _medir(url, api_key)
            except Exception:
                time.sleep(3)
                data = _medir(url, api_key)
        except Exception as e:
            print(f"  ERROR: {e}")
            filas.append({"pagina": nombre, "url": url, "error": str(e)})
            continue

        le = data.get("loadingExperience", {})
        le_origen = data.get("originLoadingExperience", {})
        es_fallback = "metrics" not in le or not le.get("metrics")
        metrics_usadas = le.get("metrics") if not es_fallback else le_origen.get("metrics", {})
        fuente = "página específica" if not es_fallback else "fallback a dominio completo"

        lh = data.get("lighthouseResult", {})
        score_lab = lh.get("categories", {}).get("performance", {}).get("score")
        audits = lh.get("audits", {})

        fila = {
            "pagina": nombre,
            "url": url,
            "fuente_campo": fuente,
            "score_laboratorio": round(score_lab * 100) if score_lab is not None else None,
            "lcp_lab": audits.get("largest-contentful-paint", {}).get("displayValue"),
            "cls_lab": audits.get("cumulative-layout-shift", {}).get("displayValue"),
            "fcp_lab": audits.get("first-contentful-paint", {}).get("displayValue"),
        }
        for clave_api, clave_out in [
            ("LARGEST_CONTENTFUL_PAINT_MS", "lcp_campo_ms"),
            ("CUMULATIVE_LAYOUT_SHIFT_SCORE", "cls_campo_x100"),
            ("INTERACTION_TO_NEXT_PAINT", "inp_campo_ms"),
        ]:
            m = metrics_usadas.get(clave_api, {})
            fila[clave_out] = m.get("percentile")
            fila[f"{clave_out}_categoria"] = m.get("category")
        fila["overall_category_campo"] = (
            le.get("overall_category") if not es_fallback else le_origen.get("overall_category")
        )
        filas.append(fila)
        time.sleep(1)

    campos = ["pagina", "url", "fuente_campo", "overall_category_campo",
              "lcp_campo_ms", "lcp_campo_ms_categoria",
              "cls_campo_x100", "cls_campo_x100_categoria",
              "inp_campo_ms", "inp_campo_ms_categoria",
              "score_laboratorio", "lcp_lab", "cls_lab", "fcp_lab", "error"]
    out = DIR / "cwv_diagnostico.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for fila in filas:
            w.writerow(fila)
    print(f"\nGuardado -> {out}")
    for fila in filas:
        if "error" in fila and fila.get("error"):
            print(f"  {fila['pagina']}: ERROR {fila['error']}")
        else:
            print(f"  {fila['pagina']}: LCP {fila.get('lcp_campo_ms')}ms "
                  f"({fila.get('lcp_campo_ms_categoria')}) · "
                  f"CLS {fila.get('cls_campo_x100')} ({fila.get('cls_campo_x100_categoria')}) · "
                  f"INP {fila.get('inp_campo_ms')}ms ({fila.get('inp_campo_ms_categoria')}) · "
                  f"[{fila.get('fuente_campo')}]")


if __name__ == "__main__":
    main()
