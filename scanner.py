from typing import Dict, Any
import ocr_engine

def scan_invoice(filepath: str, api_key: str = None, status_callback=None) -> Dict[str, Any]:
    """
    Standalone version using local OCR (easyocr).
    Gemini API is no longer used.
    """
    def _status(msg):
        print(f"[SCANNER] {msg}")
        if status_callback:
            status_callback(msg)

    try:
        _status("Iniciando motor de OCR local...")
        # Local OCR might need a moment to load models on CPU
        data = ocr_engine.scan_invoice(filepath)
        
        _status("Mapeando datos extraídos...")
        
        # Map ocr_engine format to the application's expected format
        header = data.get("header", {})
        items = data.get("items", [])
        total = data.get("total", 0.0)
        
        encabezado = []
        if header.get("vendor"):
            encabezado.append({"campo": "Proveedor", "valor": header["vendor"], "confianza": "LocalOCR", "estado": "ok"})
        if header.get("cuit"):
            encabezado.append({"campo": "NIF/CUIT", "valor": header["cuit"], "confianza": "LocalOCR", "estado": "ok"})
        if header.get("nro_factura"):
            encabezado.append({"campo": "Número", "valor": header["nro_factura"], "confianza": "LocalOCR", "estado": "ok"})
        if header.get("fecha"):
            encabezado.append({"campo": "Fecha", "valor": header["fecha"], "confianza": "LocalOCR", "estado": "ok"})
        if total > 0:
            encabezado.append({"campo": "Total", "valor": f"{total:,.2f}", "confianza": "LocalOCR", "estado": "ok"})

        articulos = []
        for it in items:
            articulos.append({
                "codigo": it.get("codigo", ""),
                "descripcion": it.get("descripcion", ""),
                "cantidad": str(it.get("cantidad", "0")),
                "importe": str(it.get("importe", "0"))
            })

        result = {
            "tipo": "FACTURA", # Default to FACTURA for now
            "factura_data": {
                "encabezado": encabezado,
                "articulos": articulos
            }
        }
        
        _status("Escaneo completado localmente.")
        return result

    except Exception as e:
        _status(f"Error en OCR local: {str(e)}")
        raise RuntimeError(f"Fallo el escaneo local: {str(e)}")


