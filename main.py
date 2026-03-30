"""
Peucar App — Main application window
iOS / Pinterest–style desktop invoice scanner

Run:
    python main.py

Dependencies:
    pip install customtkinter pillow
    (optional DnD):  pip install tkinterdnd2
"""

import sys
import os
import time
import threading
import csv
import json
import socket
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk

import theme as T
from components import DropZone, DataTable, SAMPLE_DATA, _bind_hover, OrderCard, FloatingSearchBar
from scanner import scan_invoice
from supabase_manager import SupabaseManager

CONFIG_FILE = "config.json"

def get_persisted_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_persisted_config(data: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

HISTORY_FILE = "history.json"

def load_history() -> dict:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"history": [], "items": {}, "totals": {}}

def save_history(history: list, items: dict, totals: dict):
    try:
        data = {
            "history": history,
            "items": items,
            "totals": totals
        }
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

def normalize_id(id_str: str) -> str:
    """Removes spaces, hyphens, dots and leading zeros to allow better linking."""
    if not id_str: return ""
    # Remove all formatting
    clean = id_str.replace(" ", "").replace("-", "").replace(".", "").replace("/", "").upper()
    # Remove leading zeros if it's primarily numeric
    return clean.lstrip('0')

def sort_invoice_history(history: list) -> list:
    """Sorts invoice history by date (DD/MM/YYYY) descending."""
    from datetime import datetime
    def parse_date(row):
        try:
            return datetime.strptime(row[2], "%d/%m/%Y")
        except Exception:
            return datetime.min
    
    return sorted(history, key=parse_date, reverse=True)

def prepare_grouped_results(history: list) -> list:
    """Groups Remitos under their Facturas while maintaining global chronological order."""
    # 1. Sort all by date descending
    sorted_all = sort_invoice_history(history)
    
    final_list = []
    used_indices = set()
    
    # Helper to check if a remito is linked to ANY factura in history
    def get_parent_factura_idx(rem_doc):
        rem_id_norm = normalize_id(rem_doc[1])
        for idx, doc in enumerate(sorted_all):
            if not doc[5]: # Is Factura
                linked_id = doc[6] if len(doc) > 6 else "-"
                if normalize_id(linked_id) == rem_id_norm or normalize_id(doc[1]) == rem_id_norm:
                    return idx
        return None

    for i, doc in enumerate(sorted_all):
        if i in used_indices:
            continue
            
        is_remito = doc[5]
        
        if not is_remito:
            # It's a Factura: Add it and find its children
            final_list.append((*doc, False))
            used_indices.add(i)
            
            # Find linked remitos (children)
            linked_id = doc[6] if len(doc) > 6 else "-"
            targets = [normalize_id(linked_id), normalize_id(doc[1])]
            
            for j, potential_child in enumerate(sorted_all):
                if j not in used_indices and potential_child[5]: # Unused Remito
                    if any(t != "" and t == normalize_id(potential_child[1]) for t in targets):
                        final_list.append((*potential_child, True))
                        used_indices.add(j)
        else:
            # It's a Remito: Check if it has a parent factura somewhere
            if get_parent_factura_idx(doc) is not None:
                # If it has a parent, we skip it here; it will be added when the parent is processed
                continue
            else:
                # Standalone Remito: Add it in its chronological place
                final_list.append((*doc, False))
                used_indices.add(i)
            
    return final_list

# ── CustomTkinter global setup ────────────────────────────────────────────────
ctk.set_appearance_mode("system")  # Permite oscuredcer/aclarar según el OS o manualmente
ctk.set_default_color_theme("blue")


# ─────────────────────────────────────────────────────────────────────────────
# Top bar (Appears inside views now)
# ─────────────────────────────────────────────────────────────────────────────

