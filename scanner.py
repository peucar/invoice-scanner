import os
import json
import base64
import time
import mimetypes
import requests
from typing import Dict, Any

GEMINI_MODEL = "gemini-2.0-flash"
MAX_RETRIES = 3

def scan_invoice(filepath: str, api_key: str, status_callback=None) -> Dict[str, Any]:
    """
    Sends a file to Gemini to extract data.
    Supports Facturas, Remitos and Notepad Lists.
    Returns a dict with the full AI JSON structure.
    Uses the REST API with inline base64 data for reliability.
    Retries automatically on rate limit (429) errors.
    """
    if not api_key:
        raise ValueError("API Key de Gemini no proporcionada.")

    def _status(msg):
        print(f"[SCANNER] {msg}")
        if status_callback:
            status_callback(msg)

    prompt = (
        "Eres un sistema experto en extraer datos de documentos comerciales.\n"
        "Este documento puede ser una Factura/Remito oficial O una Lista de Pedidos (por ejemplo, exportada de un bloc de notas).\n\n"
        "Analiza el documento y determina su tipo: 'FACTURA', 'REMITO' o 'LISTA_PEDIDOS'.\n\n"
        "1. Si es 'FACTURA' o 'REMITO':\n"
        "   - Extrae el ENCABEZADO (Proveedor, NIF/CUIT, Número, Fecha DD/MM/YYYY, Subtotal, Total, Tipo).\n"
        "   - Extrae los ARTICULOS (codigo, descripcion, cantidad, importe).\n"
        "   - Busca 'Remito Vinculado' para facturas.\n\n"
        "2. Si es 'LISTA_PEDIDOS' (formato bloc de notas):\n"
        "   - Extrae los PEDIDOS. Un documento puede tener varios bloques (ej: 'Pedido Original').\n"
        "   - Formato: 'CÓDIGO X CANTIDAD' (ej: 1103P8 X 1).\n"
        "   - 'llegado': true si el ítem tiene un checkmark (v) O si el texto está tachado (strikethrough).\n"
        "   - 'fecha': busca una fecha en el encabezado (ej: 21/10/25).\n"
        "   - 'proveedor': usa los encabezados de bloque.\n\n"
        "Responde ESTRICTAMENTE con un solo objeto JSON sin formato markdown extra.\n"
        "Estructura:\n"
        "{\n"
        '  "tipo": "FACTURA" | "REMITO" | "LISTA_PEDIDOS",\n'
        '  "factura_data": {\n'
        '    "encabezado": [ {"campo": "Proveedor", "valor": "...", "confianza": "...", "estado": "..."} ],\n'
        '    "articulos": [ {"codigo": "...", "descripcion": "...", "cantidad": "...", "importe": "..."} ]\n'
        "  },\n"
        '  "pedidos_data": [\n'
        '    { "proveedor": "...", "fecha": "DD/MM/YYYY", "articulos": [ {"codigo": "...", "cantidad": "...", "llegado": true} ] }\n'
        "  ]\n"
        "}\n"
    )

    # Read file and encode to base64
    mime_type, _ = mimetypes.guess_type(filepath)
    if not mime_type:
        ext = os.path.splitext(filepath)[1].lower()
        mime_map = {'.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}
        mime_type = mime_map.get(ext, 'application/octet-stream')

    with open(filepath, 'rb') as f:
        file_data = base64.b64encode(f.read()).decode('utf-8')

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [
                {"inlineData": {"mimeType": mime_type, "data": file_data}},
                {"text": prompt}
            ]
        }]
    }

    # Retry loop — wait 60s on 429 (rate limit resets every minute)
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            _status("Analizando documento...")
            resp = requests.post(url, json=payload, timeout=90)
            
            if resp.status_code == 429:
                wait_time = 60  # always wait a full minute for rate limit reset
                _status(f"Límite de solicitudes. Esperando {wait_time}s... (intento {attempt+1}/{MAX_RETRIES})")
                time.sleep(wait_time)
                continue

            resp.raise_for_status()
            json_resp = resp.json()

            if "error" in json_resp:
                raise RuntimeError(json_resp["error"].get("message", "Error desconocido de la API."))

            raw_text = json_resp["candidates"][0]["content"]["parts"][0]["text"].strip()

            # Clean possible markdown backticks
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            return json.loads(raw_text.strip())

        except requests.exceptions.HTTPError as e:
            last_error = e
            if resp.status_code != 429:
                raise
        except Exception as e:
            last_error = e
            raise

    raise RuntimeError(f"Límite de solicitudes agotado tras {MAX_RETRIES} intentos. Esperá un minuto y volvé a intentar.\nDetalle: {last_error}")


