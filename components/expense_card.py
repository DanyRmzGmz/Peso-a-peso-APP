"""
Módulo de componente de tarjeta de gasto.
Crea las tarjetas que se muestran en el GridView de la vista de gastos.
"""

import flet as ft
from core.colors import COLOR_ATARDECER, COLOR_OCEANO, COLOR_BLANCO


def create_expense_card(icon: ft.icons, label: str, es_recurrente: bool = False) -> ft.Container:
    """
    Crea una tarjeta de gasto para el GridView.

    Args:
        icon: Icono de Flet a mostrar en la tarjeta.
        label: Etiqueta de texto para la tarjeta.
        es_recurrente: Indica si es un gasto fijo/recurrente (True) o variable (False).

    Returns:
        ft.Container: La tarjeta de gasto configurada con efectos hover.
    """
    def on_hover(e):
        e.control.scale = 1.05 if e.data == "true" else 1.0
        e.control.shadow = ft.BoxShadow(
            blur_radius=15,
            color=ft.colors.with_opacity(0.2, ft.colors.BLACK)
        ) if e.data == "true" else None
        e.control.update()

    # Crear indicador de tipo (fijo/variable)
    indicador = ft.Container(
        content=ft.Text(
            "🔄 Fijo" if es_recurrente else "📊 Variable",
            size=10,
            weight=ft.FontWeight.W_400,
        ),
        bgcolor=COLOR_OCEANO if es_recurrente else COLOR_ATARDECER,
        padding=ft.padding.only(left=8, right=8, top=4, bottom=4),
        border_radius=10,
    )

    return ft.Container(
        content=ft.Column(
            [
                ft.Stack(
                    [
                        ft.Icon(icon, color=COLOR_ATARDECER, size=48),
                        ft.Container(
                            content=indicador,
                            alignment=ft.alignment.Alignment(1, -1),
                            margin=ft.margin.only(top=-5, right=-5),
                        ),
                    ],
                    height=55,
                ),
                ft.Text(label, weight=ft.FontWeight.W_500, size=14, color=COLOR_OCEANO),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=5,
        ),
        bgcolor=COLOR_BLANCO,
        padding=20,
        border_radius=20,
        alignment=ft.alignment.Alignment.CENTER,
        animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
        on_hover=on_hover,
    )