class TopBar(ctk.CTkFrame):
    def __init__(self, parent, title="⚡ Peucar App", subtitle="", **kw):
        super().__init__(
            parent,
            height=60,
            corner_radius=0,
            fg_color=T.BG_CARD,
            border_width=0,
            **kw,
        )
        self.grid_propagate(False)
        self.grid_columnconfigure(1, weight=1)

        # Logo pill
        logo_pill = ctk.CTkFrame(
            self,
            corner_radius=T.RADIUS_SM,
            fg_color=T.ACCENT,
            border_width=0,
        )
        logo_pill.grid(row=0, column=0, padx=(T.PAD_OUTER, 10), pady=12)
        ctk.CTkLabel(
            logo_pill,
            text=f"  {title}  ",
            font=(T.FONT_FALLBACK, 14, "bold"),
            text_color="#FFFFFF",
        ).grid(row=0, column=0, padx=4, pady=4)

        # Subtitle
        ctk.CTkLabel(
            self,
            text=subtitle,
            font=T.FONT_SMALL,
            text_color=T.TEXT_TERTIARY,
        ).grid(row=0, column=1, sticky="w")

        # Right cluster: version badge
        ver_frame = ctk.CTkFrame(self, fg_color=T.BG_APP, corner_radius=T.RADIUS_SM, border_width=0)
        ver_frame.grid(row=0, column=2, padx=(0, T.PAD_OUTER), pady=14)
        ctk.CTkLabel(
            ver_frame,
            text="  v 2.0  ",
            font=T.FONT_MICRO,
            text_color=T.TEXT_TERTIARY,
        ).grid(row=0, column=0, padx=6, pady=3)

        # Bottom divider
        ctk.CTkFrame(self, height=1, fg_color=T.BORDER, corner_radius=0).grid(
            row=1, column=0, columnspan=3, sticky="ew"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Top Upload Panel
# ─────────────────────────────────────────────────────────────────────────────

class TopUploadPanel(ctk.CTkFrame):
    def __init__(self, parent, on_scan_click, **kw):
        super().__init__(
            parent,
            corner_radius=T.RADIUS_LG,
            fg_color=T.BG_CARD,
            border_color=T.BORDER,
            border_width=1,
            **kw,
        )
        self.on_scan_click = on_scan_click
        self.filepaths = []
        self._build()
        self._bind_drag_events()

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Icon box
        self._icon_box = ctk.CTkFrame(self, fg_color=T.BG_APP, corner_radius=T.RADIUS_SM, border_width=0, width=50, height=50)
        self._icon_box.grid(row=0, column=0, padx=(15, 10), pady=15)
        self._icon_box.grid_propagate(False)
        self._icon_box.grid_rowconfigure(0, weight=1)
        self._icon_box.grid_columnconfigure(0, weight=1)

        self._icon_lbl = ctk.CTkLabel(self._icon_box, text="📥", font=(T.FONT_FALLBACK, 24))
        self._icon_lbl.grid(row=0, column=0)

        # Texts
        text_frame = ctk.CTkFrame(self, fg_color="transparent")
        text_frame.grid(row=0, column=1, sticky="w")
        
        self._title_lbl = ctk.CTkLabel(text_frame, text="Subir imagen de factura", font=T.FONT_H2, text_color=T.TEXT_PRIMARY)
        self._title_lbl.pack(anchor="w", pady=(0, 2))
        
        self._sub_lbl = ctk.CTkLabel(text_frame, text="Arrastra un archivo aquí (.pdf, .png, .jpg) o haz clic para abrir tu disco.", font=T.FONT_BODY, text_color=T.TEXT_TERTIARY)
        self._sub_lbl.pack(anchor="w")

        # Main Button
        self.scan_btn = ctk.CTkButton(
            self,
            text="Escanear y registrar",
            font=T.FONT_BTN,
            height=40,
            fg_color=T.ACCENT,
            hover_color=T.ACCENT_HOVER,
            text_color=T.ACCENT_TEXT,
            corner_radius=T.RADIUS_MD,
            command=self._on_scan,
        )
        self.scan_btn.grid(row=0, column=2, padx=15, pady=15)

        # Make entire left part clickable
        for w in [self, self._icon_box, self._icon_lbl, text_frame, self._title_lbl, self._sub_lbl]:
            w.bind("<Button-1>", self._open_dialog)

    # ── Drag and Drop ─────────────────────────────────────────────────────────

    def _bind_drag_events(self):
        try:
            self.drop_target_register("DND_Files")
            self.dnd_bind("<<Drop>>", self._on_drop)
            self.dnd_bind("<<DragEnter>>", self._on_drag_enter)
            self.dnd_bind("<<DragLeave>>", self._on_drag_leave)
        except Exception:
            pass

    def _on_drag_enter(self, event=None):
        self.configure(border_color=T.ACCENT, border_width=2)
        
    def _on_drag_leave(self, event=None):
        self.configure(border_color=T.BORDER, border_width=1)

    def _on_drop(self, event):
        self._on_drag_leave()
        path = event.data.strip().strip("{}")
        self._load_file(path)

    def _open_dialog(self, event=None):
        paths = filedialog.askopenfilenames(
            title="Seleccionar facturas",
            filetypes=[("Facturas", "*.pdf *.png *.jpg *.jpeg *.tiff *.bmp")]
        )
        if paths:
            self._load_files(list(paths))

    def _load_files(self, paths: list):
        valid_paths = []
        for p in paths:
            ext = os.path.splitext(p)[1].lower()
            if ext in {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
                valid_paths.append(p)
        
        if not valid_paths:
            return
            
        self.filepaths = valid_paths
        count = len(valid_paths)
        
        if count == 1:
            basename = os.path.basename(valid_paths[0])
            self._title_lbl.configure(text=f"📄 {basename[:50]}", text_color=T.SUCCESS)
            self._sub_lbl.configure(text="Listo para escanear.")
        else:
            self._title_lbl.configure(text=f"📦 {count} archivos seleccionados", text_color=T.SUCCESS)
            self._sub_lbl.configure(text="Pulse 'Escanear' para procesar el lote.")

        self._icon_lbl.configure(text="✅" if count == 1 else "🗂️")

    def _on_scan(self):
        if callable(self.on_scan_click):
            self.on_scan_click()


# ─────────────────────────────────────────────────────────────────────────────
# Bottom Table Panel
# ─────────────────────────────────────────────────────────────────────────────

class BottomTablePanel(ctk.CTkFrame):
    def __init__(self, parent, on_delete_click=None, **kw):
        super().__init__(
            parent,
            corner_radius=T.RADIUS_MD,
            fg_color=T.BG_CARD,
            border_color=T.BORDER,
            border_width=1,
            **kw,
        )
        self.on_delete_click = on_delete_click
        self._build()

    def _build(self):
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header row ────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0, border_width=0)
        hdr.grid(row=0, column=0, sticky="ew", padx=T.PAD_INNER, pady=(T.PAD_INNER, 0))
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr, text="Historial de Facturas",
            font=T.FONT_H2, text_color=T.TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            hdr,
            text="Facturas escaneadas y persistidas",
            font=T.FONT_SMALL,
            text_color=T.TEXT_TERTIARY,
        ).grid(row=1, column=0, sticky="w", pady=(1, 0))

        # ── Toolbar ───────────────────────────────────────────────────────
        toolbar = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0, border_width=0)
        toolbar.grid(row=1, column=0, sticky="ew", padx=T.PAD_INNER, pady=(10, 6))

        # Export button (secondary style)
        export_btn = ctk.CTkButton(
            toolbar,
            text="⬆  Exportar CSV",
            font=T.FONT_SMALL,
            height=32,
            width=130,
            corner_radius=T.RADIUS_MD,
            fg_color=T.BG_APP,
            hover_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY,
            border_color=T.BORDER,
            border_width=1,
            command=self._on_export_csv,
        )
        export_btn.grid(row=0, column=0, padx=(0, 8))

        copy_btn = ctk.CTkButton(
            toolbar,
            text="⎘  Copiar",
            font=T.FONT_SMALL,
            height=32,
            width=100,
            corner_radius=T.RADIUS_MD,
            fg_color=T.BG_APP,
            hover_color=T.BG_HOVER,
            text_color=T.TEXT_PRIMARY,
            border_color=T.BORDER,
            border_width=1,
            command=self._on_copy_clipboard,
        )
        copy_btn.grid(row=0, column=1)

        # Row count label (right-aligned)
        toolbar.grid_columnconfigure(2, weight=1)
        self._row_count_lbl = ctk.CTkLabel(
            toolbar,
            text="0 facturas",
            font=T.FONT_SMALL,
            text_color=T.TEXT_TERTIARY,
        )
        self._row_count_lbl.grid(row=0, column=2, sticky="e")

        # ── Table ─────────────────────────────────────────────────────────
        self.table = DataTable(self, on_delete_click=self.on_delete_click)
        self.table.grid(
            row=2, column=0, sticky="nsew",
            padx=T.PAD_INNER, pady=(0, T.PAD_INNER),
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def load_results(self, data: list):
        # data is the clean history (6-element tuples)
        # We prepare the grouped/flagged version for the UI table
        ui_data = prepare_grouped_results(data)
        self.table.load_data(ui_data)
        self._row_count_lbl.configure(text=f"{len(data)} documentos")

    def clear_results(self):
        self.table.clear()
        self._row_count_lbl.configure(text="0 facturas")

    # ── Button Handlers ───────────────────────────────────────────────────────

    def _on_export_csv(self):
        if not self.table.data: return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            title="Exportar datos a CSV"
        )
        if not path: return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                # Data columns: prov, nro, fec, monto, estado, is_remito
                writer.writerow(["Proveedor", "ID Remito/Fac", "Fecha", "Monto", "Estado"])
                # Only write first 5 columns (exclude internal is_remito flag)
                writer.writerows([r[:5] for r in self.table.data])
        except Exception as e:
            print(f"Error escribiendo CSV: {e}")

    def _on_copy_clipboard(self):
        if not self.table.data: return
        # Copy basic ID, Provider and Status info
        text = "Proveedor\tID\tEstado\n" + "\n".join(f"{row[0]}\t{row[1]}\t{row[4]}" for row in self.table.data)
        self.clipboard_clear()
        self.clipboard_append(text)


# ─────────────────────────────────────────────────────────────────────────────
# Progress overlay
# ─────────────────────────────────────────────────────────────────────────────

class ScanOverlay(ctk.CTkToplevel):
    """Modal-like progress dialog shown while scanning."""

    def __init__(self, parent):
        super().__init__(parent)
        self.withdraw()
        self.overrideredirect(True)
        self.configure(fg_color=T.BG_CARD)

        # Center over parent
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = 340, 200
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.resizable(False, False)
        self.transient(parent) # Vincula la ventana al padre sin forzarla al frente de otras apps
        self.lift()

        inner = ctk.CTkFrame(self, corner_radius=T.RADIUS_MD, fg_color=T.BG_CARD,
                              border_color=T.BORDER, border_width=1)
        inner.place(relx=0, rely=0, relwidth=1, relheight=1)

        self._spinner_lbl = ctk.CTkLabel(inner, text="⏳", font=(T.FONT_FALLBACK, 36))
        self._spinner_lbl.pack(pady=(32, 8))

        self._status_lbl = ctk.CTkLabel(
            inner,
            text="Inicializando…",
            font=T.FONT_H3,
            text_color=T.TEXT_PRIMARY,
        )
        self._status_lbl.pack()

        ctk.CTkLabel(
            inner, text="Esto tomará solo un momento",
            font=T.FONT_SMALL, text_color=T.TEXT_TERTIARY,
        ).pack(pady=(4, 0))

        self.bar = ctk.CTkProgressBar(inner, mode="indeterminate",
                                      progress_color=T.ACCENT,
                                      height=4, corner_radius=2)
        self.bar.pack(fill="x", padx=32, pady=16)
        self.bar.start()

    def set_status(self, text: str):
        self._status_lbl.configure(text=text)

        self.show()

    def show(self):
        self.deiconify()
        self.lift()

    def hide(self):
        self.bar.stop()
        self.withdraw()


# ─────────────────────────────────────────────────────────────────────────────
# Invoice Details Modal
# ─────────────────────────────────────────────────────────────────────────────

