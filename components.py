"""
Reusable UI components
  • DropZone  — file drop area with preview
  • DataTable — iOS-style scrollable table
  • StatusBadge — coloured pill label
"""

import os
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from PIL import Image, ImageTk
import theme as T


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _rounded_shadow_frame(parent, **kw):
    """Convenience: a CTkFrame styled as a floating card."""
    return ctk.CTkFrame(
        parent,
        corner_radius=T.RADIUS_MD,
        fg_color=T.BG_CARD,
        border_color=T.BORDER,
        border_width=1,
        **kw,
    )


# ─────────────────────────────────────────────────────────────────────────────
# DropZone
# ─────────────────────────────────────────────────────────────────────────────

class DropZone(ctk.CTkFrame):
    """
    Interactive drop-zone with:
      • Dashed rounded border that pulses on hover/drag
      • File-type icon + instructions
      • Thumbnail preview after file is chosen
      • Getter: self.filepath
    """

    ACCEPTED = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}

    def __init__(self, parent, on_file_chosen=None, **kw):
        super().__init__(
            parent,
            corner_radius=T.RADIUS_LG,
            fg_color=T.BG_DROP,
            border_color=T.BORDER,
            border_width=2,
            **kw,
        )
        self.on_file_chosen = on_file_chosen
        self.filepath: str | None = None
        self._dragging = False
        self._thumb_ref = None   # keep PIL ref alive

        self._build()
        self._bind_drag_events()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.grid(row=0, column=0, sticky="nsew", padx=T.PAD_INNER, pady=T.PAD_INNER)
        self._content.grid_rowconfigure((0, 1, 2, 3, 4), weight=1)
        self._content.grid_columnconfigure(0, weight=1)

        # Cloud / upload icon (Unicode emoji — no asset needed)
        self._icon_lbl = ctk.CTkLabel(
            self._content,
            text="☁️",
            font=(T.FONT_FALLBACK, 48),
            text_color=T.TEXT_TERTIARY,
        )
        self._icon_lbl.grid(row=0, column=0, pady=(8, 0))

        self._title_lbl = ctk.CTkLabel(
            self._content,
            text="Arrastra tu factura aquí",
            font=T.FONT_H3,
            text_color=T.TEXT_PRIMARY,
        )
        self._title_lbl.grid(row=1, column=0, pady=(4, 0))

        self._sub_lbl = ctk.CTkLabel(
            self._content,
            text="o haz clic para explorar",
            font=T.FONT_SMALL,
            text_color=T.TEXT_SECONDARY,
        )
        self._sub_lbl.grid(row=2, column=0)

        self._types_lbl = ctk.CTkLabel(
            self._content,
            text="PDF · PNG · JPG · TIFF",
            font=T.FONT_MICRO,
            text_color=T.TEXT_TERTIARY,
        )
        self._types_lbl.grid(row=3, column=0, pady=(2, 8))

        # Hidden preview image label (shown after file selected)
        self._preview_lbl = ctk.CTkLabel(self._content, text="", width=200, height=200)
        self._preview_lbl.grid(row=4, column=0, pady=4)
        self._preview_lbl.grid_remove()

        # File name chip (shown after file selected)
        self._chip = ctk.CTkFrame(
            self._content,
            corner_radius=T.RADIUS_LG,
            fg_color=T.BG_APP,
            border_color=T.BORDER,
            border_width=1,
        )
        self._chip_lbl = ctk.CTkLabel(
            self._chip,
            text="",
            font=T.FONT_SMALL,
            text_color=T.TEXT_SECONDARY,
        )
        self._chip_lbl.grid(row=0, column=0, padx=12, pady=4)
        self._chip.grid(row=5, column=0, pady=(0, 8))
        self._chip.grid_remove()

        # Clickable overlay
        self.bind("<Button-1>", self._open_dialog)
        for child in self._content.winfo_children():
            child.bind("<Button-1>", self._open_dialog)

    # ── Drag-and-drop ─────────────────────────────────────────────────────────

    def _bind_drag_events(self):
        try:
            # tkinterdnd2 is optional; gracefully skip if absent
            self.drop_target_register("DND_Files")      # type: ignore[attr-defined]
            self.dnd_bind("<<Drop>>", self._on_drop)    # type: ignore[attr-defined]
            self.dnd_bind("<<DragEnter>>", self._on_drag_enter)  # type: ignore[attr-defined]
            self.dnd_bind("<<DragLeave>>", self._on_drag_leave)  # type: ignore[attr-defined]
        except Exception:
            pass   # DnD not available — click-to-open still works

    def _on_drag_enter(self, event=None):
        self.configure(fg_color=T.BG_DROP_ACT, border_color=T.ACCENT)

    def _on_drag_leave(self, event=None):
        self.configure(fg_color=T.BG_DROP, border_color=T.BORDER)

    def _on_drop(self, event):
        self._on_drag_leave()
        path = event.data.strip().strip("{}")
        self._load_file(path)

    # ── File handling ─────────────────────────────────────────────────────────

    def _open_dialog(self, event=None):
        path = filedialog.askopenfilename(
            title="Seleccionar factura",
            filetypes=[
                ("Documentos de factura", "*.pdf *.png *.jpg *.jpeg *.tiff *.bmp"),
                ("PDF", "*.pdf"),
                ("Imágenes", "*.png *.jpg *.jpeg *.tiff *.bmp"),
            ],
        )
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        ext = os.path.splitext(path)[1].lower()
        if ext not in self.ACCEPTED:
            return

        self.filepath = path
        basename = os.path.basename(path)

        # Update chip
        short = basename if len(basename) <= 32 else basename[:29] + "…"
        self._chip_lbl.configure(text=f"📄  {short}")
        self._chip.grid()

        # Attempt thumbnail (images only)
        if ext in {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
            try:
                img = Image.open(path)
                img.thumbnail((200, 180), Image.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, size=img.size)
                self._preview_lbl.configure(image=ctk_img, text="")
                self._preview_lbl._image = ctk_img   # keep ref
                self._preview_lbl.grid()
                # Hide text labels
                self._icon_lbl.configure(text="✅")
                self._title_lbl.configure(text="Archivo listo", text_color=T.SUCCESS)
                self._sub_lbl.configure(text="Haz clic para cambiar")
            except Exception:
                self._show_file_icon(ext)
        elif ext == ".pdf":
            self._icon_lbl.configure(text="📑")
            self._title_lbl.configure(text="PDF cargado", text_color=T.SUCCESS)
            self._sub_lbl.configure(text="Haz clic para cambiar")
            self._preview_lbl.grid_remove()
        else:
            self._show_file_icon(ext)

        if callable(self.on_file_chosen):
            self.on_file_chosen(path)

    def _show_file_icon(self, ext: str):
        icons = {".pdf": "📑", ".png": "🖼️", ".jpg": "🖼️", ".jpeg": "🖼️"}
        self._icon_lbl.configure(text=icons.get(ext, "📄"))
        self._title_lbl.configure(text="Archivo listo", text_color=T.SUCCESS)
        self._sub_lbl.configure(text="Haz clic para cambiar")
        self._preview_lbl.grid_remove()


# ─────────────────────────────────────────────────────────────────────────────
# StatusBadge
# ─────────────────────────────────────────────────────────────────────────────

BADGE_COLORS = {
    "success": (T.SUCCESS,  "#E9FAF0"),
    "warning": (T.WARNING,  "#FFF5E6"),
    "error":   (T.ERROR,    "#FFF0EF"),
    "neutral": (T.TEXT_SECONDARY, T.BG_APP),
}

class StatusBadge(ctk.CTkFrame):
    def __init__(self, parent, text="", status="neutral", **kw):
        fg_text, bg = BADGE_COLORS.get(status, BADGE_COLORS["neutral"])
        super().__init__(
            parent,
            corner_radius=T.RADIUS_LG,
            fg_color=bg,
            border_width=0,
            **kw,
        )
        ctk.CTkLabel(
            self,
            text=text,
            font=T.FONT_MICRO,
            text_color=fg_text,
        ).grid(row=0, column=0, padx=10, pady=3)


# ─────────────────────────────────────────────────────────────────────────────
# DataTable
# ─────────────────────────────────────────────────────────────────────────────

TABLE_COLUMNS = [
    ("Proveedor",     180),
    ("ID Remito/Fac", 140),
    ("Fecha",         100),
    ("Monto",         100),
    ("Estado",        120),
]

SAMPLE_DATA = []

ROW_H = 44
HDR_H = 38


class DataTable(ctk.CTkFrame):
    """
    Scrollable iOS-style table with:
      • Sticky header row
      • Alternating row backgrounds
      • StatusBadge in last column
      • Hover highlight per row
    """

    def __init__(self, parent, columns=TABLE_COLUMNS, data=None, on_row_click=None, on_delete_click=None, **kw):
        super().__init__(
            parent,
            corner_radius=T.RADIUS_MD,
            fg_color=T.BG_CARD,
            border_color=T.BORDER,
            border_width=1,
            **kw,
        )
        self.columns = columns
        self.data: list = data or []
        self.on_row_click = on_row_click
        self.on_delete_click = on_delete_click
        self._row_frames: list[ctk.CTkFrame] = []
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(
            self,
            fg_color=T.BG_APP,
            corner_radius=0,
            border_width=0,
            height=HDR_H,
        )
        hdr.grid(row=0, column=0, sticky="ew", padx=1, pady=(1, 0))
        hdr.grid_propagate(False)

        for col_i, (col_name, col_w) in enumerate(self.columns):
            hdr.grid_columnconfigure(col_i, minsize=col_w, weight=1)
            ctk.CTkLabel(
                hdr,
                text=col_name.upper(),
                font=(T.FONT_FALLBACK, 10, "bold"),
                text_color=T.TEXT_TERTIARY,
                anchor="center",
            ).grid(row=0, column=col_i, padx=4, pady=0, sticky="ew")
        
        # Action column header if delete is enabled
        if self.on_delete_click:
            hdr.grid_columnconfigure(len(self.columns), minsize=40, weight=0)
            ctk.CTkLabel(hdr, text="", width=40).grid(row=0, column=len(self.columns))
            
        # Scrollbar spacer to align with body
        hdr.grid_columnconfigure(99, minsize=16, weight=0)
        ctk.CTkLabel(hdr, text="", width=16).grid(row=0, column=99)

        # Thin separator
        sep = ctk.CTkFrame(self, height=1, fg_color=T.BORDER, corner_radius=0)
        sep.grid(row=1, column=0, sticky="ew", padx=1)

        # ── Scrollable body ───────────────────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=T.BORDER,
            scrollbar_button_hover_color=T.TEXT_TERTIARY,
        )
        self._scroll.grid(row=2, column=0, sticky="nsew", padx=1, pady=(0, 1))
        self.grid_rowconfigure(2, weight=1)

        # Body grid: just one column that fills the width
        self._scroll.grid_columnconfigure(0, weight=1)

        if self.data:
            self._populate(self.data)
        else:
            self._show_empty()

    # ── Populate ──────────────────────────────────────────────────────────────

    def _populate(self, data, highlight_indices=None):
        highlight_indices = highlight_indices or []
        if hasattr(self, "_empty_state") and self._empty_state and self._empty_state.winfo_exists():
            self._empty_state.destroy()
            self._empty_state = None

        for frame in self._row_frames:
            if frame.winfo_exists(): frame.destroy()
        self._row_frames.clear()

        for row_i, row_data in enumerate(data):
            # Base color: Highlight remitos (is_remito is index 5)
            is_rem = row_data[5] if len(row_data) > 5 else False
            
            if is_rem:
                bg = "#FEF9E7" # Very soft yellow for remitos
            else:
                bg = T.BG_CARD if row_i % 2 == 0 else T.BG_APP

            row_frame = ctk.CTkFrame(
                self._scroll,
                fg_color=bg,
                corner_radius=0,
                height=ROW_H,
                border_width=0,
            )
            # Row frame fills the single column of the scrollable frame
            row_frame.grid(row=row_i, column=0, sticky="ew")
            row_frame.grid_propagate(False)
            self._row_frames.append(row_frame)

            # Cells (Only for defined columns)
            for col_i in range(len(self.columns)):
                col_w = self.columns[col_i][1]
                row_frame.grid_columnconfigure(
                    col_i, minsize=col_w, weight=1
                )
            if self.on_delete_click:
                row_frame.grid_columnconfigure(len(self.columns), minsize=40, weight=0)

            # Cells (Only for defined columns)
            for col_idx in range(len(self.columns)):
                col_name = self.columns[col_idx][0]
                val = row_data[col_idx]
                
                is_subrow = row_data[-1] if len(row_data) > 0 else False
                
                if col_name == "Estado":
                    # Render explicitly as a StatusBadge
                    status_map = {
                        "Pendiente": "warning",
                        "Completado": "success",
                        "Error": "error"
                    }
                    badge_status = status_map.get(val, "neutral")
                    badge = StatusBadge(row_frame, text=str(val), status=badge_status)
                    # Align badge if subrow? Usually badges are centered/right, so maybe just slight pad
                    badge.grid(row=0, column=col_idx, padx=4, pady=0)
                    if self.on_row_click:
                        badge.bind("<Button-1>", lambda e, r=row_data: self.on_row_click(r))
                        for child in badge.winfo_children():
                            child.bind("<Button-1>", lambda e, r=row_data: self.on_row_click(r))
                else:
                    font = (T.FONT_FALLBACK, 13, "bold") if (col_idx == 0 and not is_subrow) else T.FONT_BODY
                    
                    # Indentation and symbols for sub-rows
                    display_text = str(val)
                    padx = 4
                    if col_idx == 0 and is_subrow:
                        display_text = f"    ↳ {val} (REMITO)"
                        padx = (10, 4)
                        text_color = T.TEXT_TERTIARY
                    elif col_idx == 0 and is_rem:
                        display_text = f"{val} (REMITO)"
                        padx = 4
                        text_color = T.TEXT_PRIMARY
                    else:
                        text_color = T.TEXT_PRIMARY if col_idx == 0 else T.TEXT_SECONDARY

                    lbl = ctk.CTkLabel(
                        row_frame, text=display_text, font=font,
                        text_color=text_color, anchor="w" if (col_idx == 0) else "center",
                    )
                    lbl.grid(row=0, column=col_idx, padx=padx, pady=0, sticky="ew")
                    # Bind click for the cell label
                    if self.on_row_click:
                        lbl.bind("<Button-1>", lambda e, r=row_data: self.on_row_click(r))
            
            # Delete button
            if self.on_delete_click:
                def _handle_del(r=row_data):
                    self.on_delete_click(r)
                    return "break" # Evita que el evento suba al frame

                btn_del = ctk.CTkButton(
                    row_frame, text="🗑️", font=(T.FONT_FALLBACK, 14),
                    width=30, height=30, fg_color="transparent",
                    hover_color=T.BG_HOVER, text_color=T.ERROR,
                    command=_handle_del
                )
                btn_del.grid(row=0, column=len(self.columns), padx=5)
                # También bindeamos el click directo para asegurar que el frame no lo robe
                btn_del.bind("<Button-1>", lambda e: _handle_del(), add="+")

            # Hover highlight & Click event (on frame)
            normal_bg = bg
            hover_bg = "#FFF59D" if is_rem else T.BG_HOVER
            _bind_hover(row_frame, normal_bg, hover_bg)
            
            if self.on_row_click:
                row_frame.bind("<Button-1>", lambda e, r=row_data: self.on_row_click(r))

        # Thin row separators
        # (drawn by alternating colours above — no extra widget needed)

    # Remove specific binding helper that was causing conflicts with children events
    # def _bind_click(self, widget, row_data): ... 


    def _show_empty(self):
        """Placeholder shown before any file is scanned."""
        if hasattr(self, "_empty_state") and self._empty_state and self._empty_state.winfo_exists():
            self._empty_state.destroy()
            self._empty_state = None

        for frame in self._row_frames:
            if frame.winfo_exists(): frame.destroy()
        self._row_frames.clear()

        self._empty_state = ctk.CTkFrame(self._scroll, fg_color="transparent", corner_radius=0)
        self._empty_state.grid(row=0, column=0, sticky="nsew")
        for col_i in range(len(self.columns)):
            self._empty_state.grid_columnconfigure(col_i, weight=1)

        ctk.CTkLabel(
            self._empty_state,
            text="🔍",
            font=(T.FONT_FALLBACK, 40),
            text_color=T.TEXT_TERTIARY,
        ).grid(row=0, column=0, columnspan=4, pady=(48, 4))

        ctk.CTkLabel(
            self._empty_state,
            text="Aún no hay datos",
            font=T.FONT_H3,
            text_color=T.TEXT_SECONDARY,
        ).grid(row=1, column=0, columnspan=4)

        ctk.CTkLabel(
            self._empty_state,
            text="Carga una factura y pulsa  'Escanear'",
            font=T.FONT_SMALL,
            text_color=T.TEXT_TERTIARY,
        ).grid(row=2, column=0, columnspan=4, pady=(2, 48))

    # ── Public API ────────────────────────────────────────────────────────────

    def load_data(self, data: list, highlight_indices=None):
        self.data = data
        self._populate(data, highlight_indices)

    def clear(self):
        self.data = []
        self._show_empty()


