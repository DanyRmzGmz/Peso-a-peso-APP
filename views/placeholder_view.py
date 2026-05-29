"""
Módulo de vista Placeholder.
Contiene una vista genérica para vistas en construcción.
"""

import flet as ft
from core.colors import COLOR_OCEANO


def get_placeholder_view(title: str) -> ft.Column:
    """
    Genera una vista de marcador de posición para vistas en construcción.

    Args:
        title: Título de la vista a mostrar.

    Returns:
        ft.Column: La columna que contiene la vista placeholder.
    """
    return ft.Column(
        [
            ft.Text(title, size=32, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
            ft.Container(
                content=ft.Text(f"Contenido de {title} en construcción...", size=18, italic=True),
                expand=True,
                alignment=ft.alignment.Alignment.CENTER,
            ),
        ],
        expand=True,
    )