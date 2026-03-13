"""
Theme configuration — iOS/Pinterest aesthetic
Soft whites, warm grays, vivid accent, generous radius
"""

# ── Palette (Light, Dark) ────────────────────────────────────────────────────
# CustomTkinter usa arreglos [Color_Claro, Color_Oscuro] para cambiar dinámicamente.

BG_APP        = ["#F5F5F7", "#121212"]   # macOS / iOS system background
BG_CARD       = ["#FFFFFF", "#1E1E1E"]   # card / panel surface
BG_SIDEBAR    = ["#E2E2E9", "#0M0M0M"]   # sidebar surface (un poco más distintivo) -> reemplazado abajo
BG_SIDEBAR    = ["#EAEAEF", "#0A0A0A"]
BG_HOVER      = ["#F0F0F5", "#2C2C2E"]   # hover state for rows/buttons
BG_DROP       = ["#F8F8FC", "#18181B"]   # drop-zone fill
BG_DROP_ACT   = ["#EEF0FF", "#2E2D4A"]   # drop-zone active (dragging over)

ACCENT        = ["#5B5BF6", "#5E5CE6"]   # vibrant indigo — main CTA
ACCENT_HOVER  = ["#4747E0", "#4A49D1"]
ACCENT_TEXT   = ["#FFFFFF", "#FFFFFF"]

TEXT_PRIMARY   = ["#1C1C1E", "#F2F2F7"]  # iOS label colour
TEXT_SECONDARY = ["#6E6E73", "#AEAEC0"]  # iOS secondary label
TEXT_TERTIARY  = ["#AEAEB2", "#636366"]  # placeholder / disabled

BORDER        = ["#E5E5EA", "#38383A"]   # very light divider
BORDER_FOCUS  = ["#5B5BF6", "#5E5CE6"]   # focused input ring

SUCCESS       = ["#34C759", "#32D74B"]   # iOS green
WARNING       = ["#FF9F0A", "#FF9F0A"]   # iOS orange
ERROR         = ["#FF3B30", "#FF453A"]   # iOS red

# ── Geometry ─────────────────────────────────────────────────────────────────
RADIUS_SM  = 10
RADIUS_MD  = 16
RADIUS_LG  = 24
RADIUS_XL  = 32

PAD_OUTER  = 24   # outer margin of the window
PAD_INNER  = 16   # inner padding inside cards
GAP        = 16   # gap between panels / rows

# ── Typography ────────────────────────────────────────────────────────────────
FONT_FAMILY   = "SF Pro Display"   # falls back to system sans-serif
FONT_FALLBACK = "Segoe UI"

FONT_H1  = (FONT_FALLBACK, 22, "bold")
FONT_H2  = (FONT_FALLBACK, 16, "bold")
FONT_H3  = (FONT_FALLBACK, 13, "bold")
FONT_BODY  = (FONT_FALLBACK, 13, "normal")
FONT_SMALL = (FONT_FALLBACK, 11, "normal")
FONT_MICRO = (FONT_FALLBACK, 10, "normal")
FONT_BTN   = (FONT_FALLBACK, 14, "bold")

# ── CustomTkinter appearance overrides ───────────────────────────────────────
CTK_THEME = {
    "CTk": {
        "fg_color": BG_APP,
    },
    "CTkFrame": {
        "fg_color": BG_CARD,
        "top_fg_color": BG_CARD,
        "corner_radius": RADIUS_MD,
        "border_width": 1,
        "border_color": BORDER,
    },
    "CTkButton": {
        "fg_color": ACCENT,
        "hover_color": ACCENT_HOVER,
        "text_color": ACCENT_TEXT,
        "corner_radius": RADIUS_LG,
        "border_width": 0,
    },
    "CTkLabel": {
        "text_color": TEXT_PRIMARY,
    },
}

# ── Window ────────────────────────────────────────────────────────────────────
WIN_W  = 1180
WIN_H  = 700
WIN_MIN_W = 900
WIN_MIN_H = 580
WIN_TITLE = "Peucar App  ·  Escáner de Facturas"
