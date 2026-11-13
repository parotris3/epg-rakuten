#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
 Rakuten TV España - Generador de Guía EPG (XMLTV) + Lista de Canales
=============================================================================
 Descarga la programación de todos los canales FAST en directo de Rakuten TV
 España y genera:
   1. Un archivo XML compatible con el estándar XMLTV (y su versión comprimida .gz).
   2. Un archivo 'canales.txt' con el listado de todos los canales incluidos.

 Diseñado para ejecutarse tanto localmente como de forma desatendida en
 GitHub Actions (sin dependencias externas).
=============================================================================
"""

import argparse
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# Parámetros oficiales de la API de Rakuten TV para España
API_BASE = "https://gizmo.rakuten.tv/v3"
CLASSIFICATION_ID = "5"     # 5 = España
MARKET_CODE = "es"
LOCALE = "es"
DEVICE_IDENTIFIER = "web"
PER_PAGE = 50               # Límite por página permitido por la API

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://rakuten.tv/",
    "Origin": "https://rakuten.tv",
}


def sanitize_text(text: str) -> str:
    """Elimina caracteres de control no válidos en XML manteniendo saltos de línea."""
    if not text:
        return ""
    return "".join(c for c in text if c.isprintable() or c in "\n\r\t")


def format_xmltv_datetime(dt: datetime) -> str:
    """Convierte un objeto datetime al formato estándar XMLTV: YYYYMMDDHHMMSS +HHMM."""
    return dt.strftime("%Y%m%d%H%M%S %z")


def fetch_channels_page(page: int, start_dt: datetime, end_dt: datetime, retries: int = 3) -> dict:
    """Solicita una página de canales junto a sus programas para la ventana temporal indicada."""
    starts_str = start_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    ends_str = end_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    params = (
        f"classification_id={CLASSIFICATION_ID}"
        f"&device_identifier={DEVICE_IDENTIFIER}"
        f"&device_stream_audio_quality=2.0"
        f"&device_stream_hdr_type=NONE"
        f"&device_stream_video_quality=FHD"
        f"&epg_duration_minutes=360"
        f"&epg_ends_at={ends_str}"
        f"&epg_ends_at_timestamp={end_dt.timestamp()}"
        f"&epg_starts_at={starts_str}"
        f"&epg_starts_at_timestamp={start_dt.timestamp()}"
        f"&locale={LOCALE}"
        f"&market_code={MARKET_CODE}"
        f"&per_page={PER_PAGE}"
        f"&page={page}"
    )

    url = f"{API_BASE}/live_channels?{params.replace(':', '%3A')}"
    req = urllib.request.Request(url, headers=HEADERS)

    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", errors="ignore")
            if attempt == retries:
                raise RuntimeError(f"Error HTTP {e.code} en página {page}: {msg}")
            time.sleep(2 * attempt)
        except Exception as e:
            if attempt == retries:
                raise RuntimeError(f"Error de conexión en página {page}: {e}")
            time.sleep(2 * attempt)

    return {}


def download_epg_data(days: int = 2) -> tuple[list, list]:
    """Descarga todos los canales y sus programas correspondientes."""
    now_utc = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    end_utc = now_utc + timedelta(days=days)

    print(f"[*] Obteniendo guía EPG para {days} día(s)...")
    print(f"[*] Período: {now_utc.strftime('%Y-%m-%d %H:%M UTC')} hasta {end_utc.strftime('%Y-%m-%d %H:%M UTC')}")

    channels = []
    programmes = []

    page = 1
    total_pages = 1

    while page <= total_pages:
        print(f"  -> Descargando página {page}/{total_pages}...", flush=True)
        data = fetch_channels_page(page, now_utc, end_utc)
        items = data.get("data", [])
        if not items:
            break

        pagination = data.get("meta", {}).get("pagination", {})
        total_pages = pagination.get("total_pages", total_pages)

        for ch in items:
            ch_id = ch.get("id")
            ch_title = ch.get("title", "").strip()
            ch_number = ch.get("channel_number")

            imgs = ch.get("images") or {}
            ch_icon = (
                imgs.get("artwork_negative")
                or imgs.get("artwork")
                or imgs.get("snapshot")
            )

            tags = []
            labels = ch.get("labels") or {}
            for t in labels.get("tags") or []:
                if t.get("name"):
                    tags.append(t.get("name"))

            lang_code = "SPA"
            for lang in labels.get("languages") or []:
                if lang.get("id"):
                    lang_code = lang.get("id")
                    break

            classification = ch.get("classification") or {}
            age_rating = classification.get("name") or classification.get("age")

            channels.append({
                "id": ch_id,
                "title": ch_title,
                "number": ch_number,
                "icon": ch_icon,
                "tags": tags,
                "lang_code": lang_code,
                "age_rating": age_rating,
            })

            for prog in ch.get("live_programs") or []:
                p_title = prog.get("title")
                if not p_title:
                    continue

                try:
                    start_dt = datetime.fromisoformat(prog["starts_at"])
                    end_dt = datetime.fromisoformat(prog["ends_at"])
                except (ValueError, TypeError, KeyError):
                    continue

                p_imgs = prog.get("images") or {}
                p_icon = p_imgs.get("snapshot") or p_imgs.get("snapshot_webp")

                p_class = prog.get("classification") or {}
                p_rating = p_class.get("name") or p_class.get("age") or age_rating

                programmes.append({
                    "channel_id": ch_id,
                    "title": p_title,
                    "subtitle": prog.get("subtitle"),
                    "description": prog.get("description"),
                    "start": start_dt,
                    "end": end_dt,
                    "tags": tags,
                    "icon": p_icon,
                    "rating": p_rating,
                })

        page += 1
        time.sleep(0.3)

    print(f"[+] Descarga completada: {len(channels)} canales y {len(programmes)} programas.")

    # Normalización de eventos
    programmes.sort(key=lambda p: (p["channel_id"], p["start"]))
    by_channel = {}
    for p in programmes:
        by_channel.setdefault(p["channel_id"], []).append(p)

    normalized_progs = []
    for ch_id, plist in by_channel.items():
        for i in range(len(plist)):
            cur = plist[i]
            if i + 1 < len(plist):
                nxt = plist[i + 1]
                if nxt["start"] <= cur["end"]:
                    cur["end"] = nxt["start"]
                else:
                    gap = (nxt["start"] - cur["end"]).total_seconds()
                    if 0 < gap <= 60:
                        cur["end"] = nxt["start"]
            normalized_progs.append(cur)

    return channels, normalized_progs


def build_xmltv(channels: list, programmes: list) -> ET.ElementTree:
    """Genera la estructura XMLTV estándar."""
    root = ET.Element("tv")
    root.set("generator-info-name", "RakutenTV-ES-EPG-Generator")
    root.set("generator-info-url", "https://rakuten.tv/es")
    root.set("source-info-name", "Rakuten TV España Live Channels")

    for ch in channels:
        ch_elem = ET.SubElement(root, "channel", id=str(ch["id"]))

        name_elem = ET.SubElement(ch_elem, "display-name", lang="es")
        name_elem.text = sanitize_text(ch["title"])

        if ch.get("number"):
            num_elem = ET.SubElement(ch_elem, "display-name")
            num_elem.text = str(ch["number"])

        if ch.get("icon"):
            ET.SubElement(ch_elem, "icon", src=ch["icon"])

    for pr in programmes:
        prog_elem = ET.SubElement(
            root,
            "programme",
            channel=str(pr["channel_id"]),
            start=format_xmltv_datetime(pr["start"]),
            stop=format_xmltv_datetime(pr["end"]),
        )

        title_elem = ET.SubElement(prog_elem, "title", lang="es")
        title_elem.text = sanitize_text(pr["title"])

        if pr.get("subtitle"):
            sub_elem = ET.SubElement(prog_elem, "sub-title", lang="es")
            sub_elem.text = sanitize_text(pr["subtitle"])

        if pr.get("description"):
            desc_elem = ET.SubElement(prog_elem, "desc", lang="es")
            desc_elem.text = sanitize_text(pr["description"])

        for tag in pr.get("tags") or []:
            cat_elem = ET.SubElement(prog_elem, "category", lang="es")
            cat_elem.text = sanitize_text(tag)

        if pr.get("icon"):
            ET.SubElement(prog_elem, "icon", src=pr["icon"])

        if pr.get("rating"):
            rating_elem = ET.SubElement(prog_elem, "rating", system="ES")
            val_elem = ET.SubElement(rating_elem, "value")
            val_elem.text = str(pr["rating"])

    ET.indent(root, space="  ", level=0)
    return ET.ElementTree(root)


def save_channels_txt(channels: list, filepath: str):
    """Guarda el listado de nombres de canales ordenados alfabéticamente en un fichero de texto."""
    print(f"[*] Guardando listado de canales en: {filepath}...")
    
    # Extraer nombres únicos y ordenarlos alfabéticamente sin distinguir mayúsculas
    names = sorted(list({ch["title"] for ch in channels if ch.get("title")}), key=lambda s: s.lower())

    with open(filepath, "w", encoding="utf-8") as f:
        for name in names:
            f.write(f"{name}\n")

    print(f"[OK] Fichero de canales guardado ({len(names)} canales).")


def main():
    parser = argparse.ArgumentParser(
        description="Generador de XMLTV EPG y canales.txt para Rakuten TV España."
    )
    parser.add_argument(
        "-o", "--output",
        default="rakuten_es_epg.xml",
        help="Ruta del archivo XMLTV de salida (por defecto: rakuten_es_epg.xml)",
    )
    parser.add_argument(
        "-d", "--days",
        type=int,
        default=2,
        help="Días de programación a descargar (1 a 5, por defecto: 2)",
    )
    parser.add_argument(
        "-z", "--gzip",
        action="store_true",
        help="Generar además la versión comprimida en .xml.gz",
    )
    parser.add_argument(
        "-c", "--channels-txt",
        default="canales.txt",
        help="Ruta del archivo de texto con el listado de nombres de canales (por defecto: canales.txt)",
    )

    args = parser.parse_args()

    days = max(1, min(args.days, 5))
    if days != args.days:
        print(f"[!] Días ajustados a {days} (rango admitido: 1 a 5).")

    xml_out_path = args.output
    txt_out_path = args.channels_txt

    start_time = time.time()
    try:
        channels, programmes = download_epg_data(days=days)

        # 1. Guardar canales.txt
        if txt_out_path:
            save_channels_txt(channels, txt_out_path)

        # 2. Construir y guardar XMLTV
        print("[*] Construyendo XMLTV...")
        tree = build_xmltv(channels, programmes)

        print(f"[*] Guardando EPG en: {xml_out_path}...")
        xml_bytes = ET.tostring(tree.getroot(), encoding="utf-8", xml_declaration=True)

        with open(xml_out_path, "wb") as f:
            f.write(xml_bytes)

        size_mb = os.path.getsize(xml_out_path) / (1024 * 1024)
        print(f"[OK] XML guardado: {xml_out_path} ({size_mb:.2f} MB)")

        # 3. Guardar versión .xml.gz si se solicita
        if args.gzip:
            gz_out_path = xml_out_path + ".gz" if not xml_out_path.endswith(".gz") else xml_out_path
            print(f"[*] Comprimiendo en gzip: {gz_out_path}...")
            with gzip.open(gz_out_path, "wb") as f:
                f.write(xml_bytes)
            gz_size_mb = os.path.getsize(gz_out_path) / (1024 * 1024)
            print(f"[OK] XML comprimido: {gz_out_path} ({gz_size_mb:.2f} MB)")

        elapsed = time.time() - start_time
        print(f"\n[OK] ¡Proceso completado en {elapsed:.2f} segundos!")
        print(f"     Total canales: {len(channels)}")
        print(f"     Total programas: {len(programmes)}")

    except KeyboardInterrupt:
        print("\n[!] Proceso detenido por el usuario.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Falló la ejecución: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
