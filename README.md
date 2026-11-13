# Guía EPG Rakuten TV España (XMLTV)

Este repositorio genera y actualiza automáticamente cada 12 horas la guía electrónica de programas (**EPG**) en formato estándar **XMLTV** para los canales FAST en directo de Rakuten TV España, además de mantener un listado actualizado de los canales en `canales.txt`.

## Enlaces Directos (Raw)

Una vez subido a tu repositorio de GitHub, podrás usar las siguientes URLs directas en tu reproductor IPTV (TiviMate, Kodi, Jellyfin, Plex, IPTV Smarters, etc.):

- **Guía XMLTV comprimida (Recomendada):**
  ```text
  https://raw.githubusercontent.com/parotris3/epg-rakuten/main/rakuten_es_epg.xml.gz
  ```
- **Guía XMLTV sin comprimir:**
  ```text
  https://raw.githubusercontent.com/parotris3/epg-rakuten/main/rakuten_es_epg.xml
  ```
- **Listado de canales:**
  ```text
  https://raw.githubusercontent.com/parotris3/epg-rakuten/main/canales.txt
  ```

---

## Archivos del Repositorio

- `rakuten_epg.py`: Script principal en Python (sin librerías de terceros).
- `canales.txt`: Lista en texto plano con el nombre de todos los canales incluidos en la EPG.
- `rakuten_es_epg.xml`: Guía EPG en formato XML estándar XMLTV.
- `rakuten_es_epg.xml.gz`: Versión comprimida de la guía EPG.
- `.github/workflows/epg.yml`: Automatización de GitHub Actions que se ejecuta diariamente a las 06:00 y a las 18:00 (hora peninsular española).
