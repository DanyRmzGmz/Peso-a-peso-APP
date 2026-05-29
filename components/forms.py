"""
Formularios modulares y diálogos interactivos de la aplicación.
Gestión nativa para transacciones rápidas, creación de categorías y plantillas dinámicas.
Refactorizado con look de alta gama blanco/crema y bordes suavizados con opacidad sutil.
"""
import flet as ft
import datetime
from database.connection import get_payment_methods_for_dropdown, save_transaction, get_transaction_by_id, get_categories_by_group, get_payment_methods
from core.colors import COLOR_ARENA, COLOR_BLANCO, COLOR_OCEANO, COLOR_CREMA, COLOR_CIAN
from core.translations import t

# LISTA MAESTRA DE 30 ÍCONOS PARA HOMOLOGAR FORMULARIOS
SHARED_ICONS = [
    "🛒", "🍔", "🚌", "🏥", "🐾", "🎮", "👕", "🔧", "🎁", "✈️", 
    "📱", "🏠", "💡", "💰", "📦", "🍽️", "☕", "🎬", "📚", "⛽", 
    "💊", "💻", "🎉", "🏋️", "🎵", "⚡", "💳", "🏦", "📈", "✨"
]

class TransactionForm(ft.AlertDialog):
    """Formulario dinámico para registrar una transacción (gasto o ingreso) como Modal con recurrencia flexible."""
    def __init__(self, page: ft.Page, category_id: int, category_name: str, transaction_type: str, 
                 is_recurring_default: bool, on_save_callback: callable, on_cancel_callback: callable, edit_id: int = None):
        super().__init__()
        self._page = page
        self.category_id = category_id
        self.category_name = t(str(category_name).lower().replace(" ", "_"), default=category_name)
        self.transaction_type = transaction_type
        self.is_recurring_default = is_recurring_default
        self.on_save_callback = on_save_callback
        self.on_cancel_callback = on_cancel_callback
        self.edit_id = edit_id
        self.is_editing = edit_id is not None
        
        self.bgcolor = COLOR_CREMA
        self.shape = ft.RoundedRectangleBorder(radius=20)

        self._setup_form_controls()
        if self.is_editing:
            self._load_transaction_data()

    def _load_transaction_data(self):
        transaction = get_transaction_by_id(self.edit_id)
        if transaction:
            self.amount_field.value = str(transaction["amount"])
            self.description_field.value = transaction["description"]
            
            if "date" in transaction and transaction["date"]:
                try:
                    date_obj = datetime.datetime.strptime(transaction["date"], "%Y-%m-%d")
                    self.date_field.value = date_obj.strftime("%d/%m/%Y")
                except ValueError:
                    self.date_field.value = transaction["date"]

            if "payment_method_id" in transaction and transaction["payment_method_id"] is not None:
                self.payment_method_dropdown.value = str(transaction["payment_method_id"])
            
            # Carga de datos de recurrencia en modo edición
            if "is_recurrence_active" in transaction:
                is_active = bool(transaction["is_recurrence_active"])
                self.recurrence_checkbox.value = is_active
                self.recurrence_dropdown.visible = is_active
                if is_active and "recurrence_type" in transaction and transaction["recurrence_type"]:
                    self.recurrence_dropdown.value = transaction["recurrence_type"]

    def _setup_form_controls(self) -> None:
        self.title = ft.Text(
            t("transaction_form_register", "Registrar {category}").replace("{category}", self.category_name),
            weight=ft.FontWeight.BOLD, color=COLOR_OCEANO, size=22
        )

        padding_estandar = ft.padding.symmetric(horizontal=12)
        alto_estandar = 62

        self.amount_field = ft.TextField(
            label=t("transaction_form_amount", "Monto"), hint_text="0.00", prefix=ft.Text("$ ", color=COLOR_OCEANO, weight=ft.FontWeight.BOLD),
            keyboard_type=ft.KeyboardType.NUMBER, input_filter=ft.InputFilter(allow=True, regex_string=r"^[0-9]*\.?[0-9]*$"),
            bgcolor=COLOR_BLANCO, border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO), focused_border_color=COLOR_OCEANO,
            color=ft.Colors.BLACK, border_radius=10, label_style=ft.TextStyle(color=ft.Colors.GREY_600), 
            content_padding=padding_estandar, height=alto_estandar
        )

        raw_options = get_payment_methods_for_dropdown()
        translated_options = []
        
        for o in raw_options:
            text_str = str(o.text)
            parts = text_str.split(" ", 1)
            if len(parts) > 1:
                icon_part = parts[0]
                name_part = parts[1].strip()
                translated_text = f"{icon_part} {t(name_part.lower().replace(' ', '_'), default=name_part)}"
            else:
                translated_text = t(text_str.lower().replace(' ', '_'), default=text_str)
            translated_options.append(ft.dropdown.Option(key=o.key, text=translated_text))

        self.payment_method_dropdown = ft.Dropdown(
            label=t("transaction_form_payment_method", "Método de Pago"), 
            options=translated_options,
            bgcolor=COLOR_BLANCO, border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO), focused_border_color=COLOR_OCEANO,
            color=ft.Colors.BLACK, border_radius=10, label_style=ft.TextStyle(color=ft.Colors.GREY_600), 
            content_padding=padding_estandar, height=alto_estandar
        )
        
        if self.payment_method_dropdown.options:
            self.payment_method_dropdown.value = self.payment_method_dropdown.options[0].key

        self.date_picker = ft.DatePicker(
            on_change=self._on_date_change, on_dismiss=lambda e: self._page.update(),
            help_text="Seleccionar Fecha", cancel_text="Cancelar", confirm_text="Aceptar",
            error_format_text="Formato inválido.", error_invalid_text="Fecha fuera de rango.",
            field_hint_text="dd/mm/yyyy", field_label_text="Ingresar fecha"
        )
        self._page.overlay.append(self.date_picker)

        self.date_field = ft.TextField(
            label=t("transaction_form_date", "Fecha"), 
            value=datetime.datetime.now().strftime("%d/%m/%Y") if not self.is_editing else "",
            read_only=True, bgcolor=COLOR_BLANCO, border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO), focused_border_color=COLOR_OCEANO,
            color=ft.Colors.BLACK, border_radius=10, label_style=ft.TextStyle(color=ft.Colors.GREY_600), 
            content_padding=padding_estandar, height=alto_estandar
        )

        self.date_row = ft.Row([
            self.date_field, 
            ft.IconButton(icon=ft.Icons.CALENDAR_MONTH, on_click=lambda e: setattr(self.date_picker, 'open', True) or self._page.update(), icon_color=COLOR_OCEANO)
        ], spacing=5)
        
        self.description_field = ft.TextField(
            label=t("transaction_form_description", "Nota (opcional)"), 
            multiline=True, min_lines=2, max_lines=3, max_length=250, 
            bgcolor=COLOR_BLANCO, border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO), focused_border_color=COLOR_OCEANO,
            color=ft.Colors.BLACK, border_radius=10, label_style=ft.TextStyle(color=ft.Colors.GREY_600), content_padding=ft.padding.symmetric(horizontal=12, vertical=10)
        )

        # CHECKBOX Y DROPDOWN CON LOCALE SEGURO Y OPCIONES EXPANDIDAS
        self.recurrence_checkbox = ft.Checkbox(
            label=t("transaction_form_recurring", "Es movimiento recurrente"), 
            value=self.is_recurring_default, 
            active_color=COLOR_OCEANO,
            on_change=self._toggle_recurrence_dropdown,
            disabled=self.is_editing
        )

        self.recurrence_dropdown = ft.Dropdown(
            label=t("transaction_form_frequency", "Frecuencia de Cobro"),
            options=[
                ft.dropdown.Option("dia", t("frequency_daily", "Diario")),
                ft.dropdown.Option("semana", t("frequency_weekly", "Semanal")),
                ft.dropdown.Option("quincenal", t("frequency_biweekly", "Quincenal")),
                ft.dropdown.Option("mes", t("frequency_monthly", "Mensual")),
                ft.dropdown.Option("bimensual", t("frequency_bimonthly", "Bimensual")),
                ft.dropdown.Option("trimestral", t("frequency_quarterly", "Trimestral")),
                ft.dropdown.Option("semestral", t("frequency_semiannually", "Semestral")),
                ft.dropdown.Option("anio", t("frequency_yearly", "Anual")),
            ],
            value="mes",
            visible=self.is_recurring_default,
            bgcolor=COLOR_BLANCO, border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO), focused_border_color=COLOR_OCEANO,
            color=ft.Colors.BLACK, border_radius=10, label_style=ft.TextStyle(color=ft.Colors.GREY_600),
            content_padding=padding_estandar, height=alto_estandar
        )

        self.content = ft.Container(
            content=ft.Column([
                self.amount_field, self.payment_method_dropdown, self.date_row, 
                self.description_field, self.recurrence_checkbox, self.recurrence_dropdown
            ], tight=True, spacing=15),
            padding=ft.padding.only(top=10)
        )

        self.actions = [
            ft.OutlinedButton(
                content=ft.Text(t("transaction_form_cancel", "↩️ Volver"), color=COLOR_OCEANO, weight=ft.FontWeight.BOLD),
                on_click=self._close_modal,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), side=ft.BorderSide(1, COLOR_OCEANO))
            ),
            ft.FilledButton(
                content=ft.Text(t("transaction_form_update", "🔄 Actualizar") if self.is_editing else t("transaction_form_save", "💾 Guardar"), color=COLOR_BLANCO, weight=ft.FontWeight.BOLD),
                bgcolor=COLOR_OCEANO, on_click=self._on_save_click,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
            )
        ]
        self.actions_alignment = ft.MainAxisAlignment.SPACE_BETWEEN

    def _toggle_recurrence_dropdown(self, e):
        """Muestra u oculta el selector de frecuencias según la casilla de verificación."""
        self.recurrence_dropdown.visible = self.recurrence_checkbox.value
        self.recurrence_dropdown.update()

    def _on_date_change(self, e: ft.ControlEvent) -> None:
        if self.date_picker.value:
            self.date_field.value = self.date_picker.value.strftime("%d/%m/%Y")
        self._page.update()

    def _close_modal(self, e=None):
        self.open = False
        self._page.update()
        if self.on_cancel_callback: self.on_cancel_callback()

    def _on_save_click(self, e: ft.ControlEvent) -> None:
        if not self.amount_field.value or not self.amount_field.value.replace(".", "", 1).isdigit():
            self.amount_field.error_text = t("transaction_form_invalid_amount", "Ingresa un monto válido")
            self._page.update()
            return
        else:
            self.amount_field.error_text = None
        
        date_str = self.date_field.value
        try:
            db_date = datetime.datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            db_date = datetime.datetime.now().strftime("%Y-%m-%d")

        # Inyección de los nuevos parámetros hacia la firma adaptativa de la base de datos
        data = {
            "category_id": self.category_id,
            "payment_method_id": int(self.payment_method_dropdown.value),
            "amount": float(self.amount_field.value),
            "description": self.description_field.value,
            "type": self.transaction_type,
            "date": db_date,
            "recurrence_type": self.recurrence_dropdown.value if self.recurrence_checkbox.value else None,
            "is_recurrence_active": self.recurrence_checkbox.value
        }
        if self.is_editing: data["id"] = self.edit_id
        
        self.open = False
        self._page.update()
        self.on_save_callback(data)
        
class CategoryForm(ft.AlertDialog):
    """Formulario modular para crear o editar categorías."""
    def __init__(self, page: ft.Page, category: dict | None, on_save_callback: callable, on_cancel_callback: callable):
        super().__init__()
        self._page = page
        self.category = category
        self.is_editing = category is not None
        self.on_save_callback = on_save_callback
        self.on_cancel_callback = on_cancel_callback
        
        self.bgcolor = COLOR_CREMA
        self.shape = ft.RoundedRectangleBorder(radius=20)
        
        self.available_icons = list(SHARED_ICONS)
        self.selected_icon = self.category["icon"] if self.is_editing else "📦"
        if self.is_editing and self.selected_icon not in self.available_icons:
            self.available_icons.insert(0, self.selected_icon)
            
        self._setup_controls()

    def _setup_controls(self):
        self.title = ft.Text(t("three_panel_edit_card", "Editar Carta") if self.is_editing else t("three_panel_new_card", "Nueva Carta"), weight=ft.FontWeight.BOLD, color=COLOR_OCEANO, size=22)
        
        padding_estandar = ft.padding.symmetric(horizontal=12)
        alto_estandar = 62

        self.name_input = ft.TextField(
            label=t("three_panel_category_name", "Nombre de la categoría"), value=self.category["name"] if self.is_editing else "", 
            autofocus=True, bgcolor=COLOR_BLANCO, border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO), focused_border_color=COLOR_OCEANO,
            color=ft.Colors.BLACK, border_radius=10, label_style=ft.TextStyle(color=ft.Colors.GREY_600), 
            content_padding=padding_estandar, height=alto_estandar
        )

        self.icons_grid = ft.Row(wrap=True, spacing=10, run_spacing=10, alignment=ft.MainAxisAlignment.CENTER)
        self._render_icons()

        # Ajuste de Tarjeta Premium para la grilla de iconos con fondo blanco y sombra sutil
        grid_container = ft.Container(
            content=ft.Column([self.icons_grid], scroll=ft.ScrollMode.AUTO), 
            height=180, 
            bgcolor=COLOR_BLANCO,
            border=ft.border.all(1, ft.Colors.with_opacity(0.08, COLOR_CIAN)), 
            border_radius=12, 
            padding=10,
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=8, color=ft.Colors.with_opacity(0.02, ft.Colors.BLACK), offset=ft.Offset(0, 3))
        )

        self.content = ft.Container(
            content=ft.Column([
                self.name_input, ft.Container(height=2),
                ft.Text(t("three_panel_select_icon", "Selecciona un ícono:"), weight=ft.FontWeight.W_600, size=13, color=COLOR_OCEANO),
                grid_container
            ], tight=True, width=350, spacing=10),
            padding=ft.padding.only(top=5)
        )

        self.actions = [
            ft.OutlinedButton(
                content=ft.Text(t("three_panel_cancel", "Volver"), color=COLOR_OCEANO, weight=ft.FontWeight.BOLD),
                on_click=self._close, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), side=ft.BorderSide(1, COLOR_OCEANO))
            ),
            ft.FilledButton(
                content=ft.Text(t("three_panel_save", "Guardar"), color=COLOR_BLANCO, weight=ft.FontWeight.BOLD),
                bgcolor=COLOR_OCEANO, on_click=self._save, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
            )
        ]
        self.actions_alignment = ft.MainAxisAlignment.SPACE_BETWEEN

    def _render_icons(self):
        self.icons_grid.controls.clear()
        for icon_str in self.available_icons:
            is_selected = icon_str == self.selected_icon
            btn = ft.Container(
                content=ft.Text(icon_str, size=24), padding=8, border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.08, COLOR_OCEANO) if is_selected else ft.Colors.TRANSPARENT,
                border=ft.border.all(2, COLOR_OCEANO) if is_selected else ft.border.all(1, ft.Colors.TRANSPARENT),
                shadow=None, data=icon_str, on_click=self._select_icon
            )
            self.icons_grid.controls.append(btn)

    def _select_icon(self, e):
        self.selected_icon = e.control.data
        self._render_icons()
        self.icons_grid.update()

    def _close(self, e=None):
        self.open = False
        self._page.update()
        if self.on_cancel_callback: self.on_cancel_callback()

    def _save(self, e):
        if not self.name_input.value.strip():
            self.name_input.error_text = t("three_panel_name_required", "El nombre es obligatorio")
            self.name_input.update()
            return
            
        data = {
            "name": self.name_input.value.strip(),
            "icon": self.selected_icon,
            "color": "#95A5A6" 
        }
        if self.is_editing:
            data["id"] = self.category["id"]
            
        self.open = False
        self._page.update()
        self.on_save_callback(data)


