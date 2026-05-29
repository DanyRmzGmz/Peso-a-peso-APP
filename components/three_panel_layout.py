import flet as ft
from core.colors import COLOR_ARENA, COLOR_CREMA, COLOR_BLANCO, COLOR_OCEANO, COLOR_ATARDECER, COLOR_CIAN, GRADIENTE_OCEANO, GRADIENTE_DESTACADO
from core.translations import t

class ThreePanelLayout:
    """Clase que gestiona el layout de navegación reconstruyendo estados para evitar bugs de Flet."""

    def __init__(self, page: ft.Page):
        self.page = page
        self.current_menu_item = "General"  # Estado activo inicial
        self.menu_items_dict = {}  # Almacén de referencias para manipulación rápida de hover/clic
        self._setup_panels()

    def create_menu_item(self, text, emoji_icon, data, click_handler):
        """Genera un ítem de menú estático garantizando el renderizado del gradiente y sombra en Windows."""
        is_active = (data == self.current_menu_item)
        text_color = COLOR_OCEANO if is_active else COLOR_BLANCO

        text_control = ft.Text(
            text, 
            size=22,  
            weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.W_500, 
            color=text_color
        )
        icon_control = ft.Text(emoji_icon, size=28)  

        def handle_hover(e):
            if self.current_menu_item != data:
                e.control.bgcolor = ft.Colors.with_opacity(0.12, COLOR_BLANCO) if e.data == "true" else ft.Colors.TRANSPARENT
                e.control.update()

        active_shadow = ft.BoxShadow(
            spread_radius=1,
            blur_radius=12,
            color=ft.Colors.with_opacity(0.3, COLOR_ATARDECER),
            offset=ft.Offset(0, 4)
        )

        return ft.Container(
            content=ft.Row(
                controls=[icon_control, text_control], 
                spacing=10, 
                alignment=ft.MainAxisAlignment.START,
            ), 
            padding=ft.padding.only(top=12, bottom=12, left=12, right=14), 
            border_radius=12, 
            width=252,  
            gradient=GRADIENTE_DESTACADO if is_active else None,
            shadow=active_shadow if is_active else None,
            bgcolor=None if is_active else ft.Colors.TRANSPARENT,
            on_hover=handle_hover,
            on_click=click_handler, 
            data=data,
        )

    def _setup_panels(self) -> None:
        logo_container = ft.Container(
            content=ft.Image(
                src="logo.png", 
                width=160,      
                height=160,
                fit="contain",
            ),
            alignment=ft.Alignment(0, 0),
            margin=ft.margin.symmetric(vertical=15)
        )

        self.menu_buttons_column = ft.Column(spacing=6)
        self.settings_button_container = ft.Container()

        sidebar_column = ft.Column(
            controls=[
                self.menu_buttons_column,
                logo_container,
                self.settings_button_container
            ], 
            expand=True,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.sidebar = ft.Container(
            content=sidebar_column,
            padding=ft.padding.only(top=30, bottom=30, left=14, right=14), 
            width=280,
            gradient=GRADIENTE_OCEANO,
        )

        self._rebuild_sidebar()

        self.tabs_container = ft.Container(visible=False, margin=ft.margin.only(bottom=24)) 
        self.tab_body_container = ft.Container(expand=True) 
        
        self.main_content_column = ft.Column(
            controls=[
                self.tabs_container,
                self.tab_body_container
            ],
            expand=True, 
            horizontal_alignment=ft.CrossAxisAlignment.START, 
            alignment=ft.MainAxisAlignment.START,
        )

        self.main_panel = ft.Container(
            content=ft.Container(
                content=self.main_content_column, 
                bgcolor=COLOR_BLANCO,
                border_radius=24,
                padding=32,
                expand=True,
                border=ft.border.all(1, ft.Colors.with_opacity(0.05, COLOR_CIAN))
            ),
            expand=True, 
            padding=ft.padding.all(24), 
            bgcolor=COLOR_CREMA, 
            alignment=ft.Alignment(0, -1),
        )

    def _rebuild_sidebar(self) -> None:
        """Borra e inyecta controles nuevos desde cero para evitar limitaciones físicas de parches en Flet."""
        self.menu_buttons_column.controls = [
            self.create_menu_item(t("three_panel_general", "General"), "📊", "General", self._handle_menu_click),
            self.create_menu_item(t("three_panel_expenses", "Gastos"), "💸", "Gastos", self._handle_menu_click),
            self.create_menu_item(t("three_panel_income", "Ingresos"), "📈", "Ingresos", self._handle_menu_click),
            self.create_menu_item(t("three_panel_debts", "Deudas"), "💳", "Deudas", self._handle_menu_click),
            self.create_menu_item(t("three_panel_history", "Historial"), "🕒", "Historial", self._handle_menu_click),
        ]
        
        self.settings_button_container.content = self.create_menu_item(
            t("menu_config", "Configuración"), "⚙️", "Configuración", self._handle_menu_click
        )
        
        if hasattr(self, 'sidebar') and getattr(self.sidebar, "_page", None) is not None:
            self.sidebar.update()

    def _handle_menu_click(self, e: ft.TapEvent) -> None:
        menu_item = e.control.data
        if menu_item == self.current_menu_item and self.tabs_container.visible:
            return

        self.current_menu_item = menu_item
        self._rebuild_sidebar()
        self.page.update()
        
        self.tabs_container.visible = False 
        self.tab_body_container.content = None

        if menu_item == "General":
            from views.general_view import create_general_view
            self.tab_body_container.content = create_general_view(self.page)
        elif menu_item == "Deudas":
            from views.deudas_view import create_deudas_view
            self.tab_body_container.content = create_deudas_view(self.page)
        elif menu_item == "Historial":
            from views.historial_view import create_historial_view
            self.tab_body_container.content = create_historial_view(self.page)
        elif menu_item == "Configuración":
            from views.settings_view import create_settings_view
            self.tab_body_container.content = create_settings_view(self.page)
        elif menu_item == "Gastos":
            grupos_gastos = [
                ("three_panel_expenses_fixed", "Gastos Fijos"),
                ("three_panel_expenses_operational", "Gastos Operativos"),
                ("three_panel_expenses_minor", "Gastos Hormiga"),
                ("three_panel_expenses_periodic", "Gastos Periódicos"),
                ("three_panel_other_expenses", "Otros gastos")
            ]
            self._build_tabbed_view(grupos_gastos, 'expense')
            return
        elif menu_item == "Ingresos":
            grupos_ingresos = [
                ("three_panel_income_fixed", "Ingresos Fijos"),
                ("three_panel_income_variable", "Ingresos Variables"),
                ("three_panel_income_passive", "Ingresos Pasivos"),
                ("three_panel_income_extraordinary", "Ingresos Extraordinarios")
            ]
            self._build_tabbed_view(grupos_ingresos, 'income')
            return
        
        self.main_panel.update()

    def _build_tabbed_view(self, groups: list[tuple], category_type: str) -> None:
        """Construye las sub-pestañas superiores aplicando mutación interna de colores del gradiente."""
        from views.categorias_view import create_categorias_view
        state = {"active_group": groups[0][1]}
        tab_gradients_dict = {}
        
        def render_tabs():
            tabs_controls = []
            for t_key, g_name in groups:
                is_active = (g_name == state["active_group"])
                
                initial_colors = GRADIENTE_DESTACADO.colors if is_active else [ft.Colors.TRANSPARENT, ft.Colors.TRANSPARENT]
                
                local_tab_gradient = ft.LinearGradient(
                    begin=GRADIENTE_DESTACADO.begin,
                    end=GRADIENTE_DESTACADO.end,
                    colors=initial_colors
                )
                tab_gradients_dict[g_name] = local_tab_gradient
                
                tab = ft.Container(
                    content=ft.Text(
                        t(t_key, g_name), 
                        size=14, 
                        weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.W_500,
                        color=COLOR_OCEANO if is_active else ft.Colors.GREY_500,
                    ),
                    padding=ft.padding.symmetric(horizontal=18, vertical=10),
                    border_radius=10,
                    gradient=local_tab_gradient,
                    on_click=lambda e, group=g_name: on_tab_change(group),
                    animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT)
                )
                tabs_controls.append(tab)
                
            self.tabs_container.content = ft.Container(
                content=ft.Row(
                    controls=tabs_controls, 
                    scroll=ft.ScrollMode.AUTO, 
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.06, COLOR_CIAN))),
                padding=ft.padding.only(bottom=10)
            )
            self.tabs_container.visible = True
            
        def on_tab_change(group):
            if group == state["active_group"]:
                return
            state["active_group"] = group
            render_tabs()
            self.tab_body_container.content = create_categorias_view(self.page, group, category_type)
            self.main_panel.update()

        render_tabs()
        self.tab_body_container.content = create_categorias_view(self.page, state["active_group"], category_type)
        self.main_panel.update()

    def get_layout(self) -> ft.Row:
        """Devuelve el control raíz Row del layout para el inicializador de la app."""
        return ft.Row(
            controls=[self.sidebar, self.main_panel],
            expand=True, 
            spacing=0, 
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )

def create_three_panel_layout(page: ft.Page) -> ft.Row:
    layout = ThreePanelLayout(page)
    return layout.get_layout()