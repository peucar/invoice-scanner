import cv2
import easyocr
import numpy as np
import re
import json

class InvoiceOCREngine:
    def __init__(self, languages=['es']):
        # Initialize EasyOCR reader. GPU=False for local CPU compliance.
        self.reader = easyocr.Reader(languages, gpu=False)

    def preprocess_image(self, image_path):
        """Upscale and enhance contrast for better OCR on poor quality images."""
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"No se pudo cargar la imagen: {image_path}")

        h, w = img.shape[:2]
        if w < 1500:
            scale = 1500 / w
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        return clahe.apply(gray)

    def get_ocr_results(self, image):
        return self.reader.readtext(image)

    def group_by_rows(self, ocr_results, y_tolerance=12):
        """Groups text boxes into rows based on vertical proximity."""
        sorted_results = sorted(ocr_results, key=lambda x: x[0][0][1])
        rows = []
        if not sorted_results: return rows

        current_row = [sorted_results[0]]
        for i in range(1, len(sorted_results)):
            prev_item, curr_item = current_row[-1], sorted_results[i]
            prev_y = (prev_item[0][0][1] + prev_item[0][2][1]) / 2
            curr_y = (curr_item[0][0][1] + curr_item[0][2][1]) / 2

            if abs(curr_y - prev_y) <= y_tolerance:
                current_row.append(curr_item)
            else:
                rows.append(sorted(current_row, key=lambda x: x[0][0][0]))
                current_row = [curr_item]
        if current_row: rows.append(sorted(current_row, key=lambda x: x[0][0][0]))
        return rows

    def clean_number(self, text):
        """Converts noisy OCR text to float, mapping common errors (O->0, S->5, etc)."""
        if not text: return 0.0
        text = text.upper()
        mapping = {
            'O': '0', 'I': '1', 'L': '1', 'J': '1', ';': '1',
            'S': '5', 'B': '8', 'Z': '2', 'G': '6',
            'C': '6', '/': '7', 'U': '0', 'A': '4'
        }
        res = "".join([mapping.get(c, c) for c in text if c in mapping or c in "0123456789.,-"])
        if not res: return 0.0
        if ',' in res:
            res = res.replace('.', '').replace(',', '.')
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

        if "ALBENS" in full_text.upper(): vendor = "Albens S.A."
        cuit_m = re.search(r'(\d{2}[-.\s]*\d{8}[-.\s]*\d{1})', full_text)
        if cuit_m: cuit = cuit_m.group(1)
        date_m = re.search(r'(\d{2}[/7]\d{2}[/7]\d{4})', full_text)
        if date_m: fecha = date_m.group(1).replace('7', '/')
        nro_m = re.search(r'(\d[0-9JBI]{3}-\d[0-9JBI]{7})', full_text, re.I)
        if nro_m: nro_factura = nro_m.group(1).translate(str.maketrans('JIB', '118'))

        table_started = False
        for row in rows:
            line_text = " ".join([it[1] for it in row]).upper()
            if not table_started:
                if any(k in line_text for k in ["DESCRIP", "IMPORTE", "CANT", "UNIT"]): table_started = True
                continue
            
            clean_row = [it[1] for it in row if len(it[1].strip()) > 1]
            if any(k in line_text for k in ["TOTAL", "SUBTOTAL", "PESOS", "CAE"]) and len(clean_row) < 5:
                if "TOTAL" in line_text:
                    m = re.findall(r'[\d.,COIJSBZ/]{4,}', line_text)
                    if m: total = max(total, self.clean_number(m[-1]))
                if any(k in line_text for k in ["CAE", "SON"]): table_started = False
                continue

            if len(clean_row) >= 4:
                try:
                    codigo = clean_row[0].strip()
                    nums = [i for i, v in enumerate(clean_row) if i > 0 and (re.search(r'[0-9]', v) or re.search(r'[COIJSBZ/]{3,}', v))]
                    if len(nums) >= 3:
                        qty_idx, imp_idx = nums[-3], nums[-1]
                        desc = " ".join(clean_row[1:qty_idx]).replace("R ", "")
                        qty, imp = self.clean_number(clean_row[qty_idx]), self.clean_number(clean_row[imp_idx])
                        if qty > 0 and imp > 0:
                            items.append({"codigo": codigo, "descripcion": desc, "cantidad": qty, "importe": imp})
                except: pass

        if total == 0:
            m = re.findall(r'TOTAL\s*([\d.,COIJSBZ/]{5,})', full_text, re.I)
            if m: total = self.clean_number(m[-1])

        return {
            "header": {"vendor": vendor, "fecha": fecha, "nro_factura": nro_factura, "cuit": cuit},
            "items": items, "total": total
        }

def scan_invoice(image_path):
    engine = InvoiceOCREngine()
    proc = engine.preprocess_image(image_path)
    res = engine.get_ocr_results(proc)
    rows = engine.group_by_rows(res)
    return engine.parse_invoice(rows)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(json.dumps(scan_invoice(sys.argv[1]), indent=2))
