"""
Vista de Historial de la aplicación.
Permite filtrar movimientos por periodos, cuentas y visualizar métricas y gráficas avanzadas.
Refactorizado con tipografía premium, soporte de gradiente y traducción en celdas dinámicas.
"""
import flet as ft
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import io
import base64
import csv
import os
from datetime import datetime, timedelta
import calendar
from core.colors import COLOR_OCEANO, COLOR_ATARDECER, COLOR_CREMA, COLOR_BLANCO, COLOR_ARENA, COLOR_CIAN, GRADIENTE_FONDO_SUAVE
from core.formatters import format_currency
from core.translations import t
from database.connection import (
    get_filtered_transactions,
    get_sum_income,
    get_sum_expenses,
    get_daily_trend,
    get_monthly_trend,
    get_historical_balance,
    get_transaction_by_id,
    update_transaction,
    delete_transaction,
    get_payment_methods,
    get_expenses_by_category_summary,
    get_income_by_category_summary,
    get_setting,
    get_balance_by_payment_method,
    process_recurring_transactions,
    get_connection
)

class HistorialView:
    def __init__(self, page: ft.Page):
        self.page = page
        self.current_filter = "Mes"
        self.selected_month = str(datetime.now().month)
        self.selected_year = str(datetime.now().year)
        self.selected_table_type = "Todos"
        self.selected_payment_method_id = None 
        self.selected_chart_tab = 0 
        
        # Estados de control para ordenación interactiva
        self.sort_column = "date"
        self.date_sort_desc = True
        self.amount_sort_desc = True
        
        self.search_query = ""
        self.current_page = 1
        self.rows_per_page = int(get_setting("table_rows_per_page", "10")) 
        
        self.show_only_recurring = False
        
        self.header_container = ft.Container()
        self.chips_container = ft.Container(margin=ft.margin.only(bottom=10))
        self.kpi_container = ft.Container()
        self.chart_container = ft.Container()
        self.table_container = ft.Container()
        self.show_chart_filter = False
                
        self.setup_ui()

    def _clean_decimals(self, currency_str: str) -> str:
        """Remueve los decimales de la cadena formateada únicamente si terminan en .00"""
        if currency_str.endswith(".00"):
            return currency_str[:-3]
        return currency_str

    def _get_localized_month_name(self, month_int: int) -> str:
        """Devuelve el nombre del mes adaptado al idioma actual configurado."""
        months_es = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        months_en = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        lang = get_setting("language", "es")
        if lang == "es":
            return months_es[month_int - 1]
        return months_en[month_int - 1]

    def setup_ui(self):
        self.header_container.content = self.build_header()
        self.chips_container.content = self.build_payment_method_chips()
        self.kpi_container.content = self.build_kpi_section()
        self.chart_container.content = self.build_chart_section()
        self.table_container.content = self.build_transactions_layout()
        
        self.update_transactions_data() 

        self.main_column = ft.Column(
            controls=[
                self.header_container,
                self.chips_container,
                self.kpi_container,
                self.chart_container,
                self.table_container
            ],
            spacing=20,
            expand=True,
            scroll=ft.ScrollMode.AUTO
        )

        center_wrapper = ft.Container(
            content=self.main_column,
            width=1300, 
            alignment=ft.Alignment(0, -1),
        )

        self.main_container = ft.Container(
            gradient=GRADIENTE_FONDO_SUAVE,
            expand=True,
            padding=20,
            alignment=ft.Alignment(0, -1), 
            content=center_wrapper
        )

    def get_view(self) -> ft.Container:
        """Devuelve el contenedor principal estructurado de la vista."""
        return self.main_container

    def export_csv_to_desktop(self, e):
        """Genera el CSV usando el filtro actual y la ruta de la configuración."""
        transactions = self.get_current_filtered_transactions()
        if not transactions:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("historial_no_chart_data")), bgcolor=ft.Colors.RED_700)
            self.page.snack_bar.open = True
            self.page.update()
            return
            
        try:
            ruta_saved = get_setting("export_path", "")
            if ruta_saved and os.path.exists(ruta_saved):
                directorio = ruta_saved
            else:
                directorio = os.path.join(os.path.expanduser("~"), "Desktop")
            
            tipo_filtro = self.selected_table_type.lower()
            timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M")
            file_name = f"movimientos_{tipo_filtro}_{timestamp}.csv"
            file_path = os.path.join(directorio, file_name)
            
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["Fecha", "Tipo", "Categoría", "Descripción", "Metodo de Pago", "Monto"])
                
                for trans in transactions:
                    tipo_str = "Egreso" if trans["type"] == "expense" else "Ingreso"
                    is_rec = int(trans.get("is_recurrence_active", 0)) in [1, 2]
                    prefix = "🔄 " if is_rec else ""
                    desc_final = f"{prefix}{trans['description']}" if trans["description"] else trans["category_name"]
                    clean_amount = self._clean_decimals(str(trans["amount"]))
                    
                    raw_method = trans.get("payment_method_name") or t("deudas_unknown_account", default="Desconocido")
                    writer.writerow([
                        trans["date"], tipo_str, trans["category_name"],
                        desc_final, raw_method, clean_amount
                    ])
                    
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("historial_csv_saved").format(directory=directorio)), bgcolor=ft.Colors.GREEN_700)
            self.page.snack_bar.open = True
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(f"Error al guardar: {str(ex)}"), bgcolor=ft.Colors.RED_700)
            self.page.snack_bar.open = True
            
        self.page.update()

    def on_search_change(self, e):
        """Manejador reactivo para cambios en el cuadro de búsqueda."""
        self.search_query = e.control.value.strip().lower()
        self.current_page = 1 
        self.update_view()

    def change_page(self, delta, total_pages):
        value_page = self.current_page + delta
        if 1 <= value_page <= total_pages:
            self.current_page = value_page
            self.update_transactions_data()

    def build_header(self):
        botones_principales = ft.Row(
            controls=[
                self.create_filter_button("Mes", t("historial_filter_month")),
                self.create_filter_button("Año", t("historial_filter_year")),
                self.create_filter_button("Histórico", t("historial_filter_historical")),
            ],
            spacing=10
        )
        filtros_secundarios = self.build_filters()
        return ft.Row(
            controls=[botones_principales, filtros_secundarios],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

    def create_filter_button(self, filter_key, label_text):
        is_selected = self.current_filter == filter_key
        return ft.Container(
            content=ft.Text(label_text, color=COLOR_BLANCO if is_selected else COLOR_OCEANO, weight=ft.FontWeight.BOLD),
            padding=ft.padding.symmetric(horizontal=15, vertical=8),
            bgcolor=COLOR_OCEANO if is_selected else COLOR_BLANCO,
            border_radius=8,
            border=ft.border.all(1, COLOR_OCEANO),
            on_click=lambda e: self.change_filter(filter_key),
            ink=True
        )

    def change_filter(self, new_filter_key):
        self.current_filter = new_filter_key
        self.current_page = 1 
        self.header_container.content = self.build_header()
        self.header_container.update()
        self.update_view()

    def build_filters(self):
        # PUNTO 2: Obtener únicamente años con movimientos financieros reales en la Base de Datos
        active_years = {datetime.now().year}
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT substr(date, 1, 4) as y FROM transactions WHERE date IS NOT NULL AND date != '1900-01-01'
                UNION
                SELECT DISTINCT substr(date, 1, 4) as y FROM transfers WHERE date IS NOT NULL
            """)
            for row in cursor.fetchall():
                if row[0] and row[0].isdigit():
                    active_years.add(int(row[0]))
            conn.close()
        except:
            pass
        
        sorted_years = sorted(list(active_years))
        years_options = [ft.dropdown.Option(key=str(y), text=str(y)) for y in sorted_years]

        if self.current_filter == "Mes":
            months = [ft.dropdown.Option(key=str(i), text=self._get_localized_month_name(i)) for i in range(1, 13)]
            
            self.dropdown_mes = ft.Dropdown(
                label=t("historial_filter_month"), 
                options=months, 
                value=self.selected_month, 
                width=150, height=30,
                text_size=14,
                content_padding=ft.padding.symmetric(horizontal=10, vertical=0),
                bgcolor=COLOR_BLANCO
            )
            self.dropdown_ano = ft.Dropdown(
                label=t("historial_filter_year"), 
                options=years_options, 
                value=self.selected_year, 
                width=150, height=30,
                text_size=14,
                content_padding=ft.padding.symmetric(horizontal=10, vertical=0),
                bgcolor=COLOR_BLANCO
            )
            btn_aplicar = ft.OutlinedButton(
                content=ft.Row([ft.Text("🔍"), ft.Text(t("historial_apply"), color=COLOR_OCEANO, weight=ft.FontWeight.BOLD)]), 
                on_click=self.apply_filters, 
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), side=ft.BorderSide(1, COLOR_OCEANO))
            )
            return ft.Row(controls=[self.dropdown_mes, self.dropdown_ano, btn_aplicar], spacing=15, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            
        elif self.current_filter == "Año":
            self.dropdown_ano = ft.Dropdown(
                label=t("historial_filter_year"), 
                options=years_options, 
                value=self.selected_year, 
                width=150, height=30,
                text_size=14,
                content_padding=ft.padding.symmetric(horizontal=10, vertical=0),
                bgcolor=COLOR_BLANCO
            )
            btn_aplicar = ft.OutlinedButton(
                content=ft.Row([ft.Text("🔍"), ft.Text(t("historial_apply"), color=COLOR_OCEANO, weight=ft.FontWeight.BOLD)]), 
                on_click=self.apply_filters, 
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), side=ft.BorderSide(1, COLOR_OCEANO))
            )
            return ft.Row(controls=[self.dropdown_ano, btn_aplicar], spacing=15, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            
        return ft.Container()

    def build_payment_method_chips(self):
        methods = get_payment_methods()
        chips = []

        is_all_selected = self.selected_payment_method_id is None
        chips.append(
            ft.Container(
                content=ft.Text(f"🏦 {t('historial_all_accounts')}", color=COLOR_BLANCO if is_all_selected else COLOR_OCEANO, weight=ft.FontWeight.BOLD), 
                padding=ft.padding.symmetric(horizontal=15, vertical=8),
                bgcolor=COLOR_OCEANO if is_all_selected else COLOR_BLANCO,
                border_radius=20,
                border=ft.border.all(1, COLOR_OCEANO),
                on_click=lambda e: self.change_payment_method(None),
                ink=True
            )
        )

        efectivo = [m for m in methods if m["type"] == "cash"]
        credito = [m for m in methods if m["type"] == "card"]
        debito = [m for m in methods if m["type"] == "bank_account"]
        ordered_methods = efectivo + credito + debito

        for m in ordered_methods:
            is_selected = self.selected_payment_method_id == m["id"]
            is_frozen = m.get("status") == "frozen"
            icon = m.get("icon") or "💳"
            name = t(str(m.get("name")).lower().replace(" ", "_"), default=m.get("name"))
            
            if is_frozen:
                name = f"{name} ❄️"
            
            if is_selected:
                bgcolor = COLOR_OCEANO
                text_color = COLOR_BLANCO
                border_color = COLOR_OCEANO
            elif is_frozen:
                bgcolor = ft.Colors.BLUE_50
                text_color = ft.Colors.BLUE_GREY_700
                border_color = ft.Colors.BLUE_300
            else:
                bgcolor = COLOR_BLANCO
                text_color = COLOR_OCEANO
                border_color = COLOR_OCEANO
            
            chips.append(
                ft.Container(
                    content=ft.Text(f"{icon} {name}", color=text_color, weight=ft.FontWeight.BOLD),
                    padding=ft.padding.symmetric(horizontal=15, vertical=8),
                    bgcolor=bgcolor,
                    border_radius=20,
                    border=ft.border.all(1, border_color),
                    on_click=lambda e, method_id=m["id"]: self.change_payment_method(method_id),
                    ink=True
                )
            )
        return ft.Row(controls=chips, scroll=ft.ScrollMode.AUTO, spacing=10)

    def change_payment_method(self, method_id):
        self.selected_payment_method_id = method_id
        self.current_page = 1 
        self.chips_container.content = self.build_payment_method_chips()
        self.chips_container.update()
        self.update_view()
        
    def apply_filters(self, e):
        if self.current_filter == "Mes" and hasattr(self, 'dropdown_mes'):
            if self.dropdown_mes.value: self.selected_month = self.dropdown_mes.value
        if hasattr(self, 'dropdown_ano') and self.dropdown_ano.value:
            self.selected_year = self.dropdown_ano.value
        self.current_page = 1 
        self.update_view()

    def get_date_range(self):
        if self.current_filter == "Mes":
            start_date = f"{self.selected_year}-{int(self.selected_month):02d}-01"
            if int(self.selected_month) == 12:
                end_date = f"{int(self.selected_year) + 1}-01-01"
            else:
                end_date = f"{self.selected_year}-{int(self.selected_month) + 1:02d}-01"
            return start_date, end_date
        elif self.current_filter == "Año":
            return f"{self.selected_year}-01-01", f"{int(self.selected_year) + 1}-01-01"
        else:
            # PUNTOS 1: Escaneo interactivo de la fecha más lejana real en la BD para evitar el fallback 1900
            start_date = "2024-01-01"  # Fallback seguro por diseño
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MIN(d) FROM (
                        SELECT MIN(date) as d FROM transactions WHERE date IS NOT NULL AND date != '1900-01-01' AND is_recurrence_active != 1
                        UNION
                        SELECT MIN(date) as d FROM transfers WHERE date IS NOT NULL
                    ) WHERE d IS NOT NULL
                """)
                row = cursor.fetchone()
                if row and row[0]:
                    start_date = row[0][:10]
                conn.close()
            except:
                pass
            end_date = f"{datetime.now().year + 5}-01-01"
            return start_date, end_date
            
    def get_filter_start_date(self):
        if self.current_filter == "Mes": return f"{self.selected_year}-{int(self.selected_month):02d}-01"
        elif self.current_filter == "Año": return f"{self.selected_year}-01-01"
        return None

    def build_kpi_section(self):
        """Calcula y construye la sección de KPIs aplicando exclusión macro condicional ante transferencias propias."""
        transactions = self.get_current_filtered_transactions()
        methods = get_payment_methods()
        
        method_types_by_name = {str(m["name"]).lower().strip(): m["type"] for m in methods}
        method_types_by_id = {str(m["id"]): m["type"] for m in methods}

        ingresos_total = 0
        gastos_total = 0
        ingresos_efectivo = 0
        ingresos_debito = 0
        gastos_efectivo = 0
        gastos_debito = 0
        gastos_credito = 0

        for trans in transactions:
            if int(trans.get("is_recurrence_active", 0)) == 1:
                continue

            amount = trans.get("amount", 0)
            metodo_nombre = str(trans.get("payment_method_name", "")).lower().strip()
            m_id = str(trans.get("payment_method_id") or "")
            
            tipo_metodo_real = method_types_by_id.get(m_id, "")
            if not tipo_metodo_real:
                tipo_metodo_real = method_types_by_name.get(metodo_nombre, "")

            is_cash = (tipo_metodo_real == "cash") or ("efectivo" in metodo_nombre)
            is_credit = (tipo_metodo_real == "card")

            category_clean = str(trans.get("category_name", "")).lower().strip()
            desc_clean = str(trans.get("description", "")).lower().strip()
            
            # Se redefine is_internal aislando los abonos a deudas para que sumen al gasto macro del mes
            is_internal = (
                category_clean in ["pago de tarjetas", "pago de tarjeta"] 
                or "pago desde:" in desc_clean 
                or "pago a tarjeta" in desc_clean 
                or (category_clean == "transferencia" and "abono a préstamo" not in desc_clean)
                or (str(trans.get("id", "")).startswith("tf_") and category_clean != "pago de deudas" and "abono a préstamo" not in desc_clean)
            )

            # EXCLUSIÓN MANUAL SOLICITADA: Si no hay cuenta seleccionada (Vista Global "All Accounts"), se omiten flujos internos puros
            if self.selected_payment_method_id is None and is_internal:
                continue

            if trans.get("type") == "income":
                ingresos_total += amount
                if is_cash: ingresos_efectivo += amount
                else: ingresos_debito += amount 
            elif trans.get("type") == "expense":
                gastos_total += amount
                if is_cash: gastos_efectivo += amount
                elif is_credit: gastos_credito += amount
                else: gastos_debito += amount

        saldo_periodo = ingresos_total - gastos_total
        
        dragged_balance = 0
        if self.current_filter != "Histórico":
            filter_start_date = self.get_filter_start_date()
            if filter_start_date:
                start_date_obj = datetime.strptime(filter_start_date, "%Y-%m-%d")
                previous_day_str = (start_date_obj - timedelta(days=1)).strftime("%Y-%m-%d")
                dragged_balance = get_historical_balance(previous_day_str, self.selected_payment_method_id)

        payment_balances = get_balance_by_payment_method()
        
        # Lógica dinámica para mutar la quinta tarjeta KPI
        kpi_5_title = "🛡️ " + t("general_kpi_available_credit")
        kpi_5_number_color = COLOR_OCEANO
        
        if self.selected_payment_method_id is not None:
            selected_method = next((m for m in methods if m["id"] == self.selected_payment_method_id), None)
            if selected_method and selected_method.get("type") in ["bank_account", "cash"]:
                kpi_5_title = "💳 " + t("general_kpi_available_debit", default="Débito Disponible")
                selected_pb = next((pb for pb in payment_balances if pb.get("id") == self.selected_payment_method_id or pb.get("payment_method_id") == self.selected_payment_method_id), None)
                liquid_balance = selected_pb.get("balance", 0.0) if selected_pb else 0.0
                kpi_5_value_amount = liquid_balance
                kpi_5_number_color = ft.Colors.GREEN_400 if liquid_balance >= 0 else ft.Colors.RED_400
            else:
                # Es tarjeta de crédito específica seleccionada
                selected_pb = next((pb for pb in payment_balances if pb.get("id") == self.selected_payment_method_id or pb.get("payment_method_id") == self.selected_payment_method_id), None)
                card_bal = selected_pb.get("balance", 0.0) if selected_pb else 0.0
                kpi_5_value_amount = selected_method.get("credit_limit", 0.0) + card_bal
        else:
            # Vista global de Crédito Disponible acumulado
            card_debt_balance = sum(pb.get("balance", 0) for pb in payment_balances if pb.get("type", "") == "card")
            total_credit_limit = sum(m.get("credit_limit", 0) for m in methods if m.get("type") == "card")
            kpi_5_value_amount = total_credit_limit + card_debt_balance

        color_saldo_periodo = ft.Colors.RED_400 if saldo_periodo < 0 else ft.Colors.GREEN_400
        title_context = f" ({self.search_query})" if self.search_query else ""

        str_saldo_periodo = self._clean_decimals(format_currency(saldo_periodo))
        str_ingresos_total = self._clean_decimals(format_currency(ingresos_total))
        str_ingresos_efectivo = self._clean_decimals(format_currency(ingresos_efectivo))
        str_ingresos_debito = self._clean_decimals(format_currency(ingresos_debito))
        str_kpi_5_value = self._clean_decimals(format_currency(kpi_5_value_amount))
        
        str_dragged_balance = self._clean_decimals(format_currency(dragged_balance))
        str_gastos_total = self._clean_decimals(format_currency(gastos_total))
        str_gastos_efectivo = self._clean_decimals(format_currency(gastos_efectivo))
        str_gastos_debito = self._clean_decimals(format_currency(gastos_debito))
        str_gastos_credito = self._clean_decimals(format_currency(gastos_credito))

        row1 = ft.Row([
            self.create_kpi_card_unified("📊 " + t("general_kpi_period_balance") + title_context, str_saldo_periodo, ft.Colors.BLACK, color_saldo_periodo),
            self.create_kpi_card_unified("📈 " + t("historial_kpi_income") + title_context, str_ingresos_total, COLOR_OCEANO, ft.Colors.GREEN_400),
            self.create_kpi_card_unified("💵 " + t("historial_kpi_cash"), str_ingresos_efectivo, COLOR_OCEANO, ft.Colors.GREEN_400),
            self.create_kpi_card_unified("💳 " + t("general_kpi_debit_card"), str_ingresos_debito, COLOR_OCEANO, ft.Colors.GREEN_400),
            self.create_kpi_card_unified(kpi_5_title, str_kpi_5_value, COLOR_OCEANO, kpi_5_number_color),
        ], spacing=15, scroll=ft.ScrollMode.AUTO)

        row2 = ft.Row([
            self.create_kpi_card_unified("⏳ " + t("historial_kpi_dragged_balance"), str_dragged_balance, ft.Colors.BLACK, ft.Colors.BLUE_GREY_400),
            self.create_kpi_card_unified("📉 " + t("historial_kpi_expenses") + title_context, str_gastos_total, COLOR_ATARDECER, COLOR_ATARDECER),
            self.create_kpi_card_unified("💵 " + t("historial_kpi_cash"), str_gastos_efectivo, COLOR_ATARDECER, COLOR_ATARDECER),
            self.create_kpi_card_unified("💳 " + t("general_kpi_debit_card"), str_gastos_debito, COLOR_ATARDECER, COLOR_ATARDECER),
            self.create_kpi_card_unified("💳 " + t("general_kpi_credit_card"), str_gastos_credito, COLOR_ATARDECER, COLOR_ATARDECER),
        ], spacing=15, scroll=ft.ScrollMode.AUTO)

        return ft.Container(content=ft.Column(controls=[row1, row2], spacing=15))

    def build_chart_section(self):
        """Construye la sección analítica de gráficos aplicando la exclusión de transferencias relacionales en vista global."""
        def handle_tab_change(index):
            self.selected_chart_tab = index
            self.chart_container.content = self.build_chart_section()
            self.chart_container.update()

        tabs_data = [
            (0, f"📈 {t('historial_chart_trend', default='Tendencia')}"),
            (1, f"📊 {t('historial_chart_net_flow', default='Flujo Neto')}"),
            (2, f"🍕 {t('historial_chart_expenses', default='Pie Categorías (Gastos)')}"),
            (3, f"🍩 {t('historial_chart_income', default='Donut Fuentes (Ingresos)')}")
        ]

        tab_controls = []
        for index, label in tabs_data:
            is_selected = self.selected_chart_tab == index
            tab_controls.append(
                ft.Container(
                    content=ft.Text(label, color=COLOR_OCEANO if is_selected else ft.Colors.GREY_500, weight=ft.FontWeight.BOLD),
                    padding=ft.padding.symmetric(horizontal=15, vertical=10),
                    border=ft.border.all(1, ft.Colors.with_opacity(0.1, COLOR_OCEANO)) if is_selected else None,
                    bgcolor=COLOR_BLANCO if is_selected else ft.Colors.TRANSPARENT,
                    border_radius=10,
                    on_click=lambda e, i=index: handle_tab_change(i),
                    ink=True
                )
            )
        
        # Mutación adaptativa e internacionalización bilingüe del switch según pestaña activa
        lang = get_setting("language", "es")
        if self.selected_chart_tab == 1:
            default_lbl = "Flujo Neto Recurrente" if lang == "es" else "Recurring Net Flow"
            switch_label = f"{t('chart_switch_net_flow', default=default_lbl)} 📊"
        elif self.selected_chart_tab == 2:
            default_lbl = "Gastos Recurrentes" if lang == "es" else "Recurring Expenses"
            switch_label = f"{t('chart_switch_expenses', default=default_lbl)} 🍕"
        elif self.selected_chart_tab == 3:
            default_lbl = "Ingresos Recurrentes" if lang == "es" else "Recurring Income"
            switch_label = f"{t('chart_switch_income', default=default_lbl)} 🍩"
        else:
            default_lbl = "Tendencia Recurrente" if lang == "es" else "Recurring Trend"
            switch_label = f"{t('chart_switch_trend', default=default_lbl)} 📈"

        chart_switch = ft.Switch(
            label=switch_label,
            value=self.show_chart_filter,
            active_color=COLOR_OCEANO,
            on_change=self._on_chart_filter_change
        )

        header_row = ft.Row(
            controls=[
                ft.Row(controls=tab_controls, spacing=5, scroll=ft.ScrollMode.AUTO),
                chart_switch
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

        chart_txs = self._ensure_correct_mapping_for_charts()
        chart_layout = None 
        metrics_panel = None 
        
        acc_map = str.maketrans("áéíóúüÁÉÍÓÚÜ", "aeiouuaeiouu")
        sq_norm = self.search_query.translate(acc_map) if self.search_query else ""

        if self.selected_chart_tab in [0, 1]:
            fig, ax = plt.subplots(figsize=(10, 4), dpi=100)
            fig.patch.set_alpha(0)
            box_face = 'none'
            ax.set_facecolor(box_face)
            
            trend_map = {}
            for tx in chart_txs:
                category_clean = str(tx.get("category_name", "")).lower().strip()
                desc_clean = str(tx.get("description", "")).lower().strip()
                
                is_internal = (
                    category_clean in ["pago de tarjetas", "pago de tarjeta"] 
                    or "pago desde:" in desc_clean 
                    or "pago a tarjeta" in desc_clean 
                    or (category_clean == "transferencia" and "abono a préstamo" not in desc_clean)
                    or (str(tx.get("id", "")).startswith("tf_") and category_clean != "pago de deudas" and "abono a préstamo" not in desc_clean)
                )

                # EXCLUSIÓN MANUAL: Omitir si es vista global "Todas las cuentas" para no descuadrar curvas macros
                if self.selected_payment_method_id is None and is_internal:
                    continue

                key = tx["date"][:10] if self.current_filter == "Mes" else tx["date"][:7]
                if key not in trend_map:
                    trend_map[key] = {"date": key, "month": key, "income": 0.0, "expense": 0.0, "rec_income": 0.0, "rec_expense": 0.0, "search_income": 0.0, "search_expense": 0.0}
                
                amt = tx["amount"]
                is_rec_applied = int(tx.get("is_recurrence_active", 0)) == 2
                
                # Búsqueda insensible a acentos en curvas de tendencia
                is_match_applied = False
                if self.search_query:
                    tx_desc_norm = str(tx.get("description") or "").lower().translate(acc_map)
                    tx_cat_norm = str(tx.get("category_name") or "").lower().translate(acc_map)
                    if sq_norm in tx_desc_norm or sq_norm in tx_cat_norm:
                        is_match_applied = True
                
                if tx["type"] == "income":
                    trend_map[key]["income"] += amt
                    if is_rec_applied: trend_map[key]["rec_income"] += amt
                    if is_match_applied: trend_map[key]["search_income"] += amt
                else:
                    trend_map[key]["expense"] += amt
                    if is_rec_applied: trend_map[key]["rec_expense"] += amt
                    if is_match_applied: trend_map[key]["search_expense"] += amt

            sorted_keys = sorted(trend_map.keys())
            data = [trend_map[k] for k in sorted_keys]

            if not data: 
                chart_layout = ft.Container(height=300, alignment=ft.Alignment(0, 0), content=ft.Text("Sin datos para graficar en este periodo", color=ft.Colors.GREY_400))
            else:
                x_labels = [k.split("-")[2] if self.current_filter == "Mes" else k for k in sorted_keys]
                indices = list(range(len(data)))

                net_flows = [d["income"] - d["expense"] for d in data]
                expenses_list = [d["expense"] for d in data]
                avg_net_flow = sum(net_flows) / len(net_flows) if net_flows else 0
                max_expense = max(expenses_list) if expenses_list else 0

                str_avg = self._clean_decimals(format_currency(avg_net_flow))
                str_max = self._clean_decimals(format_currency(max_expense))
                color_avg = ft.Colors.GREEN_400 if avg_net_flow >= 0 else COLOR_ATARDECER

                metrics_panel = ft.Container(
                    margin=ft.margin.only(top=10), padding=ft.padding.symmetric(horizontal=15, vertical=10),
                    bgcolor=ft.Colors.with_opacity(0.02, COLOR_OCEANO), border_radius=10,
                    content=ft.Row([
                        ft.Row([ft.Text("⚡ " + t("metrics_avg_net", default="Promedio Neto del Periodo:"), size=13, color=ft.Colors.GREY_600, weight=ft.FontWeight.W_500), ft.Text(str_avg, size=13, color=color_avg, weight=ft.FontWeight.BOLD)], spacing=5),
                        ft.Row([ft.Text("🔥 " + t("metrics_max_expense", default="Pico Máximo de Gasto Registrado:"), size=13, color=ft.Colors.GREY_600, weight=ft.FontWeight.W_500), ft.Text(str_max, size=13, color=COLOR_ATARDECER, weight=ft.FontWeight.BOLD)], spacing=5)
                    ], alignment=ft.MainAxisAlignment.SPACE_EVENLY)
                )

                def format_millions(x, pos):
                    if abs(x) >= 1_000_000: return f'${x*1e-6:.1f}M'
                    elif abs(x) >= 1_000: return f'${x*1e-3:.0f}K'
                    return f'${x:.0f}'
                ax.yaxis.set_major_formatter(ticker.FuncFormatter(format_millions))

                if self.selected_chart_tab == 0:
                    if self.selected_table_type == "Todos":
                        ax.plot(x_labels, [d["income"] for d in data], marker='o', color=COLOR_OCEANO, label='Ingresos Totales', linewidth=2)
                        ax.plot(x_labels, [d["expense"] for d in data], marker='o', color=COLOR_ATARDECER, label='Gastos Totales', linewidth=2)
                        if self.show_chart_filter:
                            ax.plot(x_labels, [d["rec_income"] for d in data], marker='s', linestyle='--', color='#218380', label='Ingresos Recurrentes', linewidth=1.5, alpha=0.8)
                            ax.plot(x_labels, [d["rec_expense"] for d in data], marker='s', linestyle='--', color='#E63946', label='Gastos Recurrentes', linewidth=1.5, alpha=0.8)
                        if self.search_query:
                            search_totals = [d["search_income"] + d["search_expense"] for d in data]
                            ax.plot(x_labels, search_totals, marker='^', linestyle='-.', color='#9B59B6', label=f"Búsqueda: '{self.search_query}'", linewidth=2.0)
                    elif self.selected_table_type == "Ingresos":
                        ax.plot(x_labels, [d["income"] for d in data], marker='o', color=COLOR_OCEANO, label='Ingresos Totales', linewidth=2)
                        if self.show_chart_filter:
                            ax.plot(x_labels, [d["rec_income"] for d in data], marker='s', linestyle='--', color='#218380', label='Ingresos Recurrentes', linewidth=1.5, alpha=0.8)
                        if self.search_query:
                            ax.plot(x_labels, [d["search_income"] for d in data], marker='^', linestyle='-.', color='#9B59B6', label=f"Ingresos Búsqueda", linewidth=2.0)
                    elif self.selected_table_type == "Egresos":
                        ax.plot(x_labels, [d["expense"] for d in data], marker='o', color=COLOR_ATARDECER, label='Gastos Totales', linewidth=2)
                        if self.show_chart_filter:
                            ax.plot(x_labels, [d["rec_expense"] for d in data], marker='s', linestyle='--', color='#E63946', label='Gastos Recurrentes', linewidth=1.5, alpha=0.8)
                        if self.search_query:
                            ax.plot(x_labels, [d["search_expense"] for d in data], marker='^', linestyle='-.', color='#9B59B6', label=f"Gastos Búsqueda", linewidth=2.0)
                    ax.legend(frameon=False, loc="upper left")
                    ax.grid(True, linestyle='--', alpha=0.2, color=COLOR_OCEANO)
                    plt.xticks(rotation=45)

                elif self.selected_chart_tab == 1:
                    if self.selected_table_type == "Todos":
                        net_flows_calc = [d["income"] - d["expense"] for d in data]
                        rec_flows = [d["rec_income"] - d["rec_expense"] for d in data]
                        search_flows = [d["search_income"] - d["search_expense"] for d in data]
                        lbl_main, lbl_rec, lbl_src = 'Neto Total', 'Neto Recurrente', f"Neto '{self.search_query}'"
                    elif self.selected_table_type == "Ingresos":
                        net_flows_calc = [d["income"] for d in data]
                        rec_flows = [d["rec_income"] for d in data]
                        search_flows = [d["search_income"] for d in data]
                        lbl_main, lbl_rec, lbl_src = 'Ingresos Totales', 'Ingresos Recurrentes', f"Ingresos '{self.search_query}'"
                    elif self.selected_table_type == "Egresos":
                        net_flows_calc = [d["expense"] for d in data]
                        rec_flows = [d["rec_expense"] for d in data]
                        search_flows = [d["search_expense"] for d in data]
                        lbl_main, lbl_rec, lbl_src = 'Gastos Totales', 'Gastos Recurrentes', f"Gastos '{self.search_query}'"

                    colors_net = ["#27AE60" if val >= 0 else COLOR_ATARDECER for val in net_flows_calc]
                    colors_rec = ["#2ECC71" if val >= 0 else "#FF8A8A" for val in rec_flows]
                    colors_src = ["#8E44AD" if val >= 0 else "#D35400" for val in search_flows]

                    if self.show_chart_filter:
                        width = 0.25 if self.search_query else 0.35
                        if self.search_query:
                            ax.bar([i - width for i in indices], net_flows_calc, width=width, color=colors_net, label=lbl_main)
                            ax.bar([i for i in indices], rec_flows, width=width, color=colors_rec, label=lbl_rec)
                            ax.bar([i + width for i in indices], search_flows, width=width, color=colors_src, label=lbl_src)
                        else:
                            ax.bar([i - width/2 for i in indices], net_flows_calc, width=width, color=colors_net, label=lbl_main)
                            ax.bar([i + width/2 for i in indices], rec_flows, width=width, color=colors_rec, label=lbl_rec)
                        ax.legend(frameon=False)
                    else:
                        if self.search_query:
                            width = 0.35
                            ax.bar([i - width/2 for i in indices], net_flows_calc, width=width, color="#B0B0B0", alpha=0.25, label=lbl_main)
                            ax.bar([i + width/2 for i in indices], search_flows, width=width, color=colors_src, label=lbl_src)
                        else:
                            ax.bar(indices, net_flows_calc, color=colors_net, width=0.6, label=lbl_main)
                        ax.legend(frameon=False)
                    
                    ax.set_xticks(indices)
                    ax.set_xticklabels(x_labels)
                    ax.axhline(0, color=COLOR_OCEANO, linewidth=1, alpha=0.3)
                    ax.grid(axis='y', linestyle='--', alpha=0.2, color=COLOR_OCEANO)
                    plt.xticks(rotation=45)

                buf = io.BytesIO()
                fig.savefig(buf, format='png', bbox_inches='tight', transparent=True)
                buf.seek(0)
                img_base64 = base64.b64encode(buf.read()).decode('utf-8')
                plt.close(fig)
                chart_layout = ft.Container(content=ft.Image(src=f"data:image/png;base64,{img_base64}", fit="contain"), height=300, alignment=ft.Alignment(0, 0))

        elif self.selected_chart_tab in [2, 3]:
            fig, ax = plt.subplots(figsize=(6, 6), dpi=100) 
            fig.patch.set_alpha(0)
            target_type = "expense" if self.selected_chart_tab == 2 else "income"
            
            cat_map = {}
            for tx in chart_txs:
                if tx["type"] != target_type: continue
                category_clean = str(tx.get("category_name", "")).lower().strip()
                desc_clean = str(tx.get("description", "")).lower().strip()
                
                is_internal = (
                    category_clean in ["pago de tarjetas", "pago de tarjeta"] 
                    or "pago desde:" in desc_clean 
                    or "pago a tarjeta" in desc_clean 
                    or (category_clean == "transferencia" and "abono a préstamo" not in desc_clean)
                    or (str(tx.get("id", "")).startswith("tf_") and category_clean != "pago de deudas" and "abono a préstamo" not in desc_clean)
                )

                # EXCLUSIÓN MANUAL: Omitir si es vista global "Todas las cuentas" para no distorsionar sectores analíticos
                if self.selected_payment_method_id is None and is_internal:
                    continue

                is_search_match = False
                if self.search_query:
                    cat_translated = t(category_clean.replace(" ", "_"), default=category_clean).lower()
                    desc_translated = desc_clean
                    if "pago desde:" in desc_clean:
                        parts = desc_clean.split(":")
                        if len(parts) > 1:
                            account_name = parts[1].strip()
                            account_key = account_name.lower().replace(" ", "_").replace("-", "").strip()
                            desc_translated = f"{t('pago_desde', default='Pago desde')}: {t(account_key, default=account_name)}".lower()
                    elif "saldo inicial:" in desc_clean:
                        parts = desc_clean.split(":")
                        if len(parts) > 1:
                            account_name = parts[1].strip()
                            account_key = account_name.lower().replace(" ", "_").replace("-", "").strip()
                            desc_translated = f"{t('comun_initial_balance', default='Saldo inicial')}: {t(account_key, default=account_name)}".lower()
                    elif "transferencia a:" in desc_clean:
                        parts = desc_clean.split(":")
                        if len(parts) > 1:
                            dest_name = parts[1].strip()
                            dest_key = dest_name.lower().replace(" ", "_").replace("-", "").strip()
                            desc_translated = f"{t('transferencia_a', default='Transferencia a')}: {t(dest_key, default=dest_name)}".lower()
                    elif "transferencia desde:" in desc_clean:
                        parts = desc_clean.split(":")
                        if len(parts) > 1:
                            source_name = parts[1].strip()
                            source_key = source_name.lower().replace(" ", "_").replace("-", "").strip()
                            desc_translated = f"{t('transferencia_desde', default='Transferencia desde')}: {t(source_key, default=source_name)}".lower()
                    elif "pago a tarjeta:" in desc_clean:
                        parts = desc_clean.split(":")
                        if len(parts) > 1:
                            card_name = parts[1].strip()
                            card_key = card_name.lower().replace(" ", "_").replace("-", "").strip()
                            desc_translated = f"{t('pago_a_tarjeta', default='Pago a tarjeta')}: {t(card_key, default=card_name)}".lower()
                    elif "abono a préstamo:" in desc_clean:
                        parts = desc_clean.split(":")
                        if len(parts) > 1:
                            loan_name = parts[1].strip()
                            loan_key = loan_name.lower().replace(" ", "_").replace("-", "").strip()
                            desc_translated = f"{t('abono_a_prestamo', default='Abono a préstamo')}: {t(loan_key, default=loan_name)}".lower()
                    elif desc_clean == "ajuste inicial de cuenta":
                        desc_translated = t("ajuste_inicial_cuenta", default="Ajuste inicial de cuenta").lower()
                    else:
                        clean_key = desc_clean.replace("✨", "").lower().strip().replace(" ", "_")
                        translated_lookup = t(clean_key, default="")
                        if translated_lookup:
                            desc_translated = translated_lookup.lower()
                        else:
                            desc_translated = desc_clean.replace("✨", "").strip()

                    # Búsqueda insensible a acentos en sectores de pay/donut
                    if (sq_norm in desc_clean.translate(acc_map) or 
                        sq_norm in category_clean.translate(acc_map) or 
                        sq_norm in cat_translated.translate(acc_map) or 
                        sq_norm in desc_translated.translate(acc_map)):
                        is_search_match = True

                c_name = tx["category_name"]
                if c_name not in cat_map:
                    cat_map[c_name] = {
                        "category": c_name, 
                        "color": tx.get("category_color") or ("#95A5A6" if target_type == "expense" else "#27AE60"), 
                        "total": 0.0,
                        "rec_total": 0.0,
                        "has_match": False
                    }
                cat_map[c_name]["total"] += tx["amount"]
                if int(tx.get("is_recurrence_active", 0)) == 2:
                    cat_map[c_name]["rec_total"] += tx["amount"]
                if is_search_match:
                    cat_map[c_name]["has_match"] = True
                
            data = sorted(cat_map.values(), key=lambda x: x["total"], reverse=True)

            if not data:
                plt.close(fig)
                chart_layout = ft.Container(height=300, alignment=ft.Alignment(0, 0), content=ft.Text(t("historial_no_chart_data"), color=ft.Colors.GREY_400))
            else:
                sizes = [d["total"] for d in data]
                colors, explode = [], []
                
                is_highlight_active = self.show_chart_filter or bool(self.search_query)

                for d in data:
                    should_explode = False
                    if self.show_chart_filter and d["rec_total"] > 0:
                        should_explode = True
                    if self.search_query and d["has_match"]:
                        should_explode = True

                    if is_highlight_active:
                        if should_explode:
                            colors.append(d["color"])
                            explode.append(0.12)
                        else:
                            colors.append("#E0E0E0")
                            explode.append(0)
                    else:
                        colors.append(d["color"])
                        explode.append(0)

                total_sum = sum(sizes)
                ax.pie(sizes, colors=colors, explode=explode, startangle=90, wedgeprops=dict(width=0.4, edgecolor='w', linewidth=2))
                ax.axis('equal')

                buf = io.BytesIO()
                fig.savefig(buf, format='png', bbox_inches='tight', transparent=True)
                buf.seek(0)
                img_base64 = base64.b64encode(buf.read()).decode('utf-8')
                plt.close(fig)
                
                legend_rows = []
                for d in data:
                    pct = (d["total"] / total_sum) * 100 if total_sum > 0 else 0
                    category_translated = t(d['category'].lower().replace(" ", "_"), default=d['category'])
                    
                    should_highlight_text = False
                    if self.show_chart_filter and d["rec_total"] > 0:
                        should_highlight_text = True
                    if self.search_query and d["has_match"]:
                        should_highlight_text = True

                    if is_highlight_active:
                        if should_highlight_text:
                            text_color = COLOR_OCEANO
                            text_weight = ft.FontWeight.BOLD
                            icon_color = d["color"]
                        else:
                            text_color = ft.Colors.BLUE_GREY_200
                            text_weight = ft.FontWeight.NORMAL
                            icon_color = ft.Colors.BLUE_GREY_100
                    else:
                        text_color = ft.Colors.GREY_800
                        text_weight = ft.FontWeight.W_500
                        icon_color = d["color"]

                    legend_rows.append(
                        ft.Row([
                            ft.Container(width=14, height=14, bgcolor=icon_color, border_radius=4),
                            ft.Container(content=ft.Text(category_translated, size=13, color=text_color, weight=text_weight), expand=True),
                            ft.Text(f"{pct:.1f}%", size=13, weight=ft.FontWeight.BOLD if should_highlight_text else ft.FontWeight.W_500, color=text_color if is_highlight_active and not should_highlight_text else COLOR_OCEANO),
                        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
                    )
                
                legend_container = ft.Container(width=250, height=280, padding=ft.padding.only(left=20, top=10, bottom=10), border=ft.border.only(left=ft.BorderSide(1, ft.Colors.with_opacity(0.1, COLOR_CIAN))), content=ft.Column(controls=legend_rows, scroll=ft.ScrollMode.AUTO, spacing=8))
                chart_layout = ft.Row([ft.Container(content=ft.Image(src=f"data:image/png;base64,{img_base64}", fit="contain")), legend_container], expand=True, alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=50)

        return ft.Container(
            bgcolor=COLOR_BLANCO, border_radius=20, padding=25, border=ft.border.all(1, ft.Colors.with_opacity(0.1, COLOR_OCEANO)),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=20, color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK), offset=ft.Offset(0, 10)),
            content=ft.Column([header_row, ft.Container(content=chart_layout, height=300), metrics_panel if metrics_panel else ft.Container()], spacing=5)
        )

    def _ensure_correct_mapping_for_charts(self):
        """Helper para extraer movimientos en memoria unificados para las gráficas analíticas."""
        start, end = self.get_date_range()
        
        chart_should_filter_recurring = self.show_chart_filter and self.show_only_recurring

        if chart_should_filter_recurring:
            # Si ambos están activos, filtramos en caliente únicamente las recurrentes ya procesadas (Estado 2)
            raw_txs = get_filtered_transactions(start, end, self.selected_payment_method_id, is_recurrence_view=False)
            txs = [dict(t_val) for t_val in raw_txs if int(t_val.get("is_recurrence_active", 0)) == 2]
        else:
            raw_txs = get_filtered_transactions(start, end, self.selected_payment_method_id, is_recurrence_view=False)
            txs = [dict(t_val) for t_val in raw_txs]

        if not chart_should_filter_recurring:
            try:
                conn = get_connection()
                cursor = conn.cursor()
                query = """
                    SELECT t.id, t.amount, t.date, t.description, t.source_method_id, pm_s.name as source_name, pm_s.icon as source_icon, t.destination_method_id, pm_d.name as dest_name, pm_d.icon as dest_icon, pm_d.type as dest_type, t.destination_loan_id, l.name as loan_name, l.icon as loan_icon
                    FROM transfers t
                    JOIN payment_methods pm_s ON t.source_method_id = pm_s.id
                    LEFT JOIN payment_methods pm_d ON t.destination_method_id = pm_d.id
                    LEFT JOIN loans l ON t.destination_loan_id = l.id
                    WHERE t.date >= ? AND t.date < ?
                """
                cursor.execute(query, (start, end))
                for row in cursor.fetchall():
                    if row["destination_loan_id"]:
                        computed_desc = f"{t('deudas_loan_payment_title', default='Abono a préstamo')}: {row['loan_name']}"
                        cat_name = "Pago de deudas"
                        cat_icon = "🏦"
                    elif row["dest_type"] == "card":
                        computed_desc = f"{t('deudas_card_payment_title', default='Pago a tarjeta')}: {row['dest_name']}"
                        cat_name = "Pago de tarjetas"
                        cat_icon = "💳"
                    else:
                        computed_desc = row["description"] if row["description"] else f"Transferencia"
                        cat_name = "Transferencia"
                        cat_icon = "🔀"

                    if self.selected_payment_method_id is None or self.selected_payment_method_id == row["source_method_id"]:
                        txs.append({"id": f"tf_out_{row['id']}", "amount": float(row["amount"]), "description": computed_desc, "type": "expense", "date": row["date"], "category_name": cat_name, "category_icon": cat_icon, "category_color": "#34495E", "payment_method_id": row["source_method_id"], "payment_method_name": row["source_name"], "payment_method_icon": row["source_icon"] or "💳"})
                    if row["destination_method_id"] is not None and row["dest_type"] != "card":
                        if self.selected_payment_method_id is None or self.selected_payment_method_id == row["destination_method_id"]:
                            txs.append({"id": f"tf_in_{row['id']}", "amount": float(row["amount"]), "description": row["description"] or f"Transferencia", "type": "income", "date": row["date"], "category_name": "Transferencia", "category_icon": "🔀", "category_color": "#2ECC71", "payment_method_id": row["destination_method_id"], "payment_method_name": row["dest_name"], "payment_method_icon": row["dest_icon"] or "💳"})
                conn.close()
            except: pass
        return txs

    def create_kpi_card_unified(self, full_title_with_icon, value, title_color, number_color):
        """Construye un contenedor premium con tipografía premium para los tableros de KPIs."""
        return ft.Container(
            width=245, height=115,
            bgcolor=COLOR_BLANCO, border_radius=15,
            border=ft.border.all(1, ft.Colors.with_opacity(0.1, COLOR_OCEANO)),
            padding=ft.padding.symmetric(vertical=15, horizontal=16),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=10, color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK), offset=ft.Offset(0, 5)),
            content=ft.Column(
                controls=[
                    ft.Text(full_title_with_icon, size=16, color=title_color, weight=ft.FontWeight.W_600, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(value, size=28, weight=ft.FontWeight.BOLD, color=number_color, overflow=ft.TextOverflow.CLIP)
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.START, spacing=4
            )
        )

    def _toggle_date_sort(self, e):
        """Conmutador reactivo para reordenar la tabla de movimientos por Fecha."""
        self.sort_column = "date"
        self.date_sort_desc = not self.date_sort_desc
        self.current_page = 1
        self.update_transactions_data()

    def _toggle_amount_sort(self, e):
        """Conmutador reactivo para reordenar la tabla de movimientos por Monto."""
        self.sort_column = "amount"
        self.amount_sort_desc = not self.amount_sort_desc
        self.current_page = 1
        self.update_transactions_data()

    def apply_table_filter(self, e):
        """Manejador para aplicar el filtro de tipo de tabla."""
        if hasattr(self, 'dropdown_type') and self.dropdown_type.value:
            self.selected_table_type = self.dropdown_type.value
        self.current_page = 1 
        self.update_view()

    def _on_recurring_switch_change(self, e):
        """Manejador reactivo para conmutar el switch de recurrentes."""
        self.show_only_recurring = self.recurring_switch.value
        self.current_page = 1
        self.update_view()

    def _on_chart_filter_change(self, e):
        """Manejador reactivo para el switch de Balance actual + Filtro en las gráficas."""
        self.show_chart_filter = e.control.value
        self.chart_container.content = self.build_chart_section()
        self.chart_container.update()

    def build_transactions_layout(self):
        self.dropdown_type = ft.Dropdown(
            options=[ft.dropdown.Option("Todos", t("historial_all_accounts")), ft.dropdown.Option("Ingresos", t("historial_kpi_income")), ft.dropdown.Option("Egresos", t("historial_kpi_expenses"))],
            value=self.selected_table_type, width=140, bgcolor=COLOR_BLANCO, text_size=14, content_padding=10
        )

        btn_aplicar_tabla = ft.OutlinedButton(
            content=ft.Row([ft.Text("🔽"), ft.Text(t("historial_apply"), color=COLOR_OCEANO, weight=ft.FontWeight.BOLD)]),
            on_click=self.apply_table_filter, 
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), side=ft.BorderSide(1, COLOR_OCEANO))
        )

        self.search_field = ft.TextField(
            value=self.search_query, hint_text=t("historial_search_placeholder"),
            width=260, height=30, content_padding=10, text_size=14,
            bgcolor=COLOR_BLANCO, border_color=ft.Colors.GREY_400, border_radius=8
        )
        self.search_field.on_change = self.on_search_change

        btn_exportar = ft.Container(
            content=ft.Row([ft.Text(t("historial_export_csv_to_desktop"), size=14, color=COLOR_OCEANO, weight=ft.FontWeight.BOLD)], spacing=5, alignment=ft.MainAxisAlignment.CENTER),
            padding=ft.padding.symmetric(horizontal=15, vertical=8), border=ft.border.all(1, COLOR_OCEANO), border_radius=8, ink=True, on_click=self.export_csv_to_desktop 
        )

        self.recurring_switch = ft.Switch(
            label=t("historial_filter_recurring", "Solo recurrentes 🔄"),
            value=self.show_only_recurring, active_color=COLOR_OCEANO, on_change=self._on_recurring_switch_change
        )

        header_row = ft.Row(
            controls=[
                ft.Text(t("historial_transactions_detail"), size=20, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
                ft.Row([self.search_field, self.recurring_switch, ft.Text(t("historial_type_label"), size=14, color=ft.Colors.GREY_700), self.dropdown_type, btn_aplicar_tabla, btn_exportar], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, scroll=ft.ScrollMode.AUTO
        )

        self.table_data_container = ft.Container(expand=True)
        self.table_paginator_container = ft.Container()

        return ft.Container(
            width=float("inf"), bgcolor=COLOR_BLANCO, border_radius=20, padding=25,
            border=ft.border.all(1, ft.Colors.with_opacity(0.1, COLOR_OCEANO)),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=20, color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK), offset=ft.Offset(0, 10)),
            content=ft.Column([header_row, self.table_data_container, self.table_paginator_container], spacing=15)
        )

    def get_current_filtered_transactions(self):
        """Obtiene las transacciones fusionando de forma simétrica las transferencias y deudas."""
        start, end = self.get_date_range()
        if self.show_only_recurring:
            raw_txs = get_filtered_transactions("1900-01-01", "2100-01-01", self.selected_payment_method_id, is_recurrence_view=True)
            if self.current_filter != "Histórico":
                raw_txs = [t_val for t_val in raw_txs if start <= t_val["date"] < end]
        else:
            raw_txs = get_filtered_transactions(start, end, self.selected_payment_method_id, is_recurrence_view=False)

        transactions = [dict(t_val) for t_val in raw_txs]
        synthetic_transfers = []

        if not self.show_only_recurring:
            try:
                conn = get_connection()
                cursor = conn.cursor()
                query = """
                    SELECT 
                        t.id, t.amount, t.date, t.description,
                        t.source_method_id, pm_s.name as source_name, pm_s.icon as source_icon, pm_s.type as source_type,
                        t.destination_method_id, pm_d.name as dest_name, pm_d.icon as dest_icon, pm_d.type as dest_type,
                        t.destination_loan_id, l.name as loan_name, l.icon as loan_icon
                    FROM transfers t
                    JOIN payment_methods pm_s ON t.source_method_id = pm_s.id
                    LEFT JOIN payment_methods pm_d ON t.destination_method_id = pm_d.id
                    LEFT JOIN loans l ON t.destination_loan_id = l.id
                    WHERE t.date >= ? AND t.date < ?
                """
                cursor.execute(query, (start, end))
                transfer_rows = cursor.fetchall()
                conn.close()
                
                for row in transfer_rows:
                    dest_label = row["dest_name"] or row["loan_name"] or ""
                    
                    if row["destination_loan_id"]:
                        computed_desc = f"Abono a préstamo: {row['loan_name']}"
                        cat_name = "Pago de deudas"
                        cat_icon = "🏦"
                    elif row["dest_type"] == "card":
                        computed_desc = f"Pago a tarjeta: {row['dest_name']}"
                        cat_name = "Pago de tarjetas"
                        cat_icon = "💳"
                    else:
                        computed_desc = row["description"] if row["description"] else f"Transferencia a: {row['dest_name']}"
                        cat_name = "Transferencia"
                        cat_icon = "🔀"

                    # 1. Lado Egreso (Origen)
                    if self.selected_payment_method_id is None or self.selected_payment_method_id == row["source_method_id"]:
                        synthetic_transfers.append({
                            "id": f"tf_out_{row['id']}",
                            "amount": float(row["amount"]),
                            "description": computed_desc,
                            "type": "expense",
                            "date": row["date"],
                            "recurrence_type": None,
                            "is_recurrence_active": 0,
                            "category_name": cat_name,
                            "category_icon": cat_icon,
                            "category_color": "#34495E",
                            "payment_method_id": row["source_method_id"],
                            "payment_method_name": row["source_name"],
                            "payment_method_icon": row["source_icon"] or "💳"
                        })
                    
                    # 2. Lado Ingreso (Destino)
                    if row["destination_method_id"] is not None and row["dest_type"] != "card":
                        if self.selected_payment_method_id is None or self.selected_payment_method_id == row["destination_method_id"]:
                            synthetic_transfers.append({
                                "id": f"tf_in_{row['id']}",
                                "amount": float(row["amount"]),
                                "description": row["description"] if row["description"] else f"Transferencia desde: {row['source_name']}",
                                "type": "income",
                                "date": row["date"],
                                "recurrence_type": None,
                                "is_recurrence_active": 0,
                                "category_name": "Transferencia",
                                "category_icon": "🔀",
                                "category_color": "#2ECC71",
                                "payment_method_id": row["destination_method_id"],
                                "payment_method_name": row["dest_name"],
                                "payment_method_icon": row["dest_icon"] or "💳"
                            })
            except Exception as ex:
                print(f"Error integrando transferencias al listado: {ex}")

        transactions.extend(synthetic_transfers)
        
        def _get_sort_timestamp(tx_dict) -> str:
            raw_date_str = tx_dict.get("date", "")
            if len(raw_date_str) == 10:
                return f"{raw_date_str} 00:00:00"
            return raw_date_str

        if self.sort_column == "date":
            transactions.sort(key=lambda x: (_get_sort_timestamp(x), str(x.get("id", ""))), reverse=self.date_sort_desc)
        elif self.sort_column == "amount":
            transactions.sort(key=lambda x: x.get("amount", 0.0), reverse=self.amount_sort_desc)

        if self.selected_table_type == "Ingresos":
            transactions = [t_val for t_val in transactions if t_val["type"] == "income"]
        elif self.selected_table_type == "Egresos":
            transactions = [t_val for t_val in transactions if t_val["type"] == "expense"]

        # INTEGRACIÓN DE BÚSQUEDA OPTIMIZADA E INSENSIBLE A ACENTOS Y MONTOS
        if self.search_query:
            filtered_transactions = []
            lang = get_setting("language", "es")
            
            # Mapeo de acentos para una normalización diacritic-insensitive limpia
            acc_map = str.maketrans("áéíóúüÁÉÍÓÚÜ", "aeiouuaeiouu")
            
            # UX Híbrido: Eliminamos el signo '$' por si el usuario lo escribe por costumbre
            sq_clean = self.search_query.replace("$", "").strip()
            sq_norm = sq_clean.translate(acc_map)
            
            for t_val in transactions:
                raw_desc = str(t_val.get("description") or t_val.get("category_name") or "").strip().lower()
                raw_cat = str(t_val.get("category_name") or "").strip().lower()
                
                raw_desc_norm = raw_desc.translate(acc_map)
                raw_cat_norm = raw_cat.translate(acc_map)
                
                # Normalización de los montos a cadenas de texto para búsqueda directa (tanto flotante como entera)
                raw_amount_str = str(t_val.get("amount", "")).lower()
                raw_amount_int_str = str(int(t_val.get("amount", 0)))
                is_amount_match = (sq_norm in raw_amount_str or sq_norm in raw_amount_int_str)
                
                if lang == "es":
                    if (sq_norm in raw_desc_norm or sq_norm in raw_cat_norm or is_amount_match):
                        filtered_transactions.append(t_val)
                    continue
                
                cat_translated = t(raw_cat.replace(" ", "_"), default=raw_cat).lower()
                desc_translated = raw_desc
                
                if "pago desde:" in raw_desc:
                    parts = raw_desc.split(":")
                    if len(parts) > 1:
                        account_name = parts[1].strip()
                        account_key = account_name.lower().replace(" ", "_").replace("-", "").strip()
                        desc_translated = f"{t('pago_desde', default='Pago desde')}: {t(account_key, default=account_name)}".lower()
                elif "saldo inicial:" in raw_desc:
                    parts = raw_desc.split(":")
                    if len(parts) > 1:
                        account_name = parts[1].strip()
                        account_key = account_name.lower().replace(" ", "_").replace("-", "").strip()
                        desc_translated = f"{t('comun_initial_balance', default='Saldo inicial')}: {t(account_key, default=account_name)}".lower()
                elif "transferencia a:" in raw_desc:
                    parts = raw_desc.split(":")
                    if len(parts) > 1:
                        dest_name = parts[1].strip()
                        dest_key = dest_name.lower().replace(" ", "_").replace("-", "").strip()
                        desc_translated = f"{t('transferencia_a', default='Transferencia a')}: {t(dest_key, default=dest_name)}".lower()
                elif "transferencia desde:" in raw_desc:
                    parts = raw_desc.split(":")
                    if len(parts) > 1:
                        source_name = parts[1].strip()
                        source_key = source_name.lower().replace(" ", "_").replace("-", "").strip()
                        desc_translated = f"{t('transferencia_desde', default='Transferencia desde')}: {t(source_key, default=source_name)}".lower()
                elif "pago a tarjeta:" in raw_desc:
                    parts = raw_desc.split(":")
                    if len(parts) > 1:
                        card_name = parts[1].strip()
                        card_key = card_name.lower().replace(" ", "_").replace("-", "").strip()
                        desc_translated = f"{t('pago_a_tarjeta', default='Pago a tarjeta')}: {t(card_key, default=card_name)}".lower()
                elif "abono a préstamo:" in raw_desc:
                    parts = raw_desc.split(":")
                    if len(parts) > 1:
                        loan_name = parts[1].strip()
                        loan_key = loan_name.lower().replace(" ", "_").replace("-", "").strip()
                        desc_translated = f"{t('abono_a_prestamo', default='Abono a préstamo')}: {t(loan_key, default=loan_name)}".lower()
                elif raw_desc == "ajuste inicial de cuenta":
                    desc_translated = t("ajuste_inicial_cuenta", default="Ajuste inicial de cuenta").lower()
                else:
                    clean_key = raw_desc.replace("✨", "").lower().strip().replace(" ", "_")
                    translated_lookup = t(clean_key, default="")
                    if translated_lookup:
                        desc_translated = translated_lookup.lower()
                    else:
                        desc_translated = raw_desc.replace("✨", "").strip()

                cat_trans_norm = cat_translated.translate(acc_map)
                desc_trans_norm = desc_translated.translate(acc_map)

                if (sq_norm in raw_desc_norm or 
                    sq_norm in raw_cat_norm or 
                    sq_norm in cat_trans_norm or 
                    sq_norm in desc_trans_norm or
                    is_amount_match):
                    filtered_transactions.append(t_val)
                    
            transactions = filtered_transactions

        return transactions

    def update_transactions_data(self):
        try:
            process_recurring_transactions()
        except Exception as ex:
            print(f"[Historial] Error inyectando retroactivos: {ex}")

        transactions = self.get_current_filtered_transactions()

        total_items = len(transactions)
        total_pages = (total_items + self.rows_per_page - 1) // self.rows_per_page
        if total_pages == 0: total_pages = 1 
        
        if self.current_page > total_pages:
            self.current_page = total_pages

        start_idx = (self.current_page - 1) * self.rows_per_page
        end_idx = start_idx + self.rows_per_page
        paginated_transactions = transactions[start_idx:end_idx]

        if not transactions:
            self.table_data_container.content = ft.Container(padding=20, alignment=ft.Alignment(0, 0), content=ft.Text(t("historial_no_transactions"), size=16, color=ft.Colors.GREY_500))
            self.table_paginator_container.content = ft.Container()
        else:
            # Obtener mapeo de métodos congelados para aplicar opacidad estricta
            frozen_method_ids = {m["id"] for m in get_payment_methods() if m.get("status") == "frozen"}
            rows = []
            
            for trans in paginated_transactions:
                is_expense = trans["type"] == "expense"
                
                current_method_id = trans.get("payment_method_id")
                is_account_frozen = current_method_id in frozen_method_ids
                
                # Ajuste de colorimetría basado en congelamiento
                if is_account_frozen:
                    amount_color = ft.Colors.BLUE_GREY_300
                    row_bg_color = ft.Colors.BLUE_50
                    cell_text_color = ft.Colors.BLUE_GREY_400
                else:
                    amount_color = COLOR_ATARDECER if is_expense else ft.Colors.GREEN_400
                    row_bg_color = ft.Colors.TRANSPARENT if len(rows) % 2 == 0 else ft.Colors.with_opacity(0.01, COLOR_OCEANO)
                    cell_text_color = ft.Colors.BLACK87
                    
                amount_prefix = "-" if is_expense else "+"
                indicador_simbolo = "▼" if is_expense else "▲"
                
                is_rec = int(trans.get("is_recurrence_active", 0)) in [1, 2]
                is_synthetic = str(trans["id"]).startswith("tf_")
                
                try:
                    date_obj = datetime.strptime(trans["date"][:10], "%Y-%m-%d")
                    visual_date = date_obj.strftime("%d-%m-%Y")
                except:
                    visual_date = trans["date"]
                
                raw_desc = trans.get("description") or trans.get("category_name") or ""
                if not str(raw_desc).strip() or str(raw_desc).strip() == "-":
                    raw_desc = trans["category_name"]
                
                desc_text = str(raw_desc).strip()
                
                if "pago desde:" in desc_text.lower():
                    parts = desc_text.split(":")
                    if len(parts) > 1:
                        account_name = parts[1].strip()
                        account_key = account_name.lower().replace(" ", "_").replace("-", "").strip()
                        desc_text = f"{t('pago_desde', default='Pago desde')}: {t(account_key, default=account_name)}"
                        
                elif "saldo inicial:" in desc_text.lower():
                    parts = desc_text.split(":")
                    if len(parts) > 1:
                        account_name = parts[1].strip()
                        account_key = account_name.lower().replace(" ", "_").replace("-", "").strip()
                        desc_text = f"{t('comun_initial_balance', default='Saldo inicial')}: {t(account_key, default=account_name)}"
                        
                elif "transferencia a:" in desc_text.lower():
                    parts = desc_text.split(":")
                    if len(parts) > 1:
                        dest_name = parts[1].strip()
                        dest_key = dest_name.lower().replace(" ", "_").replace("-", "").strip()
                        desc_text = f"{t('transferencia_a', default='Transferencia a')}: {t(dest_key, default=dest_name)}"
                        
                elif "transferencia desde:" in desc_text.lower():
                    parts = desc_text.split(":")
                    if len(parts) > 1:
                        source_name = parts[1].strip()
                        source_key = source_name.lower().replace(" ", "_").replace("-", "").strip()
                        desc_text = f"{t('transferencia_desde', default='Transferencia desde')}: {t(source_key, default=source_name)}"

                elif "pago a tarjeta:" in desc_text.lower():
                    parts = desc_text.split(":")
                    if len(parts) > 1:
                        card_name = parts[1].strip()
                        card_key = card_name.lower().replace(" ", "_").replace("-", "").strip()
                        desc_text = f"{t('pago_a_tarjeta', default='Pago a tarjeta')}: {t(card_key, default=card_name)}"

                elif "abono a préstamo:" in desc_text.lower():
                    parts = desc_text.split(":")
                    if len(parts) > 1:
                        loan_name = parts[1].strip()
                        loan_key = loan_name.lower().replace(" ", "_").replace("-", "").strip()
                        desc_text = f"{t('abono_a_prestamo', default='Abono a préstamo')}: {t(loan_key, default=loan_name)}"
                        
                elif desc_text.lower() == "ajuste inicial de cuenta":
                    desc_text = t("ajuste_inicial_cuenta", default="Ajuste inicial de cuenta")
                else:
                    clean_key = desc_text.replace("✨", "").lower().strip().replace(" ", "_")
                    translated_lookup = t(clean_key, default="")
                    if translated_lookup:
                        desc_text = translated_lookup
                    else:
                        desc_text = str(raw_desc).replace("✨", "").strip()

                if len(desc_text) > 30:
                    desc_text = desc_text[:27] + "..."
                
                tipo_visual = f"🔄 {indicador_simbolo}" if is_rec else indicador_simbolo
                cat_translated = t(trans["category_name"].lower().strip().replace(" ", "_"), default=trans["category_name"])
                
                raw_method = trans.get("payment_method_name")
                if raw_method is not None:
                    method_translated = t(str(raw_method).lower().strip().replace(" ", "_"), default=str(raw_method))
                else:
                    method_translated = t("deudas_unknown_account", default="Desconocido")
                
                if is_account_frozen:
                    method_translated = f"❄️ {method_translated}"
                
                try:
                    str_amount = self._clean_decimals(format_currency(trans['amount']))
                except:
                    str_amount = f"{trans['amount']}"

                # Control estricto de bloqueos operativos si la cuenta está congelada
                is_edit_disabled = int(trans.get("is_recurrence_active", 0)) == 1 or is_synthetic or is_account_frozen
                is_delete_disabled = is_synthetic or is_account_frozen

                edit_opacity = 0.3 if is_edit_disabled else 1.0
                delete_opacity = 0.3 if is_delete_disabled else 1.0

                rows.append(
                    ft.DataRow(
                        color=row_bg_color,
                        cells=[
                            ft.DataCell(ft.Text(tipo_visual, color=amount_color, size=16, weight=ft.FontWeight.BOLD)),
                            ft.DataCell(ft.Text(visual_date, size=14, weight=ft.FontWeight.W_500, color=cell_text_color)),
                            ft.DataCell(ft.Row([ft.Text(trans["category_icon"], size=16), ft.Text(cat_translated, size=14, weight=ft.FontWeight.W_600, color=cell_text_color)])),
                            ft.DataCell(ft.Text(desc_text, size=14, color=cell_text_color, weight=ft.FontWeight.NORMAL)),
                            ft.DataCell(ft.Row([ft.Text(trans["payment_method_icon"], size=16), ft.Text(method_translated, size=14, weight=ft.FontWeight.W_500, color=ft.Colors.BLUE_700 if is_account_frozen else cell_text_color)])),
                            ft.DataCell(ft.Text(f"{amount_prefix}{str_amount}", color=amount_color, weight=ft.FontWeight.BOLD, size=15)),
                            ft.DataCell(
                                ft.Row(
                                    controls=[
                                        ft.Container(
                                            content=ft.Text("✏️", size=16, opacity=edit_opacity), 
                                            padding=8, border_radius=5, 
                                            ink=not is_edit_disabled, 
                                            on_click=(lambda e, trans_id=trans["id"]: self._edit_transaction(trans_id)) if not is_edit_disabled else None
                                        ),
                                        ft.Container(
                                            content=ft.Text("🗑️", size=16, opacity=delete_opacity), 
                                            padding=8, border_radius=5, 
                                            ink=not is_delete_disabled, 
                                            on_click=(lambda e, trans_id=trans["id"]: self._show_delete_confirmation(trans_id)) if not is_delete_disabled else None
                                        )
                                    ], spacing=5, alignment=ft.MainAxisAlignment.CENTER
                                )
                            )
                        ]
                    )
                )

            self.table_data_container.content = ft.Row(
                controls=[
                    ft.DataTable(
                        columns=[
                            ft.DataColumn(ft.Text(" ")), 
                            ft.DataColumn(
                                ft.Row([
                                    ft.Text(t("historial_table_date", "Fecha")),
                                    ft.IconButton(
                                        icon=ft.Icons.ARROW_DOWNWARD if self.date_sort_desc else ft.Icons.ARROW_UPWARD,
                                        icon_size=14, padding=0, on_click=self._toggle_date_sort
                                    )
                                ], spacing=2)
                            ), 
                            ft.DataColumn(ft.Text(t("historial_table_category", "Categoría"))), 
                            ft.DataColumn(ft.Text(t("historial_table_description", "Descripción"))), 
                            ft.DataColumn(ft.Text(t("historial_table_payment", "Método"))),
                            ft.DataColumn(
                                ft.Row([
                                    ft.Text(t("historial_table_amount", "Monto")),
                                    ft.IconButton(
                                        icon=ft.Icons.ARROW_DOWNWARD if self.amount_sort_desc else ft.Icons.ARROW_UPWARD,
                                        icon_size=14, padding=0, on_click=self._toggle_amount_sort
                                    )
                                ], spacing=2),
                                numeric=True
                            ),
                            ft.DataColumn(ft.Text(t("historial_table_actions", "Acciones"))),
                        ],
                        rows=rows, 
                        heading_row_color=ft.Colors.with_opacity(0.05, COLOR_OCEANO),
                        data_text_style=ft.TextStyle(size=14, color=ft.Colors.BLACK87),
                        heading_text_style=ft.TextStyle(size=15, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
                        column_spacing=35,
                        horizontal_lines=ft.BorderSide(1, ft.Colors.with_opacity(0.05, ft.Colors.BLACK)),
                    )
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True 
            )

            self.table_paginator_container.content = ft.Row(
                controls=[
                    ft.Text(t("historial_showing_transactions").format(current=len(paginated_transactions), total=total_items), size=13, color=ft.Colors.GREY_600, weight=ft.FontWeight.W_500),
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Text("◀", size=18, color=ft.Colors.GREY_400 if self.current_page == 1 else COLOR_OCEANO),
                                padding=ft.padding.symmetric(horizontal=10, vertical=5), border_radius=20, ink=self.current_page > 1,
                                on_click=(lambda e: self.change_page(-1, total_pages)) if self.current_page > 1 else None
                            ),
                            ft.Text(t("historial_page_info").format(current=self.current_page, total=total_pages), size=14, weight=ft.FontWeight.BOLD),
                            ft.Container(
                                content=ft.Text("▶", size=18, color=ft.Colors.GREY_400 if self.current_page == total_pages else COLOR_OCEANO),
                                padding=ft.padding.symmetric(horizontal=10, vertical=5), border_radius=20, ink=self.current_page < total_pages,
                                on_click=(lambda e: self.change_page(1, total_pages)) if self.current_page < total_pages else None
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=5
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            )

        try:
            self.table_data_container.update()
            self.table_paginator_container.update()
        except RuntimeError:
            pass

    def _edit_transaction(self, trans_id):
        """Abre el formulario de edición de transacciones cargando el TransactionForm dinámicamente."""
        if str(trans_id).startswith("tf_"):
            self.page.snack_bar = ft.SnackBar(content=ft.Text("Las transferencias relacionales y abonos de carteras deben editarse desde la sección de Deudas."), bgcolor=ft.Colors.ORANGE_700)
            self.page.snack_bar.open = True
            self.page.update()
            return
            
        try:
            from components.forms import TransactionForm
            tx = get_transaction_by_id(trans_id)
            if not tx: return

            def save_handler(data):
                update_data = {
                    "amount": data["amount"],
                    "description": data["description"],
                    "payment_method_id": data["payment_method_id"],
                    "date": data["date"]
                }
                update_transaction(trans_id, update_data)
                self.page.snack_bar = ft.SnackBar(ft.Text(t("three_panel_transaction_saved", default="Cambios guardados con éxito")), bgcolor=ft.Colors.GREEN_700)
                self.page.snack_bar.open = True
                self.update_view()

            # Corregido: Pasamos los argumentos por posición para evitar colisiones con el nombre del parámetro de tipo
            form = TransactionForm(
                self.page, 
                tx["category_id"], 
                tx["category_name"], 
                tx["type"],
                False, 
                save_handler, 
                None, 
                edit_id=trans_id
            )
            self.page.overlay.append(form)
            form.open = True
            self.page.update()
        except Exception as ex:
            print(f"Error al abrir formulario de edición en Historial: {ex}")

    def _show_delete_confirmation(self, trans_id):
        """Muestra un modal de confirmación irreversible antes de ejecutar la baja de la transacción."""
        if str(trans_id).startswith("tf_"):
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text("Las transferencias relacionales y abonos de carteras deben eliminarse desde la sección de Deudas."), 
                bgcolor=ft.Colors.ORANGE_700
            )
            self.page.snack_bar.open = True
            self.page.update()
            return

        def execute_delete(e):
            try:
                delete_transaction(trans_id)
                delete_dialog.open = False
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text("Movimiento financiero eliminado correctamente."), 
                    bgcolor=ft.Colors.RED_700
                )
                self.page.snack_bar.open = True
                self.update_view()
            except Exception as ex:
                print(f"Error borrando registro: {ex}")

        delete_dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA,
            shape=ft.RoundedRectangleBorder(radius=20),
            title=ft.Text(t("settings_irreversible_action", default="Acción Irreversible ⚠️"), color=COLOR_ATARDECER, weight=ft.FontWeight.BOLD, size=18),
            content=ft.Container(
                content=ft.Text("¿Estás seguro de eliminar permanentemente este movimiento de tu historial financiero? Se recalcularán tus balances globales.", color=ft.Colors.BLACK87, size=14), 
                width=440, 
                padding=5
            ),
            actions=[
                ft.TextButton(t("settings_cancel", default="Cancelar"), on_click=lambda _: setattr(delete_dialog, "open", False) or self.page.update()),
                ft.FilledButton(t("settings_confirm_delete", default="Eliminar"), bgcolor=ft.Colors.RED_600, color=ft.Colors.WHITE, on_click=execute_delete, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)))
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        self.page.overlay.append(delete_dialog)
        delete_dialog.open = True
        self.page.update()

    def update_view(self):
        self.kpi_container.content = self.build_kpi_section()
        self.chart_container.content = self.build_chart_section()
        self.update_transactions_data()
        
        self.kpi_container.update()
        self.chart_container.update()
        self.main_column.update()
        self.page.update()

def create_historial_view(page: ft.Page) -> ft.Container:
    view = HistorialView(page)
    return view.get_view()