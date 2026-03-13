import os
import json
import time
from typing import List, Tuple
from google import genai
from google.genai import types

from typing import List, Tuple, Dict, Any

def scan_invoice(filepath: str, api_key: str) -> Tuple[List[Tuple[str, str, str, str]], List[Tuple[str, str, str, str]]]:
    """
    Envía la imagen o PDF a Gemini para extraer los datos de la factura.
    Devuelve: (resultados_encabezado, resultados_articulos)
    - resultados_encabezado: lista de tuplas (Campo, Valor, Confianza, estado)
    - resultados_articulos: lista de tuplas (codigo, descripcion, cantidad, importe)
    """
    if not api_key:
        raise ValueError("API Key de Gemini no proporcionada.")

    client = genai.Client(api_key=api_key)
    
    prompt = (
        "Eres un sistema experto en extraer datos de facturas (preferiblemente de países hispanohablantes).\n"
        "Necesito que extraigas DOS conjuntos de datos de este documento:\n\n"
        "1. ENCABEZADO: Extrae los siguientes campos generales:\n"
        "- Proveedor\n"
        "- NIF / RFC / CUIT\n"
        "- Número de factura (o de Remito si el documento es un Remito)\n"
        "- Fecha de emisión (DD/MM/YYYY)\n"
        "- Subtotal\n"
        "- Total\n"
        "- Tipo de Documento (DEBE ser 'Factura' o 'Remito')\n"
        "- Remito Vinculado (SOLO para Facturas: Busca en la columna 'REMITO' de la tabla de artículos. Ej: 'Rem-A-0013-00089890'. Extrae solo el número 0013-00089890 si es posible)\n\n"
        "2. ARTICULOS: Extrae cada línea de artículo o servicio facturado.\n\n"
        "Responde ESTRICTAMENTE con un solo objeto JSON sin formato markdown extra (` ```json ` no). "
        "El JSON debe tener exactamente esta estructura:\n"
        "{\n"
        '  "encabezado": [\n'
        '    {"campo": "Proveedor", "valor": "Acme S.A.", "confianza": "98 %", "estado": "success"}\n'
        '  ],\n'
        '  "articulos": [\n'
        '    {"codigo": "001", "descripcion": "Servicio X", "cantidad": "2", "importe": "1500.00"}\n'
        '  ]\n'
        "}\n"
        "Para el encabezado, 'estado' solo puede ser 'success', 'warning' o 'error'. "
        "Si no encuentras el valor en el encabezado, pon valor vacío ('') y estado 'error'."
    )

    uploaded_file = None
    try:
        # 1. Subir archivo a la API de Files (soporta PDF nativo, PNG, JPG, etc.)
        uploaded_file = client.files.upload(file=filepath)
        
        # 2. Esperar procesamiento (necesario en PDFs por ejemplo)
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(1)
            uploaded_file = client.files.get(name=uploaded_file.name)
            
        if uploaded_file.state.name == "FAILED":
             raise RuntimeError("Fallo procesando el documento en la API de Gemini.")

        # 3. Pedir la inferencia usando gemini-2.5-flash
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[uploaded_file, prompt]
        )
        
        # 4. Parsear respuesta (limpieza de posibles backticks de markdown)
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
            
        data = json.loads(raw_text.strip())
        
        # Parse header
        header_data = data.get("encabezado", [])
        header_results = []
        for item in header_data:
            header_results.append((
                item.get("campo", "Desconocido"),
                str(item.get("valor", "")),
                str(item.get("confianza", "0 %")),
                item.get("estado", "error")
            ))
            
        # Parse items
        items_data = data.get("articulos", [])
        items_results = []
        for i in items_data:
            items_results.append((
                str(i.get("codigo", "-")),
                str(i.get("descripcion", "-")),
                str(i.get("cantidad", "1")),
                str(i.get("importe", "0.00"))
            ))
            
        return header_results, items_results

    finally:
        # 5. Limpiar archivo del lado del servidor para no acumular basura
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass
