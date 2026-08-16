"""Avatares: usa la foto real del periodista si existe en
assets/fotos_periodistas/{slug}.jpg (extraída de la caja de autor de
revistamercado.do vía data/extraer_fotos_autor.py — 6 de 14 autores tienen
foto real subida; el resto usa Gravatar genérico o SVG de silueta, así que
no se descarga nada y se cae al placeholder de iniciales sobre color)."""

import base64
import os
import re
from io import BytesIO

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

FOTOS_DIR = "assets/fotos_periodistas"


def _slugify(nombre: str) -> str:
    s = str(nombre).lower()
    s = s.translate(str.maketrans("áéíóúñ", "aeioun"))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _iniciales(nombre: str) -> str:
    partes = nombre.split()
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


@st.cache_data
def avatar_png_bytes(nombre: str, color: str, tamano: int = 160) -> bytes:
    """Círculo de color con iniciales — mismo tratamiento circular que las
    fotos reales (ver foto_circular_png_bytes), para que ambos tipos de
    avatar se vean consistentes cuando aparecen juntos en el mismo gráfico."""
    escala = 4
    grande = tamano * escala
    img = Image.new("RGB", (grande, grande), color)
    draw = ImageDraw.Draw(img)
    texto = _iniciales(nombre)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(grande * 0.4))
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), texto, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((grande - w) / 2 - bbox[0], (grande - h) / 2 - bbox[1]), texto, fill="white", font=font)

    mascara = Image.new("L", (grande, grande), 0)
    ImageDraw.Draw(mascara).ellipse((0, 0, grande, grande), fill=255)
    circular = Image.new("RGBA", (grande, grande))
    circular.paste(img, (0, 0), mascara)
    circular = circular.resize((tamano, tamano), Image.LANCZOS)

    buf = BytesIO()
    circular.save(buf, format="PNG")
    return buf.getvalue()


MIME_POR_EXT = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
BORDE_FOTO = (199, 32, 53)  # #C72035 — mismo rojo de marca que usa revistamercado.do
                             # en el borde circular de su propia .author-avatar


def _buscar_foto(nombre: str) -> str | None:
    slug = _slugify(nombre)
    for ext in MIME_POR_EXT:
        ruta = os.path.join(FOTOS_DIR, f"{slug}{ext}")
        if os.path.exists(ruta):
            return ruta
    return None


@st.cache_data
def foto_circular_png_bytes(ruta_foto: str, tamano: int = 160) -> bytes:
    """Recorta la foto real a un círculo con borde, en vez de pegarla cuadrada
    tal cual — sin esto, las fotos reales (rectangulares, fondos distintos)
    se ven inconsistentes junto a los avatares de iniciales (círculos limpios
    de color sólido), sobre todo cuando se amontonan varios en el cuadrante."""
    escala = 4  # supersample para que el borde del círculo salga suave
    grande = tamano * escala
    img = Image.open(ruta_foto).convert("RGB")
    lado = min(img.size)
    img = img.crop(((img.width - lado) // 2, (img.height - lado) // 2,
                     (img.width + lado) // 2, (img.height + lado) // 2))
    img = img.resize((grande, grande), Image.LANCZOS)

    mascara = Image.new("L", (grande, grande), 0)
    ImageDraw.Draw(mascara).ellipse((0, 0, grande, grande), fill=255)

    circular = Image.new("RGBA", (grande, grande))
    circular.paste(img, (0, 0), mascara)

    grosor = max(1, tamano // 32) * escala
    ImageDraw.Draw(circular).ellipse(
        (grosor // 2, grosor // 2, grande - grosor // 2, grande - grosor // 2),
        outline=BORDE_FOTO, width=grosor,
    )
    circular = circular.resize((tamano, tamano), Image.LANCZOS)

    buf = BytesIO()
    circular.save(buf, format="PNG")
    return buf.getvalue()


@st.cache_data
def avatar_data_uri(nombre: str, color: str, tamano: int = 160) -> str:
    ruta_foto = _buscar_foto(nombre)
    if ruta_foto:
        b64 = base64.b64encode(foto_circular_png_bytes(ruta_foto, tamano)).decode("ascii")
        return f"data:image/png;base64,{b64}"
    b64 = base64.b64encode(avatar_png_bytes(nombre, color, tamano)).decode("ascii")
    return f"data:image/png;base64,{b64}"


@st.cache_data
def logo_revistamercado_data_uri() -> str:
    """Logo real de Revista Mercado (assets/brand/revistamercado_logo.png), descargado
    directamente de revistamercado.do/wp-content/uploads/.../logo-mercado.png para
    conservar la identidad gráfica real del medio en vez de un placeholder genérico.
    Es un PNG SIN transparencia (fondo negro sólido + wordmark "MERCADO" en blanco),
    a diferencia del logo de Colombia.com — por eso no necesita envolverse en una
    tarjeta blanca: ya trae su propio fondo y se ve bien tanto en sidebar claro como oscuro."""
    with open("assets/brand/revistamercado_logo.png", "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"
