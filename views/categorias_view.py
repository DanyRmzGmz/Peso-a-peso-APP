"""
Vista de Categorías de la aplicación.
Permite visualizar favoritos, plantillas rápidas y desglosar flujos por sub-grupos.
Refactorizado con sombras difuminadas, tipografía escalada y limpieza monetaria dinámica.
"""
import flet as ft
from datetime import datetime
from core.colors import COLOR_OCEANO, COLOR_BLANCO, COLOR_CREMA, COLOR_CIAN, COLOR_ATARDECER
from core.formatters import format_currency
from core.translations import t

from database.connection import (
    get_categories_by_group, add_category, update_category, delete_category,
    save_transaction, toggle_category_favorite, get_favorite_categories,
    get_templates, add_template, delete_template, get_active_recurrences, disable_recurrence,
    process_recurring_transactions, update_transaction,get_setting
)

from components.forms import TransactionForm, CategoryForm, TemplateForm, ExecuteTemplateForm

class CategoriasView:
    def __init__(self, page: ft.Page, category_group_name: str, category_type: str):
        self.page = page
        self.category_group_name = category_group_name
        self.category_type = category_type
        self.view_type = category_type
        
        self.favorites_container = ft.Row(wrap=False, scroll=ft.ScrollMode.AUTO, spacing=15)
        self.templates_container = ft.Row(wrap=False, scroll=ft.ScrollMode.AUTO, spacing=15)
        self.category_buttons_container = ft.Row(wrap=True, spacing=20, run_spacing=20)
        
        self.main_container = self.build_content()
        self.refresh_all()

    def _clean_decimals(self, currency_str: str) -> str:
        """Remueve los decimales de la cadena formateada únicamente si terminan en .00"""
        if currency_str.endswith(".00"):
            return currency_str[:-3]
        return currency_str

    def build_content(self):
        btn_add_template = ft.Container(
            content=ft.Text("+", size=32, weight="bold", color=COLOR_OCEANO),
            on_click=lambda _: self._show_template_form(),
            padding=ft.padding.symmetric(horizontal=12, vertical=4), 
            ink=True, 
            border_radius=8,
            border=ft.border.all(1, ft.Colors.with_opacity(0.1, COLOR_OCEANO)),
            bgcolor=COLOR_BLANCO
        )

        self.content_column = ft.Column([
            ft.Text(t("gastos_favorites_title", default="⭐ Mis Favoritos"), size=18, weight="bold", color=COLOR_OCEANO),
            ft.Container(content=self.favorites_container, height=145, padding=ft.padding.only(bottom=10)),
            
            ft.Row([
                ft.Text(t("gastos_templates_title", default="⚡ Plantillas Rápidas"), size=18, weight="bold", color=COLOR_OCEANO),
                btn_add_template
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            
            ft.Container(content=self.templates_container, height=95, padding=ft.padding.only(bottom=10)),
            
            ft.Divider(height=25, color=ft.Colors.with_opacity(0.1, COLOR_CIAN)),
            
            ft.Text(t("gastos_all_categories", default="📂 Todas las Categorías"), size=18, weight="bold", color=COLOR_OCEANO),
            self.category_buttons_container,
            
            ft.Divider(height=25, color=ft.Colors.TRANSPARENT), 
            self.build_recurrences_section()
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=12)

        return self.content_column

    def refresh_all(self):
        try:
            process_recurring_transactions()
        except Exception as ex:
            print(f"[Categorías] Error sincronizando recurrencias: {ex}")

        self._render_favorites()
        self._render_templates() 
        self._render_category_cards()

        if hasattr(self, "content_column") and len(self.content_column.controls) > 0:
            self.content_column.controls[-1] = self.build_recurrences_section()
        if self.page:
            self.page.update()

    def _render_favorites(self):
        favs = get_favorite_categories(self.category_type)
        self.favorites_container.controls.clear()
        if not favs:
            self.favorites_container.controls.append(
                ft.Container(
                    content=ft.Text(t("gastos_no_favorites", "No hay favoritos"), color=ft.Colors.GREY_500, italic=True, size=14),
                    padding=ft.padding.only(top=20)
                )
            )
        else:
            favs.sort(key=lambda x: t(str(x["name"]).lower().replace(" ", "_"), default=x["name"]).lower())

            for fav in favs:
                name = t(str(fav["name"]).lower().replace(" ", "_"), default=fav["name"])
                card = self._create_simple_card(fav["icon"], name, lambda _, f=fav: self._show_transaction_form(f), border_color=ft.Colors.AMBER_300)
                btn_unfav = ft.Container(
                    content=ft.Text("★", size=22, color=ft.Colors.AMBER_500), 
                    on_click=lambda e, cid=fav["id"]: self._toggle_fav(cid, False), 
                    padding=6, ink=True, left=4, top=4
                )
                self.favorites_container.controls.append(ft.Stack([card, btn_unfav], width=130, height=130))
        self.page.update()

    def _render_templates(self):
        templates = get_templates(type_=self.category_type) 
        self.templates_container.controls.clear()
        if not templates:
            self.templates_container.controls.append(
                ft.Container(
                    content=ft.Text(t("gastos_no_templates", "No hay plantillas"), color=ft.Colors.GREY_500, italic=True, size=14),
                    padding=ft.padding.only(top=15)
                )
            )
        else:
            templates.sort(key=lambda x: float(x.get("default_amount", 0.0)))

            for temp in templates:
                btn_close = ft.Container(
                    content=ft.Text("❌", size=9, color=ft.Colors.GREY_500), 
                    on_click=lambda _, tid=temp["id"]: self._delete_template(tid), 
                    padding=6, border_radius=4, ink=True, right=4, top=4
                )
                self.templates_container.controls.append(
                    ft.Stack([
                        self._create_template_card(temp["icon"], temp["name"], lambda _, t_val=temp: self._show_exec_template_form(t_val), temp['default_amount']),
                        btn_close
                    ], width=225, height=75)
                )
        self.page.update()

    def _render_category_cards(self):
        categories = get_categories_by_group(self.category_group_name, self.category_type)
        self.category_buttons_container.controls.clear()
        
        for cat in categories:
            is_fav = bool(cat.get("is_favorite", False))
            name = t(str(cat["name"]).lower().replace(" ", "_"), default=cat["name"])
            
            card = self._create_simple_card(cat["icon"], name, lambda _, c=cat: self._show_transaction_form(c))
            btn_fav = ft.Container(
                content=ft.Text("★" if is_fav else "☆", size=22, color=ft.Colors.AMBER_500 if is_fav else ft.Colors.GREY_400),
                on_click=lambda e, cid=cat["id"], current_fav=is_fav: self._toggle_fav(cid, False if current_fav else True),
                padding=6, ink=True, left=4, top=4 
            )
            
            controls_stack = [card, btn_fav]
            if cat.get("is_custom"):
                btn_edit = ft.Container(content=ft.Text("✏️", size=13, color=COLOR_OCEANO), on_click=lambda e, c=cat: self._show_category_form(c), padding=4, ink=True)
                btn_delete = ft.Container(content=ft.Text("🗑️", size=13, color=COLOR_ATARDECER), on_click=lambda e, cid=cat["id"]: self._delete_custom_category(cid), padding=4, ink=True)
                controls_stack.append(ft.Container(content=ft.Row([btn_edit, btn_delete], spacing=2), right=6, top=6))

            self.category_buttons_container.controls.append(ft.Stack(controls_stack, width=130, height=130))

        self.category_buttons_container.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.Text("+", size=36, weight="bold", color=COLOR_OCEANO), 
                    ft.Text(t("three_panel_add_card", "Nueva"), size=13, weight="bold", color=COLOR_OCEANO)
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                width=130, height=130, 
                bgcolor=ft.Colors.with_opacity(0.04, COLOR_OCEANO), 
                border_radius=16, 
                border=ft.border.all(1, ft.Colors.with_opacity(0.12, COLOR_OCEANO)),
                on_click=lambda _: self._show_category_form(None)
            )
        )
        self.page.update()

    def _create_simple_card(self, icon, title, click_event, border_color=None):
        final_border = ft.border.all(1.5, border_color) if border_color else ft.border.all(1, ft.Colors.with_opacity(0.06, COLOR_CIAN))
        
        return ft.Container(
            content=ft.Column([
                ft.Text(icon, size=32),
                ft.Container(height=2),
                ft.Text(title, size=13, weight="bold", text_align=ft.TextAlign.CENTER, overflow=ft.TextOverflow.ELLIPSIS, color=ft.Colors.BLACK)
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1),
            width=130, height=130, 
            bgcolor=COLOR_BLANCO, 
            border_radius=16, 
            border=final_border, 
            ink=True, 
            on_click=click_event,
            padding=12, 
            tooltip=title,
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=10, color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK), offset=ft.Offset(0, 5))
        )

    def _create_template_card(self, icon, title, click_event, amount):
        str_amount = self._clean_decimals(format_currency(amount))
        
        return ft.Container(
            content=ft.Row([
                ft.Container(content=ft.Text(icon, size=26), padding=ft.padding.only(right=4, left=4)),
                ft.Column([
                    ft.Text(title, size=13, weight="bold", overflow=ft.TextOverflow.ELLIPSIS, width=135, color=ft.Colors.BLACK),
                    ft.Text(f"{str_amount}", size=13, color=COLOR_OCEANO, weight="bold")
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=1)
            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            width=225, height=75, 
            bgcolor=COLOR_BLANCO, 
            border_radius=14, 
            border=ft.border.all(1, ft.Colors.with_opacity(0.06, COLOR_CIAN)), 
            ink=True, 
            on_click=click_event,
            padding=10, 
            tooltip=title,
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=10, color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK), offset=ft.Offset(0, 5))
        )
    
    def build_recurrences_section(self):
        recurrences = get_active_recurrences(transaction_type=self.view_type)
        if not recurrences:
            return ft.Container()
            
        recurrence_cards = []
        for r in recurrences:
            freq_human = {
                "dia": t("frequency_daily", default="Diario"),
                "semana": t("frequency_weekly", default="Semanal"),
                "quincenal": t("frequency_biweekly", default="Quincenal"),
                "mes": t("frequency_monthly", default="Mensual"),
                "bimensual": t("frequency_bimonthly", default="Bimensual"),
                "trimestral": t("frequency_quarterly", default="Trimestral"),
                "semestral": t("frequency_semiannually", default="Semestral"),
                "anio": t("frequency_yearly", default="Anual")
            }.get(str(r["recurrence_type"]).lower().strip(), t("frequency_monthly", default="Mensual"))
            
            try:
                date_obj = datetime.strptime(r["date"][:10], "%Y-%m-%d")
                next_charge_str = date_obj.strftime("%d/%m/%Y")
            except Exception:
                next_charge_str = r["date"]

            raw_name = r["description"] if r["description"] else r["category_name"]
            translated_title = t(str(raw_name).lower().strip().replace(" ", "_"), default=raw_name)

            card = ft.Container(
                bgcolor=COLOR_BLANCO,
                padding=15,
                border_radius=14,
                width=280, 
                border=ft.border.all(1, ft.Colors.with_opacity(0.06, COLOR_CIAN)),
                shadow=ft.BoxShadow(spread_radius=0, blur_radius=10, color=ft.Colors.with_opacity(0.02, ft.Colors.BLACK), offset=ft.Offset(0, 4)),
                content=ft.Column([
                    ft.Row([
                        ft.Row([
                            ft.Text(r["category_icon"], size=20),
                            ft.Column([
                                ft.Text(translated_title, size=14, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Text(freq_human, size=11, color=COLOR_OCEANO, weight=ft.FontWeight.W_600)
                            ], spacing=1, width=120)
                        ], spacing=8),
                        ft.Text(f"{format_currency(r['amount'])}", size=15, weight=ft.FontWeight.BOLD, color=COLOR_ATARDECER if self.view_type == 'expense' else "#27AE60")
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    
                    ft.Divider(height=10, color=ft.Colors.BLACK12),
                    
                    ft.Row([
                        ft.Column([
                            ft.Text(t("recurrence_next_charge", default="Próximo cargo"), size=10, color=ft.Colors.GREY_500),
                            ft.Text(next_charge_str, size=11, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_800)
                        ], spacing=1),
                        ft.Row([
                            ft.IconButton(
                                icon=ft.Icons.EDIT_OUTLINED,
                                icon_color=COLOR_OCEANO,
                                icon_size=16,
                                tooltip=t("historial_edit", default="Editar parámetros"),
                                on_click=lambda e, trans=r: self._show_transaction_form(trans, is_edit_mode=True)
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CANCEL_OUTLINED, 
                                icon_color=COLOR_ATARDECER, 
                                icon_size=16,
                                tooltip=t("recurrence_disable", default="Cancelar suscripción"),
                                on_click=lambda e, rid=r["id"]: self._handle_disable_recurrence(rid)
                            )
                        ], spacing=0)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ], spacing=8)
            )
            recurrence_cards.append(card)

        icon_section = ft.Icons.LOOP_ROUNDED  
        title_section = t("title_active_recurrences_expense", default="Mis Gastos Recurrentes") if self.view_type == "expense" else t("title_active_recurrences_income", default="Mis Ingresos Recurrentes")

        return ft.Column([
            ft.Row([
                ft.Icon(icon_section, color=COLOR_OCEANO, size=20),
                ft.Text(title_section, size=18, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO)
            ], spacing=8),
            ft.Row(controls=recurrence_cards, wrap=True, spacing=15)
        ], spacing=12)
    
    def _handle_disable_recurrence(self, transaction_id):
        disable_recurrence(transaction_id)
        self.page.snack_bar = ft.SnackBar(content=ft.Text(t("recurrence_disabled_success", "Recurrencia cancelada con éxito")), bgcolor=ft.Colors.GREEN_700)
        self.page.snack_bar.open = True
        self.refresh_all()

    def _show_category_form(self, category: dict | None):
        def save_handler(data):
            if category: update_category(data["id"], data["name"], data["icon"], data["color"])
            else: add_category(data["name"], data["icon"], data["color"], self.category_type, self.category_group_name)
            self.refresh_all()

        form = CategoryForm(self.page, category, on_save_callback=save_handler, on_cancel_callback=None)

        # Recorrido recursivo para limitar el textfield del nombre a 25 caracteres
        def traverse_and_limit(control):
            if isinstance(control, ft.TextField):
                lbl = str(control.label).lower()
                if "nombre" in lbl or "name" in lbl or "categoría" in lbl or "category" in lbl:
                    control.max_length = 25
            
            if hasattr(control, "controls") and control.controls:
                for sub_c in control.controls:
                    traverse_and_limit(sub_c)
            if hasattr(control, "content") and control.content:
                traverse_and_limit(control.content)

        if hasattr(form, "content") and form.content:
            traverse_and_limit(form.content)

        self.page.overlay.append(form)
        form.open = True
        self.page.update()

    def _show_template_form(self):
        def save_handler(data):
            add_template(data)
            self.refresh_all()

        form = TemplateForm(self.page, self.category_type, self.category_group_name, on_save_callback=save_handler, on_cancel_callback=None)
        
        self._apply_form_patches(form)
        self.page.overlay.append(form)
        form.open = True
        self.page.update()

    def _show_exec_template_form(self, temp):
        cats = get_categories_by_group(self.category_group_name, self.category_type)
        target_category_id = temp.get("category_id")
        if not target_category_id:
            target_category_id = cats[0]["id"] if cats else 1
        
        def save_handler(data):
            save_transaction(**data)
            try:
                process_recurring_transactions()
            except Exception as ex:
                print(f"[Plantilla Inyección] Error en motor retroactivo: {ex}")

            self.page.snack_bar = ft.SnackBar(
                content=ft.Text("Transacción de plantilla guardada exitosamente"), 
                bgcolor=ft.Colors.GREEN_700
            )
            self.page.snack_bar.open = True
            self.refresh_all()

        form = ExecuteTemplateForm(self.page, temp, self.category_type, target_category_id, on_save_callback=save_handler, on_cancel_callback=None)
        
        self._apply_form_patches(form)
        self.page.overlay.append(form)
        form.open = True
        self.page.update()

    def _show_transaction_form(self, cat_or_trans, is_edit_mode=False):
        if is_edit_mode:
            transaction_id = cat_or_trans["id"]
            category_id = cat_or_trans["category_id"] 
            category_name = cat_or_trans["category_name"]
            
            def save_handler(data):
                update_data = {
                    "amount": data["amount"],
                    "description": data["description"],
                    "payment_method_id": data["payment_method_id"],
                    "date": data["date"]
                }
                update_transaction(transaction_id, update_data)
                
                from database.connection import update_recurrence_settings
                update_recurrence_settings(transaction_id, data["recurrence_type"], data["amount"], data["description"])
                
                try:
                    process_recurring_transactions()
                except Exception as ex:
                    print(f"[Categorías Edición] Error en motor retroactivo: {ex}")

                self.page.snack_bar = ft.SnackBar(ft.Text(t("three_panel_transaction_saved", "Cambios guardados con éxito")), bgcolor=ft.Colors.GREEN_700)
                self.page.snack_bar.open = True
                self.refresh_all()
                
            form = TransactionForm(
                self.page, category_id, category_name, self.category_type, 
                is_recurring_default=True, on_save_callback=save_handler, on_cancel_callback=None, edit_id=transaction_id
            )
        else:
            def save_handler(data):
                save_transaction(**data)
                try:
                    process_recurring_transactions()
                except Exception as ex:
                    print(f"Error en procesamiento inmediato: {ex}")
                    
                self.page.snack_bar = ft.SnackBar(ft.Text(t("three_panel_transaction_saved", "Guardado exitosamente")), bgcolor=ft.Colors.GREEN_700)
                self.page.snack_bar.open = True
                self.refresh_all()

            form = TransactionForm(
                self.page, cat_or_trans["id"], cat_or_trans["name"], self.category_type, 
                is_recurring_default=False, on_save_callback=save_handler, on_cancel_callback=None
            )

        self._apply_form_patches(form)

        self.page.overlay.append(form)
        form.open = True
        self.page.update()

    def _init_verify_dialog(self):
        pass

    def _toggle_fav(self, cid, is_favorite: bool):
        toggle_category_favorite(cid, is_favorite)
        self.refresh_all()

    def _delete_custom_category(self, cat_id: int):
        delete_category(cat_id)
        self.refresh_all()
        self.page.snack_bar = ft.SnackBar(content=ft.Text(t("three_panel_card_deleted", "Carta eliminada con éxito.")), bgcolor=ft.Colors.RED_700)
        self.page.snack_bar.open = True
        self.page.update()

    def _delete_template(self, tid: int):
        delete_template(tid)
        self.refresh_all()
    
    def _apply_form_patches(self, form):
        """
        Aplica parches dinámicos en tiempo de ejecución a los controles de los formularios
        para restringir montos, traducir opciones de Efectivo y personalizar etiquetas de ingreso.
        """
        lang = get_setting("language", "es")
        
        def traverse_and_patch(control):
            # 1. Restringir campo de Monto para aceptar únicamente números y decimales limpios con máximo de 25 caracteres
            if isinstance(control, ft.TextField):
                lbl = str(control.label).lower()
                if "monto" in lbl or "amount" in lbl:
                    control.input_filter = ft.InputFilter(allow=True, regex_string=r"^[0-9]*(?:\.[0-9]*)?$")
                    control.max_length = 25
                elif "nombre" in lbl or "name" in lbl or "plantilla" in lbl or "template" in lbl:
                    control.max_length = 25
            
            # 2 y 3. Traducir opciones de Efectivo y personalizar etiqueta de método de ingreso
            elif isinstance(control, ft.Dropdown):
                lbl = str(control.label).lower()
                if "método" in lbl or "method" in lbl or "payment" in lbl:
                    if self.category_type == "income":
                        control.label = t("form_income_method", default="Método de ingreso" if lang == "es" else "Income Method")
                
                if control.options:
                    for opt in control.options:
                        opt_txt = str(opt.text).strip().lower()
                        if opt_txt == "efectivo" and lang == "en":
                            opt.text = "Cash"
                        elif opt_txt == "cash" and lang == "es":
                            opt.text = "Efectivo"

            # Recorrido recursivo seguro del árbol de controles de Flet
            if hasattr(control, "controls") and control.controls:
                for sub_c in control.controls:
                    traverse_and_patch(sub_c)
            if hasattr(control, "content") and control.content:
                traverse_and_patch(control.content)

        if hasattr(form, "content") and form.content:
            traverse_and_patch(form.content)
        

def create_categorias_view(page: ft.Page, category_group_name: str, category_type: str) -> ft.Column:
    view = CategoriasView(page, category_group_name, category_type)
    return view.main_container