class InvoiceDetailsTopLevel(ctk.CTkToplevel):
    """Floating modal to display the individual line items of a specific scanned invoice."""

    def __init__(self, parent, invoice_number: str, items_data: list, subtotal: str = "-", total: str = "-"):
        super().__init__(parent)
        self.title("Detalle de Factura")
        self.transient(parent)  # Stay on top of main window
        self.configure(fg_color=T.BG_APP)

        # Center over parent
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = 600, 400
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(500, 300)

        # Main container card
        content = ctk.CTkFrame(self, fg_color=T.BG_CARD, corner_radius=T.RADIUS_LG, border_width=1, border_color=T.BORDER)
        content.pack(fill="both", expand=True, padx=20, pady=20)

        # 1. Header (Sticky at Top)
        hdr = ctk.CTkFrame(content, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(
            hdr, 
            text=f"Detalle de Factura #{invoice_number}", 
            font=T.FONT_H2, 
            text_color=T.TEXT_PRIMARY
        ).pack(side="left")

        # 2. Footer (Sticky at Bottom)
        ftr = ctk.CTkFrame(content, fg_color="transparent")
        ftr.pack(fill="x", side="bottom", padx=20, pady=(0, 20))
        
        ctk.CTkButton(
            ftr, 
            text="Cerrar", 
            font=T.FONT_BTN, 
            width=100, height=36,
            fg_color=T.BG_APP, hover_color=T.BG_HOVER, 
            text_color=T.TEXT_PRIMARY,
            border_width=1, border_color=T.BORDER,
            command=self.destroy
        ).pack(side="right")

        # 3. Totals Section (Sticky above Footer)
        totals_frame = ctk.CTkFrame(content, fg_color="transparent")
        totals_frame.pack(fill="x", side="bottom", padx=40, pady=(0, 10))
        
        # Subtotal Row
        sub_f = ctk.CTkFrame(totals_frame, fg_color="transparent")
        sub_f.pack(fill="x")
        ctk.CTkLabel(sub_f, text="Subtotal:", font=T.FONT_BODY, text_color=T.TEXT_SECONDARY).pack(side="left")
        ctk.CTkLabel(sub_f, text=subtotal, font=T.FONT_BODY, text_color=T.TEXT_PRIMARY).pack(side="right")
        
        # Total Row (Bold)
        tot_f = ctk.CTkFrame(totals_frame, fg_color="transparent")
        tot_f.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(tot_f, text="TOTAL:", font=T.FONT_H3, text_color=T.TEXT_PRIMARY).pack(side="left")
        ctk.CTkLabel(tot_f, text=total, font=(T.FONT_FALLBACK, 15, "bold"), text_color=T.ACCENT).pack(side="right")

        # 4. Items Table (Fill remains space, Scrollable)
        table_columns = [
            ("Código",      80),
            ("Descripción", 200),
            ("Cantidad",    80),
            ("Importe",     100),
        ]
        
        table_frame = ctk.CTkFrame(content, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        self.table = DataTable(table_frame, columns=table_columns, data=items_data)
        self.table.grid(row=0, column=0, sticky="nsew")
        
        self.grab_set() # Focus lock


# ─────────────────────────────────────────────────────────────────────────────
# Vista 1: Ingreso (Escáner Actual)
# ─────────────────────────────────────────────────────────────────────────────

class OrderEditDialog(ctk.CTkToplevel):
    """Dialog to edit an existing order's header and items."""
    def __init__(self, parent, order_data, on_save):
        super().__init__(parent)
        self.title("Editar Pedido")
        self.transient(parent)
        self.configure(fg_color=T.BG_APP)
        self.order_data = order_data
        self.on_save = on_save

        # Center
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = 500, 600
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        # UI
        content = ctk.CTkFrame(self, fg_color=T.BG_CARD, corner_radius=T.RADIUS_LG, border_width=1, border_color=T.BORDER)
        content.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(content, text="Editar Pedido", font=T.FONT_H2, text_color=T.TEXT_PRIMARY).pack(pady=(20, 10))

        # Date & Provider
        f_hdr = ctk.CTkFrame(content, fg_color="transparent")
        f_hdr.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(f_hdr, text="Fecha:", font=T.FONT_SMALL, text_color=T.TEXT_SECONDARY).pack(side="left")
        self.ent_date = ctk.CTkEntry(f_hdr, font=T.FONT_BODY, fg_color=T.BG_APP, border_color=T.BORDER)
        self.ent_date.pack(side="left", padx=10, fill="x", expand=True)
        self.ent_date.insert(0, order_data['fecha'])

        f_prov = ctk.CTkFrame(content, fg_color="transparent")
        f_prov.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(f_prov, text="Proveedor:", font=T.FONT_SMALL, text_color=T.TEXT_SECONDARY).pack(side="left")
        self.ent_prov = ctk.CTkEntry(f_prov, font=T.FONT_BODY, fg_color=T.BG_APP, border_color=T.BORDER)
        self.ent_prov.pack(side="left", padx=10, fill="x", expand=True)
        self.ent_prov.insert(0, order_data['proveedor'])
        self.ent_prov.bind("<KeyRelease>", lambda e: self._force_upper(self.ent_prov))

        # Items Textbox
        ctk.CTkLabel(content, text="Items (Código X Cantidad):", font=T.FONT_SMALL, text_color=T.TEXT_SECONDARY).pack(anchor="w", padx=20, pady=(15, 5))
        self.txt_items = ctk.CTkTextbox(content, font=(T.FONT_FALLBACK, 12), fg_color=T.BG_APP, border_color=T.BORDER, border_width=1)
        self.txt_items.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Format existing items back to text: "[v] CODE X QTY" or "[ ] CODE X QTY"
        # Item format in storage: (id, codigo, q_pedida, q_entregada)
        items_str = ""
        for _, code, qp, qe in order_data['items']:
            prefix = "[V] " if qe >= qp else "[ ] "
            items_str += f"{prefix}{code} X {int(qp)}\n"
        self.txt_items.insert("1.0", items_str.strip())

        # Prevent merging lines (Backspace at start or Delete at end)
        def _prevent_merge(event):
            idx = self.txt_items.index("insert")
            if event.keysym == "BackSpace":
                if idx.endswith(".0"): return "break"
            elif event.keysym == "Delete":
                if idx == self.txt_items.index("insert lineend"): return "break"
        
        self.txt_items.bind("<BackSpace>", _prevent_merge)
        self.txt_items.bind("<Delete>", _prevent_merge)
        self.txt_items.bind("<Return>", lambda e: self.after(1, self._on_enter_smart))

        # Buttons
        f_btns = ctk.CTkFrame(content, fg_color="transparent")
        f_btns.pack(fill="x", side="bottom", padx=20, pady=20)

        ctk.CTkButton(f_btns, text="Cancelar", command=self.destroy, fg_color="transparent", border_width=1, border_color=T.BORDER, text_color=T.TEXT_PRIMARY).pack(side="right", padx=5)
        ctk.CTkButton(f_btns, text="Tachar Todos", command=self._check_all, fg_color=T.BG_HOVER, text_color=T.TEXT_PRIMARY, border_width=1, border_color=T.BORDER).pack(side="left", padx=5)
        ctk.CTkButton(f_btns, text="Guardar Cambios", command=self._save, fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER).pack(side="right")

    def _force_upper(self, widget):
        val = widget.get()
        pos = widget.index("insert")
        widget.delete(0, "end")
        widget.insert(0, val.upper())
        widget.icursor(pos)

    def _on_enter_smart(self):
        # Auto-brackets on new line if previous line had them
        idx = self.txt_items.index("insert")
        line_num = int(idx.split(".")[0])
        prev_line_idx = f"{line_num - 1}.0"
        prev_content = self.txt_items.get(prev_line_idx, f"{line_num - 1}.end").strip()
        
        if prev_content.startswith("["):
            self.txt_items.insert("insert", "[ ] ")

    def _check_all(self):
        content = self.txt_items.get("1.0", "end")
        new_content = content.replace("[ ]", "[V]")
        self.txt_items.delete("1.0", "end")
        self.txt_items.insert("1.0", new_content.strip())

    def _save(self):
        new_date = self.ent_date.get().strip()
        new_prov = self.ent_prov.get().strip().upper()
        raw_items = self.txt_items.get("1.0", "end").strip().split("\n")
        
        parsed_items = []
        import re
        for line in raw_items:
            if not line.strip(): continue
            is_llegado = "[V]" in line.upper()
            clean_line = line.replace("[v]", "").replace("[V]", "").replace("[ ]", "").strip()

            # Handle "CODE X QTY" or just "CODE"
            if " X " in clean_line.upper():
                parts = re.split(r'\s+[xX]\s+', clean_line, flags=re.IGNORECASE)
                code = parts[0].strip().upper()
                qty = float(re.sub(r'[^\d.]', '', parts[1].split()[0]))
            else:
                code = clean_line.strip().upper()
                qty = 1.0
            
            # De lo contrario, preservamos lo que ya estaba entregado
            old_delivered = qty if is_llegado else 0
            if not is_llegado:
                for _, o_code, o_qp, o_qe in self.order_data['items']:
                    from main import normalize_id
                    if normalize_id(o_code) == normalize_id(code):
                        old_delivered = o_qe
                        break
            
            parsed_items.append((code, qty, old_delivered))
        
        self.on_save(self.order_data['id'], new_date, new_prov, parsed_items)
        self.destroy()

class ScanOverlay(ctk.CTkToplevel):
    """Simple overlay to show scanning status."""
    def __init__(self, parent):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-alpha", 0.8)
        self.configure(fg_color=T.BG_APP)
        self.lbl = ctk.CTkLabel(self, text="Escaneando...", font=T.FONT_H2, text_color=T.TEXT_PRIMARY)
        self.lbl.pack(expand=True, padx=40, pady=40)
        
        # Center on parent
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"{w}x{h}+{px+(pw-w)//2}+{py+(ph-h)//2}")
        
    def set_status(self, text):
        self.lbl.configure(text=text)
        
    def hide(self):
        self.destroy()

class ReviewImportDialog(ctk.CTkToplevel):
    """Dialog to review and edit orders extracted from a PDF/Image before final import."""
    def __init__(self, parent, orders_data, on_confirm):
        super().__init__(parent)
        self.title("Revisar Importación")
        self.transient(parent)
        self.configure(fg_color=T.BG_APP)
        self.orders = orders_data
        self.on_confirm = on_confirm

        # Center
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = 600, 700
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Main Layout
        self.container = ctk.CTkFrame(self, fg_color=T.BG_CARD, corner_radius=T.RADIUS_LG, border_width=1, border_color=T.BORDER)
        self.container.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(self.container, text="Revisar Pedidos Detectados", font=T.FONT_H2, text_color=T.TEXT_PRIMARY).pack(pady=(20, 10))
        ctk.CTkLabel(self.container, text="Verifica la fecha y el proveedor antes de confirmar.", font=T.FONT_SMALL, text_color=T.TEXT_TERTIARY).pack()

        # Scrollable area for orders
        self.scroll = ctk.CTkScrollableFrame(self.container, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=10, pady=15)

        self.order_rows = []
        for i, order in enumerate(self.orders):
            self._add_order_row(order, i)

        # Footer
        f_btns = ctk.CTkFrame(self.container, fg_color="transparent")
        f_btns.pack(fill="x", side="bottom", padx=20, pady=20)

        ctk.CTkButton(f_btns, text="Cancelar", command=self.destroy, fg_color="transparent", border_width=1, border_color=T.BORDER, text_color=T.TEXT_PRIMARY).pack(side="right", padx=5)
        ctk.CTkButton(f_btns, text="Confirmar e Importar", command=self._confirm, fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER).pack(side="right")

    def _add_order_row(self, order, idx):
        row = ctk.CTkFrame(self.scroll, fg_color=T.BG_APP, corner_radius=T.RADIUS_MD, border_width=1, border_color=T.BORDER)
        row.pack(fill="x", pady=5, padx=5)

        # Inputs
        f_inputs = ctk.CTkFrame(row, fg_color="transparent")
        f_inputs.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(f_inputs, text="Fec:", font=T.FONT_SMALL).pack(side="left")
        ent_date = ctk.CTkEntry(f_inputs, font=T.FONT_BODY, width=100)
        ent_date.pack(side="left", padx=5)
        ent_date.insert(0, order.get('fecha', ''))

        ctk.CTkLabel(f_inputs, text="Prov:", font=T.FONT_SMALL).pack(side="left", padx=(10, 0))
        ent_prov = ctk.CTkEntry(f_inputs, font=T.FONT_BODY)
        ent_prov.pack(side="left", padx=5, fill="x", expand=True)
        ent_prov.insert(0, order.get('proveedor', ''))
        ent_prov.bind("<KeyRelease>", lambda e, w=ent_prov: self._force_upper(w))

        # Items Preview (Summary)
        items = order.get('articulos', [])
        summary = f"{len(items)} artículos detectados"
        ctk.CTkLabel(row, text=summary, font=T.FONT_MICRO, text_color=T.TEXT_TERTIARY).pack(anchor="w", padx=15, pady=(0, 10))

        self.order_rows.append({'date_ent': ent_date, 'prov_ent': ent_prov, 'articulos': items})

    def _force_upper(self, widget):
        val = widget.get()
        pos = widget.index("insert")
        widget.delete(0, "end")
        widget.insert(0, val.upper())
        widget.icursor(pos)

    def _confirm(self):
        final_orders = []
        for row in self.order_rows:
            final_orders.append({
                'fecha': row['date_ent'].get(),
                'proveedor': row['prov_ent'].get().upper(),
                'articulos': row['articulos']
            })
        self.on_confirm(final_orders)
        self.destroy()

class OrdersView(ctk.CTkFrame):
    def __init__(self, parent, db_manager: OrdersManager, **kw):
        super().__init__(parent, fg_color="transparent", corner_radius=0, **kw)
        self.db = db_manager
        self._build()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.top_bar = TopBar(self, title="📦 Gestión de Pedidos", subtitle="Control de recepción")
        self.top_bar.grid(row=0, column=0, sticky="ew")

        # Main splitter: Left (entry) | Right (cards)
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=T.PAD_OUTER, pady=T.PAD_OUTER)
        content.grid_columnconfigure(0, weight=0, minsize=300) # Input side
        content.grid_columnconfigure(1, weight=1) # List side
        content.grid_rowconfigure(0, weight=1)

        # ── Left: Note Entry ───────────────────
        entry_card = ctk.CTkFrame(content, fg_color=T.BG_CARD, corner_radius=T.RADIUS_LG, border_width=1, border_color=T.BORDER)
        entry_card.grid(row=0, column=0, sticky="nsew", padx=(0, 15))
        
        ctk.CTkLabel(entry_card, text="Cargar Nueva Nota", font=T.FONT_H3, text_color=T.TEXT_PRIMARY).pack(padx=20, pady=(20, 5), anchor="w")

        # ── Proveedor + Fecha row ──────────────
        f_meta = ctk.CTkFrame(entry_card, fg_color="transparent")
        f_meta.pack(fill="x", padx=20, pady=(0, 5))
        f_meta.grid_columnconfigure(0, weight=1)
        f_meta.grid_columnconfigure(1, weight=0)

        prov_frame = ctk.CTkFrame(f_meta, fg_color="transparent")
        prov_frame.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkLabel(prov_frame, text="Proveedor", font=T.FONT_MICRO, text_color=T.TEXT_TERTIARY).pack(anchor="w")
        self.ent_prov = ctk.CTkEntry(prov_frame, font=T.FONT_BODY, fg_color=T.BG_APP, border_color=T.BORDER, placeholder_text="Ej: DM")
        self.ent_prov.pack(fill="x")
        self.ent_prov.bind("<KeyRelease>", lambda e: self._force_upper(self.ent_prov))

        fecha_frame = ctk.CTkFrame(f_meta, fg_color="transparent")
        fecha_frame.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(fecha_frame, text="Fecha", font=T.FONT_MICRO, text_color=T.TEXT_TERTIARY).pack(anchor="w")
        self.ent_date = ctk.CTkEntry(fecha_frame, font=T.FONT_BODY, fg_color=T.BG_APP, border_color=T.BORDER, width=110)
        self.ent_date.pack()
        from datetime import date as _date
        self.ent_date.insert(0, _date.today().strftime("%d/%m/%Y"))

        ctk.CTkLabel(entry_card, text="Artículos (Código X Cantidad):", font=T.FONT_SMALL, text_color=T.TEXT_TERTIARY).pack(padx=20, anchor="w")
        
        self.text_input = ctk.CTkTextbox(entry_card, font=(T.FONT_FALLBACK, 12), fg_color=T.BG_APP, border_width=1, border_color=T.BORDER)
        self.text_input.pack(fill="both", expand=True, padx=20, pady=10)
        self.text_input.bind("<Return>", lambda e: self.after(1, self._on_enter_smart))
        
        f_actions = ctk.CTkFrame(entry_card, fg_color="transparent")
        f_actions.pack(fill="x", padx=20, pady=(0, 20))

        btn_parse = ctk.CTkButton(f_actions, text="Procesar Nota", font=T.FONT_BTN, fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, command=self._on_parse)
        btn_parse.pack(side="left", fill="x", expand=True, padx=(0, 5))

        btn_import = ctk.CTkButton(f_actions, text="Importar PDF", font=T.FONT_BTN, fg_color=T.BG_APP, hover_color=T.BG_HOVER, text_color=T.TEXT_PRIMARY, border_width=1, border_color=T.BORDER, command=self._on_import_pdf)
        btn_import.pack(side="left", fill="x", expand=True)

        # ── Right: Orders Scroll ────────────────
        self.scroll = ctk.CTkScrollableFrame(content, fg_color="transparent", corner_radius=0)
        self.scroll.grid(row=0, column=1, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)

        self.refresh_list()

    def refresh_data(self):
        """Standard method for F5 refresh."""
        self.refresh_list()

    def refresh_list(self):
        for widget in self.scroll.winfo_children():
            widget.destroy()
        
        self.orders = self.db.get_orders()
        self._all_cards = []
        for i, order in enumerate(self.orders):
            card = OrderCard(self.scroll, order, on_delete=self._delete_order, on_edit=self._open_edit_dialog)
            card.pack(fill="x", pady=(0, 15))
            self._all_cards.append(card)

    def _open_edit_dialog(self, order_data):
        OrderEditDialog(self, order_data, on_save=self._save_order_edit)

    def _save_order_edit(self, order_id, date, prov, items):
        try:
            self.db.update_order(order_id, date, prov, items)
            self.refresh_list()
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"No se pudo actualizar el pedido: {e}")

    def on_search(self, text):
        """Filters order cards based on provider, date or item codes. Returns (current_match_idx+1, total_matches)."""
        self._search_text = text
        self._match_indices = []
        self._current_match_ptr = -1
        
        if not text:
            for card in self._all_cards: card.pack(fill="x", pady=(0, 15))
            return 0, 0

        t = text.upper()
        for i, card in enumerate(self._all_cards):
            d = card.order_data
            match = (t in d['proveedor'].upper() or 
                     t in d.get('repuesto', '').upper() or
                     t in d['fecha'].upper() or
                     any(t in str(item[1]).upper() for item in d['items']))
            
            card.highlight_matches(text) # Visual Highlight inside card
            
            if match:
                card.pack(fill="x", pady=(0, 15))
                self._match_indices.append(i)
            else:
                card.pack_forget()
        
        if self._match_indices:
            self._current_match_ptr = 0
            self._highlight_match(self._current_match_ptr)
            return 1, len(self._match_indices)
        return 0, 0

    def on_search_nav(self, direction):
        """navigates: 1 for next, -1 for prev."""
        if not self._match_indices: return 0, 0
        
        self._current_match_ptr = (self._current_match_ptr + direction) % len(self._match_indices)
        self._highlight_match(self._current_match_ptr)
        return self._current_match_ptr + 1, len(self._match_indices)

    def _highlight_match(self, ptr):
        idx = self._match_indices[ptr]
        for i, card in enumerate(self._all_cards):
            if i == idx:
                card.configure(border_color=T.ACCENT, border_width=2)
                # Scroll to it
                self.scroll._parent_canvas.yview_moveto(i / len(self._all_cards))
            else:
                card.configure(border_color=T.BORDER, border_width=1)

    def _delete_order(self, order_id):
        from tkinter import messagebox
        if messagebox.askyesno("Confirmar", "¿Deseas eliminar este pedido?"):
            self.db.delete_order(order_id)
            self.refresh_list()

    def _force_upper(self, widget):
        val = widget.get()
        pos = widget.index("insert")
        widget.delete(0, "end")
        widget.insert(0, val.upper())
        widget.icursor(pos)

    def _on_enter_smart(self):
        # Auto-brackets on new line if previous line had them
        idx = self.text_input.index("insert")
        line_num = int(idx.split(".")[0])
        prev_line_idx = f"{line_num - 1}.0"
        prev_content = self.text_input.get(prev_line_idx, f"{line_num - 1}.end").strip()
        
        if prev_content.startswith("["):
            self.text_input.insert("insert", "[ ] ")
            self.text_input.see("end")

    def _on_parse(self):
        raw_text = self.text_input.get("1.0", "end").strip()
        if not raw_text: return
        
        # Read manual override fields
        manual_prov = self.ent_prov.get().strip().upper()
        manual_date = self.ent_date.get().strip()
        from datetime import date as _date
        if not manual_date:
            manual_date = _date.today().strftime("%d/%m/%Y")
        
        try:
            import re
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            item_pattern = r'(.+?)\s+[xX]\s+([\d.]+)'

            # If provider is manually set -> create a single order with all items
            if manual_prov:
                items = []
                for line in lines:
                    is_llegado = "[V]" in line.upper()
                    clean_line = line.replace("[v]", "").replace("[V]", "").replace("[ ]", "").strip()
                    
                    m = re.search(item_pattern, clean_line, re.IGNORECASE)
                    if m:
                        code = m.group(1).strip().upper()
                        count = float(m.group(2))
                    else:
                        code = clean_line.strip().upper()
                        count = 1.0
                    
                    # Delivered count logic
                    qe = count if is_llegado else 0
                    # DM formatter
                    c_clean = code.replace("/", "")
                    if manual_prov == "DM" and len(c_clean) == 8 and c_clean.isdigit():
                        code = f"{c_clean[:2]}/{c_clean[2:5]}/{c_clean[5:]}"
                    items.append((code, count, qe))
                
                if not items:
                    raise ValueError("No se encontraron artículos en el texto.")
                
                self.db.add_order(manual_date, manual_prov, items)
                self.text_input.delete("1.0", "end")
                self.ent_prov.delete(0, "end")
                # Reset date to today
                self.ent_date.delete(0, "end")
                self.ent_date.insert(0, _date.today().strftime("%d/%m/%Y"))
                self.refresh_list()
                return

            # No manual provider => use smart text parsing (multi-order support)
            current_date = manual_date
            current_provider = "ORIGINAL"
            current_items = []
            date_pattern = r'^\d{1,2}/\d{1,2}/\d{2,4}$'
            pedido_pattern = r'Pedido\s+["\']?([^"\']+)["\']?'

            def save_current_order():
                if current_items:
                    self.db.add_order(current_date, current_provider, current_items)
                    return True
                return False

            processed_any = False
            for line in lines:
                if re.match(date_pattern, line):
                    if save_current_order():
                        processed_any = True
                    current_date = line
                    current_items = []
                    current_provider = "ORIGINAL"
                elif re.search(pedido_pattern, line, re.IGNORECASE):
                    if current_items:
                        if save_current_order():
                            processed_any = True
                        current_items = []
                    prov_match = re.search(pedido_pattern, line, re.IGNORECASE)
                    current_provider = prov_match.group(1).strip().upper()
                else:
                    is_llegado = "[V]" in line.upper()
                    clean_line = line.replace("[v]", "").replace("[V]", "").replace("[ ]", "").strip()

                    m = re.search(item_pattern, clean_line, re.IGNORECASE)
                    if m:
                        code = m.group(1).strip().upper()
                        count = float(m.group(2))
                    else:
                        code = clean_line.strip().upper()
                        count = 1.0
                    
                    qe = count if is_llegado else 0
                    c_clean = code.replace("/", "")
                    if current_provider == "DM" and len(c_clean) == 8 and c_clean.isdigit():
                        code = f"{c_clean[:2]}/{c_clean[2:5]}/{c_clean[5:]}"
                    current_items.append((code, count, qe))
            
            if save_current_order():
                processed_any = True
            
            if processed_any:
                self.text_input.delete("1.0", "end")
                self.refresh_list()
            else:
                raise ValueError("No se encontraron pedidos válidos en el texto.")
                
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error de Formato", f"No se pudo procesar la nota.\nDetalle: {e}")

    def _on_import_pdf(self):
        config = get_persisted_config()
        api_key = config.get("GEMINI_API_KEY")
        if not api_key:
            from tkinter import messagebox
            messagebox.showwarning("Configuración", "Por favor, configura tu API Key de Gemini primero.")
            return

        path = filedialog.askopenfilename(
            title="Seleccionar documento de pedido",
            filetypes=[("Documentos", "*.pdf *.png *.jpg *.jpeg *.tiff *.bmp")]
        )
        if not path: return

        def run_inference():
            try:
                # Show overlay
                self.overlay = ScanOverlay(self.winfo_toplevel())
                self.overlay.set_status("Analizando documento...")
                
                def update_status(msg):
                    self.after(0, lambda: self.overlay.set_status(msg) if hasattr(self, 'overlay') else None)
                
                # Import scanner
                from scanner import scan_invoice
                data = scan_invoice(path, api_key, status_callback=update_status)
                print(f"[DEBUG] Respuesta de la IA: tipo={data.get('tipo')}, pedidos={len(data.get('pedidos_data', []))}")
                
                self.after(0, lambda: self._handle_scan_result(data))
            except Exception as e:
                import traceback
                print(f"[ERROR] Importacion fallida: {traceback.format_exc()}")
                err_msg = str(e)
                self.after(0, lambda: self.overlay.hide())
                from tkinter import messagebox
                self.after(0, lambda: messagebox.showerror("Error", f"Error procesando el documento:\n{err_msg}"))

        threading.Thread(target=run_inference, daemon=True).start()

    def _handle_scan_result(self, data):
        self.overlay.hide()
        self.update()
        
        doc_type = data.get('tipo', 'FACTURA')
        print(f"[DEBUG] Tipo detectado: {doc_type}")
        
        if doc_type == 'LISTA_PEDIDOS':
            pedidos_data = data.get('pedidos_data', [])
            print(f"[DEBUG] Pedidos encontrados: {len(pedidos_data)}")
            if not pedidos_data:
                from tkinter import messagebox
                messagebox.showinfo("Scanner", "No se detectaron pedidos en el documento.")
                return
            
            # Show Review Modal
            dlg = ReviewImportDialog(self.winfo_toplevel(), pedidos_data, on_confirm=self._confirm_import)
            dlg.lift()
            dlg.focus_force()
        else:
            # Show what the AI detected so user understands
            from tkinter import messagebox
            enc = data.get('factura_data', {}).get('encabezado', [])
            prov = next((e['valor'] for e in enc if 'proveedor' in e.get('campo','').lower()), '-')
            arts = data.get('factura_data', {}).get('articulos', [])
            messagebox.showinfo(
                "Documento detectado",
                f"Tipo: {doc_type}\nProveedor: {prov}\nArtículos: {len(arts)}\n\nEste documento es una Factura/Remito. Usá el escáner principal para procesarlo."
            )

    def _confirm_import(self, final_orders):
        count = 0
        for order in final_orders:
            items = []
            for art in order['articulos']:
                code = art.get('codigo', '-')
                qp = float(art.get('cantidad', 1) or 1)
                qe = qp if art.get('llegado', False) else 0
                items.append((code, qp, qe))
            
            if items:
                self.db.add_order(order['fecha'], order['proveedor'], items)
                count += 1
        
        self.refresh_list()
        from tkinter import messagebox
        messagebox.showinfo("Importación", f"Se han importado {count} pedidos exitosamente.")

