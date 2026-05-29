import flet as ft

COLOR_ARENA = "#F2E1C1"
COLOR_OCEANO = "#226F81"
COLOR_ATARDECER = "#F3A953"
COLOR_CREMA = "#FEF9EF"
COLOR_BLANCO = "#FFFFFF"
COLOR_CIAN = "#26798C"

# El gradiente de tu barra lateral (Arriba hacia Abajo)
GRADIENTE_OCEANO = ft.LinearGradient(
    begin=ft.Alignment(-1, 0),
    end=ft.Alignment(1, 0),
    colors=[COLOR_OCEANO, ft.Colors.TEAL]
)

# Gradiente sutil para destacar tarjetas (Diagonal de arriba-izquierda a abajo-derecha)
GRADIENTE_DESTACADO = ft.LinearGradient(
    begin=ft.Alignment(-1, -1),
    end=ft.Alignment(1, 1),
    colors=[COLOR_ATARDECER, COLOR_ARENA]
)

# Gradiente suave para fondos limpios (Diagonal de arriba-izquierda a abajo-derecha)
GRADIENTE_FONDO_SUAVE = ft.LinearGradient(
    begin=ft.Alignment(-1, -1),
    end=ft.Alignment(1, 1),
    colors=[COLOR_CREMA, COLOR_BLANCO]
)