# ─────────────────────────────────────────────────────────────────────────────
# Hover helper (works on CTkFrame + its children)
# ─────────────────────────────────────────────────────────────────────────────

def _bind_hover(widget, normal_color: str, hover_color: str):
    def on_enter(e):
        try:
            widget.configure(fg_color=hover_color)
        except Exception:
            pass

    def on_leave(e):
        try:
            widget.configure(fg_color=normal_color)
        except Exception:
            pass

    widget.bind("<Enter>", on_enter, add="+")
    widget.bind("<Leave>", on_leave, add="+")
    for child in widget.winfo_children():
        child.bind("<Enter>", on_enter, add="+")
        child.bind("<Leave>", on_leave, add="+")

# ─────────────────────────────────────────────────────────────────────────────
# OrderCard
# ─────────────────────────────────────────────────────────────────────────────

class OrderCard(ctk.CTkFrame):
    """
    Card-style view for an order with a list of items and checkboxes.
    """
    def __init__(self, parent, order_data, on_delete=None, on_edit=None, **kw):
        super().__init__(
            parent,
            corner_radius=T.RADIUS_LG,
            fg_color=T.BG_CARD,
            border_width=1,
            border_color=T.BORDER,
            **kw
        )
        self.order_data = order_data
        self.on_delete = on_delete
        self.on_edit = on_edit
        self._build()

    def _build(self):
        # Header: Date and Provider
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=15, pady=(15, 10))
        
        lbl_title = ctk.CTkLabel(
            hdr, 
            text=f"{self.order_data['fecha']} — {self.order_data['proveedor']}", 
            font=T.FONT_H3, 
            text_color=T.TEXT_PRIMARY
        )
        lbl_title.pack(side="left")
        
        # State Badge
        state = self.order_data['estado']
        status_map = {"Pendiente": "warning", "Parcial": "neutral", "Completado": "success"}
        badge = StatusBadge(hdr, text=state, status=status_map.get(state, "neutral"))
        badge.pack(side="left", padx=10)

        # Actions (Delete / Edit)
        actions = ctk.CTkFrame(hdr, fg_color="transparent")
        actions.pack(side="right")

        if self.on_delete:
            btn_del = ctk.CTkButton(
                actions, text="🗑️", font=(T.FONT_FALLBACK, 12),
                width=24, height=24, fg_color="transparent",
                hover_color=T.BG_HOVER, text_color=T.ERROR,
                command=lambda: self.on_delete(self.order_data['id'])
            )
            btn_del.pack(side="right")

        if self.on_edit:
            btn_edit = ctk.CTkButton(
                actions, text="✏️", font=(T.FONT_FALLBACK, 12),
                width=24, height=24, fg_color="transparent",
                hover_color=T.BG_HOVER, text_color=T.ACCENT,
                command=lambda: self.on_edit(self.order_data)
            )
            btn_edit.pack(side="right", padx=5)

        # Separator
        ctk.CTkFrame(self, height=1, fg_color=T.BORDER).pack(fill="x", padx=15)

        # Items List
        items_frame = ctk.CTkFrame(self, fg_color="transparent")
        items_frame.pack(fill="x", padx=20, pady=(10, 15))

        for i, item in enumerate(self.order_data['items']):
            # item = (id, codigo, q_pedida, q_entregada)
            _, code, qp, qe = item
            is_done = qe >= qp
            
            row = ctk.CTkFrame(items_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            
            # Checkbox (disabled, just for visual)
            cb = ctk.CTkCheckBox(
                row, text="", width=20, height=20, 
                checkbox_width=18, checkbox_height=18,
                corner_radius=4,
                state="disabled"
            )
            if is_done: cb.select()
            cb.pack(side="left")
            
            # Text
            display_text = f"{code}  ( {int(qe)} / {int(qp)} )"
            font = (T.FONT_FALLBACK, 13)
            color = T.TEXT_SECONDARY
            
            if is_done:
                font = (T.FONT_FALLBACK, 13, "overstrike")
                color = T.TEXT_TERTIARY
                
            lbl = ctk.CTkLabel(row, text=display_text, font=font, text_color=color)
            lbl.pack(side="left", padx=5)

# ─────────────────────────────────────────────────────────────────────────────
# FloatingSearchBar
# ─────────────────────────────────────────────────────────────────────────────

class FloatingSearchBar(ctk.CTkFrame):
    """
    A Chrome-style floating search bar that appears at the top right.
    """
    def __init__(self, parent, on_search=None, on_close=None, on_next=None, on_prev=None, **kw):
        super().__init__(
            parent,
            corner_radius=T.RADIUS_MD,
            fg_color=T.BG_CARD,
            border_width=2, # Thicker border for better contrast
            border_color=T.ACCENT, # Use accent color for 'glow' effect
            height=40,
            **kw
        )
        self.on_search_callback = on_search
        self.on_close_callback = on_close
        self.on_next_callback = on_next
        self.on_prev_callback = on_prev
        self._build()

    def _build(self):
        # Result counter
        self.lbl_count = ctk.CTkLabel(
            self, text="0 / 0", font=T.FONT_SMALL, 
            text_color=T.TEXT_TERTIARY, width=60
        )
        self.lbl_count.pack(side="right", padx=(5, 12))

        # Navigation buttons (Arrows)
        self.btn_next = ctk.CTkButton(
            self, text="▼", font=(T.FONT_FALLBACK, 10),
            width=28, height=28, fg_color="transparent",
            hover_color=T.BG_HOVER, text_color=T.TEXT_SECONDARY,
            command=self.on_next_callback
        )
        self.btn_next.pack(side="right", padx=2)

        self.btn_prev = ctk.CTkButton(
            self, text="▲", font=(T.FONT_FALLBACK, 10),
            width=28, height=28, fg_color="transparent",
            hover_color=T.BG_HOVER, text_color=T.TEXT_SECONDARY,
            command=self.on_prev_callback
        )
        self.btn_prev.pack(side="right", padx=2)

        # Close button
        self.btn_close = ctk.CTkButton(
            self, text="✕", font=(T.FONT_FALLBACK, 12),
            width=28, height=28, fg_color="transparent",
            hover_color=T.BG_HOVER, text_color=T.TEXT_SECONDARY,
            command=self.on_close_callback
        )
        self.btn_close.pack(side="right", padx=(5, 2))

        # Search icon
        lbl_icon = ctk.CTkLabel(self, text="🔍", font=(T.FONT_FALLBACK, 14))
        lbl_icon.pack(side="left", padx=(15, 5))

        # Entry
        self.entry = ctk.CTkEntry(
            self, font=T.FONT_BODY, fg_color="transparent",
            border_width=0, placeholder_text="Buscar...",
            width=200
        )
        self.entry.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=4)
        self.entry.bind("<KeyRelease>", self._on_key)
        # Enter now calls NEXT
        self.entry.bind("<Return>", lambda e: self.on_next_callback() if self.on_next_callback else None)

    def _on_key(self, event):
        if self.on_search_callback:
            self.on_search_callback(self.entry.get())

    def focus(self):
        self.entry.focus_set()

    def clear(self):
        self.entry.delete(0, "end")

    def set_count(self, current, total):
        self.lbl_count.configure(text=f"{current} / {total}")