class IngresoView(ctk.CTkFrame):
    def __init__(self, parent, get_api_key_callback, db_manager: OrdersManager = None, **kw):
        super().__init__(parent, fg_color="transparent", corner_radius=0, **kw)
        self.get_api_key = get_api_key_callback
        self.db = db_manager
        self._build()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Top bar
        self.top_bar = TopBar(self, title="⚡ Ingreso de Facturas", subtitle="Escáner inteligente")
        self.top_bar.grid(row=0, column=0, sticky="ew")

        # Main content area
        content = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        content.grid(row=1, column=0, sticky="nsew", padx=T.PAD_OUTER, pady=T.PAD_OUTER)
        content.grid_rowconfigure(0, weight=0)
        content.grid_rowconfigure(1, weight=1)
        content.grid_columnconfigure(0, weight=1)

        # Top panel (drop zone)
        self.top_upload = TopUploadPanel(content, on_scan_click=self._do_scan)
        self.top_upload.grid(row=0, column=0, sticky="ew", pady=(0, T.GAP))

        # Bottom panel (table)
        self.bottom_table = BottomTablePanel(content, on_delete_click=self._on_delete_row)
        self.bottom_table.grid(row=1, column=0, sticky="nsew")
        
        # Make the main history table clickable to show details
        self.bottom_table.table.on_row_click = self._on_row_clicked

        # Track scan count and history
        self._scan_count = 0
        
        self._load_initial_data()

    def _load_initial_data(self):
        # Cargar historial (Supabase o local fallback)
        if self.db and self.db.client:
            hist, items, totals = self.db.get_history()
            data = {"history": hist, "items": items, "totals": totals}
        else:
            data = load_history()
        # Migration: handle different row formats
        raw_history = data.get("history", [])
        temp_history = []
        for r in raw_history:
            if len(r) == 4:
                # prov, nro, fec, monto -> Factura legacy
                temp_history.append([r[0], r[1], r[2], r[3], "Completado", False])
            elif len(r) == 5:
                # prov, nro, fec, monto, is_remito
                is_remito = r[4]
                estado = "Pendiente" if is_remito else "Completado"
                temp_history.append([r[0], r[1], r[2], r[3], estado, is_remito])
            else:
                temp_history.append(list(r))

        # Second pass: Link remitos with existing invoices
        norm_nros = {normalize_id(row[1]) for row in temp_history if not row[5]} # Set of normalized Factura IDs
        for i, row in enumerate(temp_history):
            if row[5] and row[4] == "Pendiente": # Is Remito and Pendiente
                if normalize_id(row[1]) in norm_nros:
                    temp_history[i][4] = "Completado"
        
        self.invoice_history = [tuple(r) for r in temp_history]
        # Now apply the grouping/sorting logic
        self.invoice_history = sort_invoice_history(self.invoice_history)
        self.invoice_items_dict = data.get("items", {})
        self.invoice_totals_dict = data.get("totals", {})
        
        if self.invoice_history:
            self.bottom_table.load_results(self.invoice_history)
        
        self._match_indices = []
        self._current_match_ptr = -1

    def refresh_data(self):
        """Public method to reload everything from disk."""
        self._load_initial_data()

    def on_search(self, text):
        """Filters the DataTable. Returns (current_match_idx+1, total_matches)."""
        self._match_indices = []
        self._current_match_ptr = -1
        
        if not text:
            self.bottom_table.load_results(self.invoice_history)
            return 0, 0
            
        t = text.upper()
        # Data structure for DataTable rows is variable, we check all strings
        self.invoice_matches = []
        for i, row in enumerate(self.invoice_history):
            if any(t in str(cell).upper() for cell in row):
                self.invoice_matches.append(row)
                self._match_indices.append(i)
                
        self.bottom_table.load_results(self.invoice_matches)
        
        if self._match_indices:
            self._current_match_ptr = 0
            self._highlight_match(self._current_match_ptr)
            return 1, len(self._match_indices)
        return 0, 0

    def on_search_nav(self, direction):
        """navigates: 1 for next, -1 for prev."""
        if not self._match_indices: return 0, 0
        
        self._current_match_ptr = (self._current_match_ptr + direction) % len(self._match_indices)
        self._highlight_match(self._current_match_ptr)
        return self._current_match_ptr + 1, len(self._match_indices)

    def _highlight_match(self, ptr):
        # In DataTable, we'll just indicate the result number for now
        # Visual highlighting of rows in DataTable would require more component work
        pass
    def _on_row_clicked(self, row_data):
        nro = row_data[1]  # The invoice number column
        items = self.invoice_items_dict.get(nro, [])
        totals = self.invoice_totals_dict.get(nro, {"subtotal": "-", "total": "-"})
        InvoiceDetailsTopLevel(
            self, 
            invoice_number=nro, 
            items_data=items,
            subtotal=totals["subtotal"],
            total=totals["total"]
        )

    def _on_delete_row(self, row_data):
        from tkinter import messagebox
        # Data is (prov, nro, fec, monto, estado, is_remito, linked_id, is_subrow)
        prov, nro = row_data[0], row_data[1]
        
        if not messagebox.askyesno("Confirmar", f"¿Estás seguro de que deseas eliminar el documento #{nro} de {prov}?"):
            return

        print(f"[DEBUG] Intentando borrar documento: {nro} de {prov}")
        # 1. Encontrar indice en la historia limpia usando el número de documento
        idx = -1
        for i, row in enumerate(self.invoice_history):
            # Normalizamos ambos para comparar por si hay discrepancias de espacios
            if normalize_id(row[1]) == normalize_id(nro):
                idx = i
                break
        
        if idx == -1:
            print(f"[DEBUG] No se encontró el documento {nro} en la historia.")
            return

        print(f"[DEBUG] Borrando índice {idx}")

        # 2. Remover de listas y dicts
        self.invoice_history.pop(idx)
        self.invoice_items_dict.pop(nro, None)
        self.invoice_totals_dict.pop(nro, None)
        
        # 3. Persistir
        if self.db and self.db.client:
            # Supabase delete not currently implemented for history individually, but
            # realistically deleting history should also be synced eventually.
            pass
        
        save_history(self.invoice_history, self.invoice_items_dict, self.invoice_totals_dict)
        
        # 4. Refresh UI
        self.bottom_table.load_results(self.invoice_history)

    def _do_scan(self):
        files = self.top_upload.filepaths
        if not files:
            self._flash_drop_zone()
            return

        api_key = self.get_api_key()
        if not api_key:
            return 

        overlay = ScanOverlay(self)
        overlay.show()
        
        start_t = time.time()

        def _worker():
            try:
                total_files = len(files)
                for i, filepath in enumerate(files):
                    self.after(0, overlay.set_status, f"Escaneando ({i+1}/{total_files})...\n{os.path.basename(filepath)}")
                    
                    # Llamada real bloqueante
                    results_header, results_items = scan_invoice(filepath, api_key)
                    
                    # Actualizar UI y guardar (sincronizado en el hilo principal)
                    self.after(0, self._on_scan_done, None, results_header, results_items, 0)
                
                self.after(0, overlay.hide)
                self.after(0, overlay.destroy)
                # Limpiar seleccion tras exito
                self.top_upload.filepaths = []
                self.after(100, lambda: self.top_upload._title_lbl.configure(text="Subir imágenes de factura", text_color=T.TEXT_PRIMARY))
                self.after(100, lambda: self.top_upload._sub_lbl.configure(text="Arrastra archivos aquí o haz clic para abrir tu disco."))
                self.after(100, lambda: self.top_upload._icon_lbl.configure(text="📥"))
                
            except Exception as e:
                self.after(0, overlay.set_status, f"Error: {e}")
                self.after(0, overlay.bar.stop)
                time.sleep(3)
                self.after(0, overlay.hide)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_scan_done(self, overlay, results_header, results_items, elapsed_s):
        if overlay:
            overlay.hide()
            overlay.destroy()
        self._scan_count += 1

        # Procesar los campos
        prov = "-"
        nro = "-"
        fec = "-"
        monto = "-"
        remito_vinculado = "-"
        
        for k, v, c, s in results_header:
            kl = k.lower()
            if "proveedor" in kl: prov = v
            elif ("número de factura" in kl or "nro" in kl) and nro == "-": nro = v
            elif "fecha de emi" in kl: fec = v 
            elif "total" in kl and "sub" not in kl: 
                monto = v
                total_val = v
            elif "subtotal" in kl:
                subtot = v
            elif "tipo de documento" in kl:
                tipo_doc = v
            elif "remito vinculado" in kl:
                remito_vinculado = v
        
        tipo_doc_low = tipo_doc.lower()
        # Evitar que "Factura con Remito" se marque como Remito
        is_remito = "remito" in tipo_doc_low and "factura" not in tipo_doc_low

        # Mejora: Si el monto está vacío y el proveedor es Albens, silenciar a Remito si no se detectó
        if not is_remito and monto == "" and "ALBENS" in prov.upper():
            is_remito = True

        if is_remito and ("ALBENS" in prov.upper() or prov == "-"):
            prov = "ALBENS" # Normalizamos el nombre para Albens en remitos
            
        if nro == "-":
            nro = f"S/N-{self._scan_count}"
            
        # Facturas siempre son Completado por definición (ya están en mano)
        estado = "Pendiente" if is_remito else "Completado"

        # Lógica de Vinculación: Si es Factura, buscar si existe un remito previo
        if not is_remito:
            # Usar remito_vinculado si se detectó, sino fallback al propio nro
            link_id = remito_vinculado if remito_vinculado != "-" else nro
            target_norm = normalize_id(link_id)
            
            for i, row in enumerate(self.invoice_history):
                # row structure: [prov, nro, fec, monto, estado, is_remito, (opt) linked_id]
                h_is_remito = row[5]
                h_estado = row[4]
                h_nro = row[1]
                
                if h_is_remito and h_estado == "Pendiente" and normalize_id(h_nro) == target_norm:
                    # Vincular y marcar ambos como completados
                    new_row = list(row)
                    new_row[4] = "Completado"
                    self.invoice_history[i] = tuple(new_row)
                    estado = "Completado"
                    break

        # Guardar con 7 elementos: [prov, nro, fec, monto, estado, is_remito, linked_id]
        self.invoice_history.append((prov, nro, fec, monto, estado, is_remito, remito_vinculado))
        self.invoice_history = sort_invoice_history(self.invoice_history)

        self.invoice_items_dict[nro] = results_items
        self.invoice_totals_dict[nro] = {"subtotal": subtot, "total": total_val}
        
        if self.db and self.db.client:
            import json
            self.db.save_history_record((prov, nro, fec, monto, estado, is_remito, link_id), json.dumps(results_items), json.dumps({"subtotal": subtot, "total": total_val}))
            
        save_history(self.invoice_history, self.invoice_items_dict, self.invoice_totals_dict)
        self.bottom_table.load_results(self.invoice_history)

        # NEW: Link with Orders Database
        if self.db:
            for code_raw, desc, q_str, price in results_items:
                try:
                    # Clean quantity (extract numeric part if it has commas/text)
                    import re
                    q_num = float(re.sub(r'[^\d.]', '', q_str.replace(',', '.')))
                    self.db.update_order_status(prov, desc or code_raw, q_num)
                except Exception as e:
                    print(f"[DEBUG] Error updating order status for item {code_raw}: {e}")

    def _flash_drop_zone(self):
        self.top_upload.configure(border_color=T.ERROR)
        self.after(600, lambda: self.top_upload.configure(border_color=T.BORDER))


