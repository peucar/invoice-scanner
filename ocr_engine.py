import cv2
import easyocr
import numpy as np
import re
import json
import torch

# Limit PyTorch to 2 threads to prevent 100% CPU starvation on low-spec machines
torch.set_num_threads(2)

class InvoiceOCREngine:
    def __init__(self, languages=['es']):
        # Initialize EasyOCR reader. GPU=False for local CPU compliance.
        self.reader = easyocr.Reader(languages, gpu=False)

    def preprocess_image(self, image_path):
        """Scale and enhance contrast for optimal OCR speed and accuracy."""
        import time
        t0 = time.time()
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"No se pudo cargar la imagen: {image_path}")

        h, w = img.shape[:2]
        # Target width 1500px for balance between speed and detail
        target_w = 1500
        scale = target_w / w
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
        
        print(f"[OCR-ENGINE] Imagen redimensionada a: {img.shape[1]}x{img.shape[0]} (Escala: {scale:.2f})")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        res = clahe.apply(gray)
        print(f"[OCR-ENGINE] Pre-procesamiento completado en {time.time()-t0:.2f}s")
        return res

    def get_ocr_results(self, image):
        return self.reader.readtext(image)

    def group_by_rows(self, ocr_results, y_tolerance=12):
        """Groups text boxes into rows based on vertical proximity."""
        sorted_results = sorted(ocr_results, key=lambda x: x[0][0][1])
        rows = []
        if not sorted_results: return rows

        current_row = [sorted_results[0]]
        # Lock the row reference Y to the first element to prevent slant-drifting
        first_item = sorted_results[0]
        row_y = (first_item[0][0][1] + first_item[0][2][1]) / 2
        
        for i in range(1, len(sorted_results)):
            curr_item = sorted_results[i]
            curr_y = (curr_item[0][0][1] + curr_item[0][2][1]) / 2

            if abs(curr_y - row_y) <= y_tolerance:
                current_row.append(curr_item)
            else:
                rows.append(sorted(current_row, key=lambda x: x[0][0][0]))
                current_row = [curr_item]
                row_y = curr_y
                
        if current_row: rows.append(sorted(current_row, key=lambda x: x[0][0][0]))
        return rows

    def clean_number(self, text):
        """Converts noisy OCR text to float, mapping common errors (O->0, S->5, etc)."""
        if not text: return 0.0
        text = text.upper().strip()
        # Remove thousands separators (dots) if followed by comma decimal
        if '.' in text and ',' in text:
            if text.find('.') < text.find(','):
                text = text.replace('.', '')

        mapping = {
            'O': '0', 'I': '1', 'L': '1', 'J': '1', ';': '1',
            'S': '5', 'B': '8', 'Z': '2', 'G': '6',
            'C': '6', '/': '7', 'U': '0', 'A': '4'
        }
        res = "".join([mapping.get(c, c) for c in text if c in mapping or c in "0123456789.,-"])
        if not res: return 0.0
        if ',' in res:
            res = res.replace('.', '').replace(',', '.')
        
        # Final sanitization: only one dot allowed
        if res.count('.') > 1:
            parts = res.split('.')
            res = "".join(parts[:-1]) + "." + parts[-1]

        try:
            return float(res)
        except:
            filtered = re.sub(r'[^0-9.]', '', res)
            try: return float(filtered)
            except: return 0.0

    def parse_invoice(self, rows):
        """Extracts header, items and total from grouped rows."""
        vendor, fecha, nro_factura, cuit = "Albens S.A.", None, None, None
        items, total = [], 0.0
        raw_lines = [" ".join([it[1] for it in row]) for row in rows]
        full_text = "\n".join(raw_lines)

        # Improved vendor detection
        if "ALBENS" in full_text.upper(): 
            vendor = "Albens S.A."
        elif "PEUGEOT" in full_text.upper() or "CITROEN" in full_text.upper():
            # Potential other vendors, but default to Albens if nothing else matches
            pass

        cuit_m = re.search(r'(\d{2}[-.\s]*\d{8}[-.\s]*\d{1})', full_text)
        if cuit_m: cuit = cuit_m.group(1)
        date_m = re.search(r'(\d{2}[/7]\d{2}[/7]\d{4})', full_text)
        if date_m: fecha = date_m.group(1).replace('7', '/')
        nro_m = re.search(r'(\d[0-9JBI]{3}-\d[0-9JBI]{7})', full_text, re.I)
        if nro_m: nro_factura = nro_m.group(1).translate(str.maketrans('JIB', '118'))

        table_started = (vendor == "Albens S.A.") # Greedy search for Albens
        for row in rows:
            line_text = " ".join([it[1] for it in row]).upper()
            if not table_started:
                if any(k in line_text for k in ["DESCRIP", "IMPORTE", "CANT", "UNIT"]): table_started = True
                continue
            
            clean_row = [it[1] for it in row if len(it[1].strip()) >= 1]
            
            # Skip noise or small fragments
            if len(clean_row) < 2: continue

            # Filtrar líneas de pie de página
            if any(k in line_text for k in ["TOTAL", "SUBTOTAL", "PESOS", "CAE", "VTO", "PAGINA", "SON:"]):
                if "TOTAL" in line_text:
                    m = re.findall(r'[\d.,COIJSBZ/]{4,}', line_text)
                    if m: total = max(total, self.clean_number(m[-1]))
                # If we hit CAE or SON, we definitely finished the table
                if any(k in line_text for k in ["CAE", "SON:", "VTO"]):
                    table_started = False
                continue

            # Albens specific logic: CODE | DESC | ... | QTY | UNIT | TOTAL
            is_albens = (vendor == "Albens S.A.")
            min_cols = 3 if is_albens else 4
            
            if len(clean_row) >= min_cols:
                try:
                    codigo = clean_row[0].strip()
                    
                    # ALBENS FIX: Skip if code looks like a header (all letters and long)
                    if is_albens and codigo.isalpha() and len(codigo) > 5:
                        continue

                    # Identify number indices (potential Qty, Price, etc)
                    num_indices = []
                    for i, v in enumerate(clean_row):
                        if i == 0: continue
                        # Check if it looks like a number (contains digits or maps to one)
                        v_clean = re.sub(r'[^0-9.,]', '', v)
                        if len(v_clean) > 0 and any(c.isdigit() for c in v_clean):
                            num_indices.append(i)
                    
                    if num_indices:
                        # In Albens, columns are usually towards the end
                        # Cantidad is usually 3-4 positions from right, Total is last
                        imp_idx = num_indices[-1]
                        qty_idx = num_indices[-2] if len(num_indices) >= 2 else num_indices[0]
                        
                        # Description resides between code and the first number
                        desc_start = 1
                        desc_end = num_indices[0]
                        
                        desc_parts = clean_row[desc_start:desc_end]
                        desc = " ".join(desc_parts).strip()
                        
                        # Strip common OCR noise from description
                        desc = re.sub(r'^[R]\s+', '', desc) # Strip leading R
                        
                        qty = self.clean_number(clean_row[qty_idx])
                        imp = self.clean_number(clean_row[imp_idx])

                        # Validation: Albens items usually have a code with at least one digit or specific length
                        # and a reasonable description length
                        if (any(c.isdigit() for c in codigo) or len(codigo) >= 4) and len(desc) > 3:
                            if imp > 0:
                                items.append({"codigo": codigo, "descripcion": desc, "cantidad": qty, "importe": imp})
                except: pass

        if total == 0:
            m = re.findall(r'TOTAL\s*([\d.,COIJSBZ/]{5,})', full_text, re.I)
            if m: total = self.clean_number(m[-1])

        if total == 0:
            m = re.findall(r'TOTAL\s*([\d.,COIJSBZ/]{5,})', full_text, re.I)
            if m: total = self.clean_number(m[-1])

        return {
            "header": {"vendor": vendor, "fecha": fecha, "nro_factura": nro_factura, "cuit": cuit},
            "items": items, "total": total, "full_text": full_text
        }

_cached_engine = None

def prewarm_engine():
    global _cached_engine
    if _cached_engine is None:
        print("[OCR-ENGINE] Pre-cargando modelos (esto puede tardar 1-2 minutos en CPUs lentas)...")
        _cached_engine = InvoiceOCREngine()
        print("[OCR-ENGINE] Modelos cargados y listos.")

def scan_invoice(image_path):
    global _cached_engine
    import time
    t_start = time.time()
    prewarm_engine()
    
    proc = _cached_engine.preprocess_image(image_path)
    
    print(f"[OCR-ENGINE] Extrayendo texto con EasyOCR...")
    t_ocr = time.time()
    res = _cached_engine.get_ocr_results(proc)
    print(f"[OCR-ENGINE] OCR completado en {time.time()-t_ocr:.2f}s")
    
    rows = _cached_engine.group_by_rows(res)
    parsed = _cached_engine.parse_invoice(rows)
    print(f"[OCR-ENGINE] Proceso total completado en {time.time()-t_start:.2f}s")
    return parsed

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(json.dumps(scan_invoice(sys.argv[1]), indent=2))
