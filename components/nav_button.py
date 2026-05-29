"""
Módulo de componente de botón de navegación.
Crea los botones del sidebar para navegar entre vistas.
"""

import flet as ft
from core.colors import COLOR_BLANCO, COLOR_OCEANO


def create_nav_button(
    text: str,
    icon: ft.icons,
    view_name: str,
    state: dict,
    update_callback: callable
) -> ft.Container:
    """
    Crea un botón de navegación para el sidebar.

    Args:
        text: Texto a mostrar en el botón.
        icon: Icono de Flet a mostrar.
        view_name: Nombre de la vista asociada al botón.
        state: Diccionario con el estado de la aplicación.
        update_callback: Función a llamar cuando se hace clic en el botón.

    Returns:
        ft.Container: El botón de navegación configurado.
    """
    is_active = state["current_view"] == view_name

    def on_click(e):
        state["current_view"] = view_name
        update_callback()

    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(icon, color=COLOR_BLANCO if is_active else COLOR_OCEANO, size=18),
                ft.Text(
                    text,
                    color=COLOR_BLANCO if is_active else COLOR_OCEANO,
                    size=16,
                    weight=ft.FontWeight.W_500
                ),
            ],
            spacing=10,
            alignment=ft.MainAxisAlignment.START,
        ),
        padding=10,
        border_radius=8,
        bgcolor=ft.Colors.TRANSPARENT,
        shadow=ft.BoxShadow(
            blur_radius=10,
            color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK)
        ) if is_active else None,
        on_click=on_click,
    )