# ─────────────────────────────────────────────────────────────────────────────
# Vista 2: Configuración
# ─────────────────────────────────────────────────────────────────────────────

class ConfiguracionView(ctk.CTkFrame):
    def __init__(self, parent, **kw):
        super().__init__(parent, fg_color="transparent", corner_radius=0, **kw)
        self._build()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.top_bar = TopBar(self, title="⚙️ Configuración", subtitle="Ajustes generales")
        self.top_bar.grid(row=0, column=0, sticky="ew")

        content = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        content.grid(row=1, column=0, sticky="nsew", padx=T.PAD_OUTER, pady=T.PAD_OUTER)
        
        # Tarjeta de Ajustes
        card = ctk.CTkFrame(content, fg_color=T.BG_CARD, corner_radius=T.RADIUS_MD, border_width=1, border_color=T.BORDER)
        card.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(card, text="Gemini API Key", font=T.FONT_H3, text_color=T.TEXT_PRIMARY).pack(anchor="w", padx=20, pady=(20, 5))
        ctk.CTkLabel(card, text="Se requiere una valid token para usar la inteligencia artificial extrayendo facturas.", font=T.FONT_SMALL, text_color=T.TEXT_SECONDARY).pack(anchor="w", padx=20)
        
        self.api_entry = ctk.CTkEntry(card, width=400, font=T.FONT_BODY, fg_color=T.BG_APP, border_color=T.BORDER, show="*")
        self.api_entry.pack(anchor="w", padx=20, pady=(10, 10))
        
        ctk.CTkLabel(card, text="Supabase URL", font=T.FONT_H3, text_color=T.TEXT_PRIMARY).pack(anchor="w", padx=20, pady=(10, 5))
        self.supa_url_entry = ctk.CTkEntry(card, width=400, font=T.FONT_BODY, fg_color=T.BG_APP, border_color=T.BORDER)
        self.supa_url_entry.pack(anchor="w", padx=20, pady=(0, 10))

        ctk.CTkLabel(card, text="Supabase Key", font=T.FONT_H3, text_color=T.TEXT_PRIMARY).pack(anchor="w", padx=20, pady=(10, 5))
        self.supa_key_entry = ctk.CTkEntry(card, width=400, font=T.FONT_BODY, fg_color=T.BG_APP, border_color=T.BORDER, show="*")
        self.supa_key_entry.pack(anchor="w", padx=20, pady=(0, 20))
        
        # Cargar si existe (de mem o config file)
        config_data = get_persisted_config()
        key = os.environ.get("GEMINI_API_KEY") or config_data.get("GEMINI_API_KEY", "")
        if key:
            self.api_entry.insert(0, key)
            os.environ["GEMINI_API_KEY"] = key
            
        supa_url = os.environ.get("SUPABASE_URL") or config_data.get("SUPABASE_URL", "")
        if supa_url:
            self.supa_url_entry.insert(0, supa_url)
            os.environ["SUPABASE_URL"] = supa_url

        supa_key = os.environ.get("SUPABASE_KEY") or config_data.get("SUPABASE_KEY", "")
        if supa_key:
            self.supa_key_entry.insert(0, supa_key)
            os.environ["SUPABASE_KEY"] = supa_key
            
        save_btn = ctk.CTkButton(card, text="Guardar Cambios", font=T.FONT_BTN, fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, command=self._save_config)
        save_btn.pack(anchor="w", padx=20, pady=(0, 20))

        # Tarjeta de Apariencia
        card2 = ctk.CTkFrame(content, fg_color=T.BG_CARD, corner_radius=T.RADIUS_MD, border_width=1, border_color=T.BORDER)
        card2.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(card2, text="Apariencia", font=T.FONT_H3, text_color=T.TEXT_PRIMARY).pack(anchor="w", padx=20, pady=(20, 5))
        
        self.theme_switch = ctk.CTkSwitch(card2, text="Modo Oscuro", font=T.FONT_BODY, command=self._toggle_theme)
        if ctk.get_appearance_mode() == "Dark":
            self.theme_switch.select()
        self.theme_switch.pack(anchor="w", padx=20, pady=(10, 20))

    def _save_config(self):
        val = self.api_entry.get().strip()
        os.environ["GEMINI_API_KEY"] = val
        
        url_val = self.supa_url_entry.get().strip()
        os.environ["SUPABASE_URL"] = url_val
        
        key_val = self.supa_key_entry.get().strip()
        os.environ["SUPABASE_KEY"] = key_val
        
        # Persistir en disco
        cfg = get_persisted_config()
        cfg["GEMINI_API_KEY"] = val
        cfg["SUPABASE_URL"] = url_val
        cfg["SUPABASE_KEY"] = key_val
        save_persisted_config(cfg)

    def _toggle_theme(self):
        if self.theme_switch.get():
            ctk.set_appearance_mode("dark")
        else:
            ctk.set_appearance_mode("light")
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(T.WIN_TITLE)
        self.geometry(f"{T.WIN_W}x{T.WIN_H}")
        self.minsize(T.WIN_MIN_W, T.WIN_MIN_H)
        self.configure(fg_color=T.BG_APP)

        # ── Layout: 2 Columns (Sidebar + Content) ─────────────────────────
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=200) # Sidebar
        self.grid_columnconfigure(1, weight=1) # Content

        # ── Sidebar ───────────────────────────────────────────────────────
        self.sidebar_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=T.BG_SIDEBAR)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(3, weight=1)

        # Spacer/Logo area
        ctk.CTkLabel(self.sidebar_frame, text=" Peucar App", font=T.FONT_H1, text_color=T.TEXT_PRIMARY).grid(row=0, column=0, padx=20, pady=(30, 30), sticky="w")

        # Botón Ingreso
        self.btn_ingreso = ctk.CTkButton(self.sidebar_frame, corner_radius=T.RADIUS_SM, height=40, font=T.FONT_BODY, anchor="w",
                                         command=lambda: self.select_view("ingreso"))
        self.btn_ingreso.grid(row=1, column=0, padx=20, pady=5, sticky="ew")

        # Botón Gestión Pedidos (NEW)
        self.btn_orders = ctk.CTkButton(self.sidebar_frame, corner_radius=T.RADIUS_SM, height=40, font=T.FONT_BODY, anchor="w",
                                         command=lambda: self.select_view("pedidos"))
        self.btn_orders.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        # Botón Configuración
        self.btn_config = ctk.CTkButton(self.sidebar_frame, corner_radius=T.RADIUS_SM, height=40, font=T.FONT_BODY, anchor="w",
                                         command=lambda: self.select_view("configuracion"))
        self.btn_config.grid(row=3, column=0, padx=20, pady=5, sticky="ew")

        # ── Content Frame ─────────────────────────────────────────────────
        self.content_container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.content_container.grid(row=0, column=1, sticky="nsew")
        self.content_container.grid_rowconfigure(0, weight=1)
        self.content_container.grid_columnconfigure(0, weight=1)

        # DB Manager init
        # Ensure credentials are in env before instantiating SupabaseManager
        cfg = get_persisted_config()
        if "SUPABASE_URL" in cfg: os.environ["SUPABASE_URL"] = cfg["SUPABASE_URL"]
        if "SUPABASE_KEY" in cfg: os.environ["SUPABASE_KEY"] = cfg["SUPABASE_KEY"]
        self.orders_db = SupabaseManager()

        # Instantiate Views
        self.views = {
            "ingreso": IngresoView(self.content_container, self._get_api_key, db_manager=self.orders_db),
            "configuracion": ConfiguracionView(self.content_container),
            "pedidos": OrdersView(self.content_container, db_manager=self.orders_db)
        }

        # Select Default
        self.select_view("ingreso")
        
        # Finally center
        self._center_window()

        # Search Bar (hidden by default)
        self.search_bar = FloatingSearchBar(
            self, 
            on_search=self._on_search, 
            on_close=self._toggle_search,
            on_next=lambda: self._on_search_nav(1),
            on_prev=lambda: self._on_search_nav(-1)
        )
        self.search_bar.place(relx=0.98, y=10, anchor="ne")
        self.search_bar.place_forget()
        self._search_active = False

        # Keyboard shortcuts
        self.bind_all("<Control-f>", lambda e: self._toggle_search())
        self.bind_all("<Escape>", lambda e: self._toggle_search(force_close=True))
        self.bind_all("<F5>", lambda e: self._on_f5())

    def _toggle_search(self, force_close=False):
        if self._search_active or force_close:
            if not self._search_active and force_close: return
            self.search_bar.place_forget()
            self._search_active = False
            # Clear search in active view
            active_view = self.views.get(self._current_view_name)
            if active_view and hasattr(active_view, "on_search"):
                active_view.on_search("")
        else:
            self.search_bar.place(relx=0.98, y=10, anchor="ne")
            self.search_bar.lift()
            self.search_bar.focus()
            self._search_active = True

    def _on_search(self, text):
        active_view = self.views.get(self._current_view_name)
        if active_view and hasattr(active_view, "on_search"):
            match_count, total_count = active_view.on_search(text)
            self.search_bar.set_count(match_count, total_count)

    def _on_search_nav(self, direction):
        active_view = self.views.get(self._current_view_name)
        if active_view and hasattr(active_view, "on_search_nav"):
            match_count, total_count = active_view.on_search_nav(direction)
            self.search_bar.set_count(match_count, total_count)

    def _on_f5(self, event=None):
        """Global Refresh handler."""
        for view in self.views.values():
            if hasattr(view, "refresh_data"):
                view.refresh_data()

    def _center_window(self):
        self.update_idletasks()
        # Use theme dimensions explicitly
        w = T.WIN_W
        h = T.WIN_H
        
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        
        x = (sw // 2) - (w // 2)
        y = (sh // 2) - (h // 2)
        
        # Set both size and position at once
        self.geometry(f'{w}x{h}+{x}+{y}')


    def select_view(self, name: str):
        self._current_view_name = name
        # Update colors on sidebar buttons to show "Active" state
        active_fg = T.BG_CARD
        inactive_fg = "transparent"
        text_active = T.TEXT_PRIMARY
        text_inactive = T.TEXT_SECONDARY

        if name == "ingreso":
            self.btn_ingreso.configure(fg_color=active_fg, text_color=text_active, text="❖  Ingreso", font=T.FONT_H3)
            self.btn_config.configure(fg_color=inactive_fg, text_color=text_inactive, text="⚙️ Configuracion", font=T.FONT_BODY)
            self.btn_orders.configure(fg_color=inactive_fg, text_color=text_inactive, text="📦 Pedidos", font=T.FONT_BODY)
        elif name == "configuracion":
            self.btn_ingreso.configure(fg_color=inactive_fg, text_color=text_inactive, text="❖  Ingreso", font=T.FONT_BODY)
            self.btn_config.configure(fg_color=active_fg, text_color=text_active, text="⚙️ Configuracion", font=T.FONT_H3)
            self.btn_orders.configure(fg_color=inactive_fg, text_color=text_inactive, text="📦 Pedidos", font=T.FONT_BODY)
        else: # pedidos
            self.btn_ingreso.configure(fg_color=inactive_fg, text_color=text_inactive, text="❖  Ingreso", font=T.FONT_BODY)
            self.btn_config.configure(fg_color=inactive_fg, text_color=text_inactive, text="⚙️ Configuracion", font=T.FONT_BODY)
            self.btn_orders.configure(fg_color=active_fg, text_color=text_active, text="📦 Pedidos", font=T.FONT_H3)

        # Hide all views, then show selected
        for view_frame in self.views.values():
            view_frame.grid_remove()
            
        self.views[name].grid(row=0, column=0, sticky="nsew")

    def _get_api_key(self) -> str:
        cfg = get_persisted_config()
        key = os.environ.get("GEMINI_API_KEY") or cfg.get("GEMINI_API_KEY", "")
        if key: 
            os.environ["GEMINI_API_KEY"] = key
            return key
        
        # Pide amigablemente que vaya a configuracion
        dialog = ctk.CTkInputDialog(
            text="Se requiere la API Key de Google Gemini.\nPuedes ingresarla aquí (se guardará permanentemente) o ir a la pestaña 'Configuracion':",
            title="Clave Faltante"
        )
        key = dialog.get_input()
        if key:
            os.environ["GEMINI_API_KEY"] = key
            cfg["GEMINI_API_KEY"] = key 
            save_persisted_config(cfg)
            # Opcional: Escribirlo en la vista de configuración
            self.views["configuracion"].api_entry.insert(0, key)
        return key or ""


# ─────────────────────────────────────────────────────────────────────────────
# Entry point (With Drag and Drop active)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Prevent multiple instances
    _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Usamos un puerto específico para Peucar App
        _lock_socket.bind(('127.0.0.1', 49155))
    except socket.error:
        # Si no podemos bindear, es que ya hay otra instancia
        print("[ALERTA] Ya hay una instancia de Peucar App ejecutándose.")
        sys.exit(0)

    # Mantener la referencia del socket viva

    # Optional: try to enable DnD (tkinterdnd2)
    try:
        from tkinterdnd2 import TkinterDnD
        class _DnDApp(App, TkinterDnD.Tk): pass  # type: ignore
        app = _DnDApp()
    except ImportError:
        app = App()

    app.mainloop()