class TemplateForm(ft.AlertDialog):
    """Formulario modular para crear plantillas rápidas."""
    def __init__(self, page: ft.Page, category_type: str, category_group_name: str, on_save_callback: callable, on_cancel_callback: callable):
        super().__init__()
        self._page = page
        self.category_type = category_type
        self.category_group_name = category_group_name
        self.on_save_callback = on_save_callback
        self.on_cancel_callback = on_cancel_callback
        
        self.bgcolor = COLOR_CREMA
        self.shape = ft.RoundedRectangleBorder(radius=20)
        
        self.available_icons = list(SHARED_ICONS)
        self.selected_icon = "⚡"
        
        self._setup_controls()

    def _setup_controls(self):
        self.title = ft.Text(t("gastos_add_template_title", "Nueva Plantilla"), weight=ft.FontWeight.BOLD, color=COLOR_OCEANO, size=22)
        
        padding_estandar = ft.padding.symmetric(horizontal=12)
        alto_estandar = 62

        self.name_input = ft.TextField(
            label=t("gastos_template_name", "Nombre de Plantilla"), 
            bgcolor=COLOR_BLANCO, border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO), focused_border_color=COLOR_OCEANO,
            color=ft.Colors.BLACK, border_radius=10, label_style=ft.TextStyle(color=ft.Colors.GREY_600), 
            content_padding=padding_estandar, height=alto_estandar
        )
        
        self.amount_input = ft.TextField(
            label=t("gastos_template_amount", "Monto Fijo"), 
            keyboard_type=ft.KeyboardType.NUMBER, hint_text="0.00", prefix=ft.Text("$ ", color=COLOR_OCEANO, weight=ft.FontWeight.BOLD),
            bgcolor=COLOR_BLANCO, border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO), focused_border_color=COLOR_OCEANO,
            color=ft.Colors.BLACK, border_radius=10, label_style=ft.TextStyle(color=ft.Colors.GREY_600), 
            content_padding=padding_estandar, height=alto_estandar
        )
        
        cats_in_group = get_categories_by_group(self.category_group_name, self.category_type)
        
        generic_text = t("gastos_template_generic", "Genérico").replace("✨", "").strip()
        translated_group = t(f"tab_{self.category_group_name.lower().replace(' ', '_')}", self.category_group_name)
        generic_full_name = f"{generic_text} ({translated_group})"

        generic_cat = next((c for c in cats_in_group if generic_full_name.lower() in str(c["name"]).lower()), None)
        cat_options = []
        
        if generic_cat:
            clean_db_name = generic_cat["name"].replace("✨", "").strip()
            cat_options.append(ft.dropdown.Option(key=str(generic_cat["id"]), text=f"{generic_cat['icon']} {clean_db_name}"))
        else:
            cat_options.append(ft.dropdown.Option(key="generic_create", text=f"✨ {generic_full_name}"))
            
        for c in cats_in_group:
            if generic_cat and c["id"] == generic_cat["id"]: continue
            cat_name_translated = t(str(c["name"]).lower().replace(" ", "_"), default=c["name"]).replace("✨", "").strip()
            cat_options.append(ft.dropdown.Option(key=str(c["id"]), text=f"{c['icon']} {cat_name_translated}"))
        
        self.category_dropdown = ft.Dropdown(
            label=t("gastos_template_associate_category", "Asociar a Categoría"), 
            options=cat_options,
            value=str(generic_cat["id"]) if generic_cat else "generic_create", 
            bgcolor=COLOR_BLANCO, border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO), focused_border_color=COLOR_OCEANO,
            color=ft.Colors.BLACK, border_radius=10, label_style=ft.TextStyle(color=ft.Colors.GREY_600), 
            content_padding=padding_estandar, height=alto_estandar
        )

        self.icons_grid = ft.Row(wrap=True, spacing=10, run_spacing=10, alignment=ft.MainAxisAlignment.CENTER)
        self._render_icons()

        grid_container = ft.Container(
            content=ft.Column([self.icons_grid], scroll=ft.ScrollMode.AUTO), 
            height=180, 
            bgcolor=COLOR_BLANCO,
            border=ft.border.all(1, ft.Colors.with_opacity(0.08, COLOR_CIAN)), 
            border_radius=12, 
            padding=10,
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=8, color=ft.Colors.with_opacity(0.02, ft.Colors.BLACK), offset=ft.Offset(0, 3))
        )

        self.content = ft.Container(
            content=ft.Column([
                self.name_input, self.amount_input, self.category_dropdown, 
                ft.Text(t("gastos_template_icon", "Icono:"), color=COLOR_OCEANO, weight=ft.FontWeight.W_600, size=13), 
                grid_container
            ], tight=True, width=350, spacing=10),
            padding=ft.padding.only(top=5)
        )
        
        self.actions = [
            ft.OutlinedButton(
                content=ft.Text(t("three_panel_cancel", "Volver"), color=COLOR_OCEANO, weight=ft.FontWeight.BOLD),
                on_click=self._close, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), side=ft.BorderSide(1, COLOR_OCEANO))
            ),
            ft.FilledButton(
                content=ft.Text(t("gastos_template_save", "Guardar"), color=COLOR_BLANCO, weight=ft.FontWeight.BOLD),
                bgcolor=COLOR_OCEANO, on_click=self._save, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
            )
        ]
        self.actions_alignment = ft.MainAxisAlignment.SPACE_BETWEEN

    def _render_icons(self):
        self.icons_grid.controls.clear()
        for icon_str in self.available_icons:
            is_selected = icon_str == self.selected_icon
            btn = ft.Container(
                content=ft.Text(icon_str, size=24), padding=8, border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.08, COLOR_OCEANO) if is_selected else ft.Colors.TRANSPARENT,
                border=ft.border.all(2, COLOR_OCEANO) if is_selected else ft.border.all(1, ft.Colors.TRANSPARENT),
                shadow=None, data=icon_str, on_click=self._select_icon
            )
            self.icons_grid.controls.append(btn)

    def _select_icon(self, e):
        self.selected_icon = e.control.data
        self._render_icons()
        self.icons_grid.update()

    def _close(self, e=None):
        self.open = False
        self._page.update()
        if self.on_cancel_callback: self.on_cancel_callback()

    def _save(self, e):
        cat_val = self.category_dropdown.value
        cat_id = None
        
        if cat_val == "generic_create":
            from database.connection import add_category, get_categories_by_group
            generic_text = t("gastos_template_generic", "Genérico").replace("✨", "").strip()
            translated_group = t(f"tab_{self.category_group_name.lower().replace(' ', '_')}", self.category_group_name)
            new_name = f"{generic_text} ({translated_group})"
            
            add_category(new_name, "✨", COLOR_OCEANO, self.category_type, self.category_group_name)
            
            updated_cats = get_categories_by_group(self.category_group_name, self.category_type)
            new_cat = next((c for c in updated_cats if c["name"] == new_name), None)
            if new_cat:
                cat_id = new_cat["id"]
        else:
            cat_id = int(cat_val) if cat_val else None

        data = {
            "name": self.name_input.value, 
            "icon": self.selected_icon, 
            "default_amount": float(self.amount_input.value or 0),
            "color": COLOR_OCEANO,
            "type": self.category_type,
            "category_id": cat_id
        }
        self.open = False
        self._page.update()
        self.on_save_callback(data)

