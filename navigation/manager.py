"""
Módulo de gestión de navegación.
Maneja la lógica del sidebar y la actualización de vistas.
"""

import flet as ft
from core.colors import COLOR_ARENA, COLOR_CREMA, COLOR_OCEANO
from components.nav_button import create_nav_button
from views.gastos_view import get_gastos_view
from views.placeholder_view import get_placeholder_view


class NavigationManager:
    """
    Clase responsable de manejar la navegación entre vistas de la aplicación.
    """

    def __init__(self, page: ft.Page, state: dict):
        """
        Inicializa el gestor de navegación.

        Args:
            page: La página de Flet.
            state: Diccionario con el estado de la aplicación.
        """
        self.page = page
        self.state = state

        # Contenedor del sidebar (izquierdo)
        self.sidebar_content = ft.Column(spacing=15, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.sidebar = ft.Container(
            content=self.sidebar_content,
            padding=30,
            bgcolor=COLOR_ARENA,
            expand=1,
        )

        # Contenedor del área de contenido principal (centro)
        self.main_content_area = ft.Container(
            expand=2,
            padding=40,
            bgcolor=COLOR_CREMA,
        )

        # Panel lateral derecho para grupos de categorías en Gastos
        self.right_panel_content = ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.right_panel = ft.Container(
            content=self.right_panel_content,
            padding=20,
            bgcolor=COLOR_ARENA,
            expand=1,
            visible=False,  # Oculto por defecto
        )

    def update_view(self) -> None:
        """
        Actualiza el contenido del sidebar y del área principal según el estado actual.
        """
        # Actualizar Sidebar
        self.sidebar_content.controls = [
            ft.Text("PESO A PESO", size=24, weight=ft.FontWeight.W_900, color=COLOR_OCEANO, text_align=ft.TextAlign.CENTER),
            ft.Divider(height=30, color="transparent"),
            create_nav_button("General", ft.icons.Icons.DASHBOARD, "General", self.state, self.update_view),
            create_nav_button("Gastos", ft.icons.Icons.MONEY_OFF, "Gastos", self.state, self.update_view),
            create_nav_button("Ingresos", ft.icons.Icons.ATTACH_MONEY, "Ingresos", self.state, self.update_view),
            create_nav_button("Historial", ft.icons.Icons.HISTORY, "Historial", self.state, self.update_view),
        ]

        # Actualizar Contenido
        if self.state["current_view"] == "Gastos":
            # Pasar referencia al panel derecho para que la vista pueda actualizarlo
            gastos_view = get_gastos_view(self.right_panel)
            self.main_content_area.content = gastos_view
            self.right_panel.visible = True
        else:
            self.main_content_area.content = get_placeholder_view(self.state["current_view"])
            self.right_panel.visible = False

        self.page.update()

    def get_layout(self) -> ft.Row:
        """
        Retorna el layout completo de la aplicación con sidebar, contenido y panel derecho.

        Returns:
            ft.Row: El layout principal de la aplicación.
        """
        return ft.Row(
            [
                self.sidebar,
                self.main_content_area,
                self.right_panel,
            ],
            expand=True,
            spacing=0,
        )

    def render_initial(self) -> None:
        """
        Renderiza la vista inicial de la aplicación.
        """
        self.update_view()