class ExecuteTemplateForm(ft.AlertDialog):
    """Formulario modular para ejecutar una plantilla y registrar la transacción."""
    def __init__(self, page: ft.Page, template: dict, category_type: str, fallback_category_id: int, on_save_callback: callable, on_cancel_callback: callable):
        super().__init__()
        self._page = page
        self.template = template
        self.category_type = category_type
        self.fallback_category_id = fallback_category_id
        self.on_save_callback = on_save_callback
        self.on_cancel_callback = on_cancel_callback
        
        self.bgcolor = COLOR_CREMA
        self.shape = ft.RoundedRectangleBorder(radius=20)
        
        self._setup_controls()

    def _setup_controls(self):
        title_text = t("transaction_form_apply_template", "Aplicar: {name}").replace("{name}", self.template['name'])
        self.title = ft.Text(title_text, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO, size=22)
        
        padding_estandar = ft.padding.symmetric(horizontal=12)
        alto_estandar = 62

        db_methods = get_payment_methods()
        
        options = [
            ft.dropdown.Option(
                key=str(m["id"]), 
                text=f"{m['icon']} {t(str(m['name']).lower().strip().replace(' ', '_'), default=m['name'])}"
            ) 
            for m in db_methods
        ]
        
        self.payment_method_dropdown = ft.Dropdown(
            label=t("transaction_form_payment_method", "Método de Pago"), 
            options=options,
            value=str(db_methods[0]["id"]) if db_methods else None,
            bgcolor=COLOR_BLANCO, border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO), focused_border_color=COLOR_OCEANO,
            color=ft.Colors.BLACK, border_radius=10, label_style=ft.TextStyle(color=ft.Colors.GREY_600), 
            content_padding=padding_estandar, height=alto_estandar,
            autofocus=True
        )

        amount_text = t("transaction_form_amount_to_register", "Monto a registrar: ${amount}").replace("{amount}", f"{self.template['default_amount']:.2f}")

        self.content = ft.Container(
            content=ft.Column([
                ft.Text(amount_text, size=16, color=COLOR_OCEANO, weight="bold"),
                self.payment_method_dropdown
            ], tight=True, spacing=15),
            padding=ft.padding.only(top=5)
        )
        
        self.actions = [
            ft.OutlinedButton(
                content=ft.Text(t("three_panel_cancel", "Volver"), color=COLOR_OCEANO, weight=ft.FontWeight.BOLD),
                on_click=self._close, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), side=ft.BorderSide(1, COLOR_OCEANO))
            ),
            ft.FilledButton(
                content=ft.Text(t("transaction_form_register_button", "Registrar"), color=COLOR_BLANCO, weight=ft.FontWeight.BOLD),
                bgcolor=COLOR_OCEANO, on_click=self._save, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
            )
        ]
        self.actions_alignment = ft.MainAxisAlignment.SPACE_BETWEEN

    def _close(self, e=None):
        self.open = False
        self._page.update()
        if self.on_cancel_callback: self.on_cancel_callback()

    def _save(self, e):
        cat_id = self.template.get("category_id")
        desc_default = t("transaction_form_quick_template_desc", "Plantilla rápida")
        dropdown_value = self.payment_method_dropdown.value
        
        data = {
            "category_id": cat_id if cat_id else self.fallback_category_id, 
            "payment_method_id": int(dropdown_value) if dropdown_value is not None else 1,
            "amount": float(self.template.get("default_amount", 0.0)),
            "description": self.template.get("name", desc_default),
            "type": self.category_type,
            "date": datetime.datetime.now().strftime("%Y-%m-%d")
        }
        self.open = False
        self._page.update()
        self.on_save_callback(data)