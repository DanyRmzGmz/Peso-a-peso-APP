"""
Vista General (Dashboard) de la aplicación.
Muestra métricas clave, liquidez, gráficos y el detalle del mes actual.
Optimizado para adaptabilidad responsiva, tipografía crecida y formateo de gráficas profesional.
"""
import flet as ft
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker  
import io
import base64
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from core.colors import COLOR_ARENA, COLOR_OCEANO, COLOR_ATARDECER, COLOR_CREMA, COLOR_BLANCO, COLOR_CIAN, GRADIENTE_FONDO_SUAVE
from core.formatters import format_currency
from core.translations import t
from database.connection import (
    get_balance_by_payment_method,
    get_current_month_dates,
    get_daily_trend,
    get_expenses_by_category_summary,
    get_income_by_category_summary,
    get_filtered_transactions,
    get_historical_balance,
    get_payment_methods,
    get_setting,
    get_connection
)

class GeneralView:
    """Vista principal del dashboard con métricas, gráficos y detalles."""

    def __init__(self, page: ft.Page):
        self.page = page
        self.selected_chart_tab = 0 
        self.show_chart_filter = False  
        self.search_query = ""          
        
        self.show_recurring_only = False

        self.sort_column = "date"
        self.date_sort_desc = True
        self.amount_sort_desc = True
        
        self.setup_ui()

    def _clean_decimals(self, currency_str: str) -> str:
        """Remueve los decimales de la cadena formateada únicamente si terminan en .00"""
        if currency_str.endswith(".00"):
            return currency_str[:-3]
        return currency_str

    def _format_millions(self, x, pos):
        """Formatea los números grandes del eje de la gráfica a formato humano (Ej: 2.5M o número limpio)."""
        if abs(x) >= 1_000_000:
            return f'${x*1e-6:.1f}M'
        elif abs(x) >= 1_000:
            return f'${x*1e-3:.0f}K'
        return f'${x:.0f}'

    def _on_chart_filter_change(self, e):
        """Manejador reactivo para actualizar el lienzo del gráfico al conmutar el switch superior."""
        self.show_chart_filter = e.control.value
        self.chart_container.content = self.build_unified_chart_section()
        self.chart_container.update()
        
    def _toggle_recurring_filter(self, e):
        """Manejador reactivo del switch para filtrar movimientos recurrentes en tiempo real."""
        self.show_recurring_only = e.control.value
        self.table_inner_container.content = self.build_recent_transactions_table()
        self.table_inner_container.update()

    def _toggle_date_sort(self, e):
        """Conmutador reactivo para ordenar los movimientos por Fecha."""
        self.sort_column = "date"
        self.date_sort_desc = not self.date_sort_desc
        self.table_inner_container.content = self.build_recent_transactions_table()
        self.table_inner_container.update()

    def _toggle_amount_sort(self, e):
        """Conmutador reactivo para ordenar los movimientos por Monto."""
        self.sort_column = "amount"
        self.amount_sort_desc = not self.amount_sort_desc
        self.table_inner_container.content = self.build_recent_transactions_table()
        self.table_inner_container.update()

    def setup_ui(self):
        """Configura todos los componentes de la UI con límite de 1300px."""
        self.chart_container = ft.Container() 
        self.table_inner_container = ft.Container()

        center_wrapper = ft.Container(
            content=self.build_content(),
            width=1300,
            alignment=ft.Alignment(0, -1)
        )
        
        self.main_container = ft.Container(
            gradient=GRADIENTE_FONDO_SUAVE,
            expand=True,
            padding=ft.padding.all(30),
            alignment=ft.Alignment(0, -1),
            content=center_wrapper
        )

    def _get_dashboard_transactions(self):
        """Extrae el universo de movimientos mensuales acoplando transferencias, deudas y gastos de tarjetas."""
        start, end = get_current_month_dates()
        raw_txs = get_filtered_transactions(start, end, None, is_recurrence_view=False)
        transactions_list = [dict(t_val) for t_val in raw_txs]
        synthetic_transfers = []

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

                # Lado del Egreso (Origen)
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
                
                # Lado del Ingreso (Destino - Excluyendo tarjetas de crédito para evitar duplicidad)
                if row["destination_method_id"] is not None and row["dest_type"] != "card":
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
            print(f"Error mapping dashboard: {ex}")

        transactions_list.extend(synthetic_transfers)
        
        if self.show_recurring_only:
            transactions = [t for t in transactions_list if int(t.get("is_recurrence_active", 0)) == 2]
        else:
            transactions = [t for t in transactions_list if int(t.get("is_recurrence_active", 0)) != 1]
        
        def _get_sort_timestamp(tx_dict) -> str:
            raw_date_str = tx_dict.get("date", "")
            if len(raw_date_str) == 10:
                return f"{raw_date_str} 00:00:00"
            return raw_date_str

        if self.sort_column == "date":
            transactions.sort(key=lambda x: (_get_sort_timestamp(x), str(x.get("id", ""))), reverse=self.date_sort_desc)
        elif self.sort_column == "amount":
            transactions.sort(key=lambda x: x.get("amount", 0.0), reverse=self.amount_sort_desc)
            
        return transactions

    def build_content(self):
        """Construye el contenido principal del dashboard."""
        username = get_setting("username", "Usuario")
        now = datetime.now()
        
        meses_es = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        meses_en = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        
        current_lang = get_setting("language", "es")
        if current_lang == "es":
            txt_saludo = f"Hola {username}, este es tu resumen de {meses_es[now.month - 1]} {now.year}"
        else:
            txt_saludo = f"Hello {username}, this is your summary for {meses_en[now.month - 1]} {now.year}"

        header_context = ft.Column([
            ft.Text(txt_saludo, size=32, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
        ], spacing=10)

        kpi_section = self.build_kpi_section()

        liquidity_container = ft.Container(
            bgcolor=COLOR_BLANCO,
            border_radius=20,
            padding=25,
            border=ft.border.all(1, ft.Colors.with_opacity(0.1, COLOR_OCEANO)),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=20, color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK), offset=ft.Offset(0, 10)),
            content=self.build_liquidity_section()
        )

        self.chart_container.content = self.build_unified_chart_section()
        self.table_inner_container.content = self.build_recent_transactions_table()
        
        transactions_container = ft.Container(
            bgcolor=COLOR_BLANCO,
            border_radius=20,
            padding=25,
            border=ft.border.all(1, ft.Colors.with_opacity(0.1, COLOR_OCEANO)),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=20, color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK), offset=ft.Offset(0, 10)),
            content=self.table_inner_container
        )

        return ft.Column(
            controls=[
                header_context,
                ft.Container(height=10),
                kpi_section, 
                ft.Container(height=15),
                ft.ResponsiveRow([
                    ft.Column([liquidity_container], col={"sm": 12, "md": 12, "lg": 12}),
                ]),
                ft.Container(height=15),
                self.chart_container,
                ft.Container(height=15),
                transactions_container 
            ],
            spacing=20,
            expand=True,
            scroll=ft.ScrollMode.AUTO
        )

    def build_kpi_section(self):
        """Calcula los KPIs del Dashboard aislando transferencias pero considerando amortizaciones como egresos."""
        transactions = self._get_dashboard_transactions()
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

        for transaction in transactions:
            if int(transaction.get("is_recurrence_active", 0)) == 1:
                continue

            amount = transaction.get("amount", 0)
            metodo_nombre = str(transaction.get("payment_method_name", "")).lower().strip()
            m_id = str(transaction.get("payment_method_id") or "")
            tipo_metodo_real = method_types_by_id.get(m_id, "")
            
            if not tipo_metodo_real:
                tipo_metodo_real = method_types_by_name.get(metodo_nombre, "")
            
            is_cash = (tipo_metodo_real == "cash") or ("efectivo" in metodo_nombre)
            is_credit = (tipo_metodo_real == "card")
            
            category_clean = str(transaction.get("category_name", "")).lower().strip()
            desc_clean = str(transaction.get("description", "")).lower().strip()
            
            is_card_or_loan_payment = (
                category_clean in ["pago de tarjetas", "pago de deudas", "pago de tarjeta"] 
                or "pago desde:" in desc_clean 
                or "pago a tarjeta" in desc_clean 
                or "abono a préstamo" in desc_clean
            )
            is_pure_transfer = (category_clean == "transferencia") or str(transaction.get("id", "")).startswith("tf_in_") or (str(transaction.get("id", "")).startswith("tf_out_") and not is_card_or_loan_payment)

            if transaction.get("type") == "income":
                if not is_card_or_loan_payment and not is_pure_transfer:
                    ingresos_total += amount
                    if is_cash: ingresos_efectivo += amount
                    else: ingresos_debito += amount
            elif transaction.get("type") == "expense":
                if not is_pure_transfer:
                    gastos_total += amount
                    if is_cash: gastos_efectivo += amount
                    elif is_credit: gastos_credito += amount
                    else: gastos_debito += amount

        saldo_periodo = ingresos_total - gastos_total
        
        # Obtener el saldo arrastrado real consultando el día anterior al inicio del mes
        start_date_str, _ = get_current_month_dates()
        try:
            start_date_obj = datetime.strptime(start_date_str, "%Y-%m-%d")
            previous_day_str = (start_date_obj - timedelta(days=1)).strftime("%Y-%m-%d")
            saldo_arrastrado = get_historical_balance(previous_day_str, None)
        except Exception:
            saldo_arrastrado = 0

        payment_balances = get_balance_by_payment_method()
        card_debt_balance = sum(pb.get("balance", 0) for pb in payment_balances if pb.get("type", "") == "card")
        total_credit_limit = sum(m.get("credit_limit", 0) for m in methods if m.get("type") == "card")
        credit_available = total_credit_limit + card_debt_balance

        color_saldo_periodo = ft.Colors.RED_400 if saldo_periodo < 0 else ft.Colors.GREEN_400

        str_saldo_periodo = self._clean_decimals(format_currency(saldo_periodo))
        str_ingresos_total = self._clean_decimals(format_currency(ingresos_total))
        str_ingresos_efectivo = self._clean_decimals(format_currency(ingresos_efectivo))
        str_ingresos_debito = self._clean_decimals(format_currency(ingresos_debito))
        str_credit_available = self._clean_decimals(format_currency(credit_available))
        
        str_dragged_balance = self._clean_decimals(format_currency(saldo_arrastrado))
        str_gastos_total = self._clean_decimals(format_currency(gastos_total))
        str_gastos_efectivo = self._clean_decimals(format_currency(gastos_efectivo))
        str_gastos_debito = self._clean_decimals(format_currency(gastos_debito))
        str_gastos_credito = self._clean_decimals(format_currency(gastos_credito))

        row1 = ft.Row([
            self._build_kpi_card_unified("📊 " + t("general_kpi_period_balance"), str_saldo_periodo, ft.Colors.BLACK, color_saldo_periodo),
            self._build_kpi_card_unified("📈 " + t("general_kpi_income"), str_ingresos_total, COLOR_OCEANO, ft.Colors.GREEN_400),
            self._build_kpi_card_unified("💵 " + t("general_kpi_cash"), str_ingresos_efectivo, COLOR_OCEANO, ft.Colors.GREEN_400),
            self._build_kpi_card_unified("💳 " + t("general_kpi_debit_card"), str_ingresos_debito, COLOR_OCEANO, ft.Colors.GREEN_400),
            self._build_kpi_card_unified("🛡️ " + t("general_kpi_available_credit"), str_credit_available, COLOR_OCEANO, COLOR_OCEANO),
        ], spacing=15, scroll=ft.ScrollMode.AUTO)

        row2 = ft.Row([
            self._build_kpi_card_unified("⏳ " + t("general_kpi_dragged_balance"), str_dragged_balance, ft.Colors.BLACK, ft.Colors.BLUE_GREY_400),
            self._build_kpi_card_unified("📉 " + t("general_kpi_expenses"), str_gastos_total, COLOR_ATARDECER, COLOR_ATARDECER),
            self._build_kpi_card_unified("💵 " + t("general_kpi_cash"), str_gastos_efectivo, COLOR_ATARDECER, COLOR_ATARDECER),
            self._build_kpi_card_unified("💳 " + t("general_kpi_debit_card"), str_gastos_debito, COLOR_ATARDECER, COLOR_ATARDECER),
            self._build_kpi_card_unified("💳 " + t("general_kpi_credit_card"), str_gastos_credito, COLOR_ATARDECER, COLOR_ATARDECER),
        ], spacing=15, scroll=ft.ScrollMode.AUTO)

        return ft.Column([row1, row2], spacing=15)

    def _build_kpi_card_unified(self, full_title_with_icon, amount, title_color, number_color):
        """Construye tarjetas KPI con icono y texto en una sola línea, evitando desbordamientos."""
        return ft.Container(
            bgcolor=COLOR_BLANCO, 
            padding=ft.padding.symmetric(vertical=15, horizontal=20), 
            border_radius=15,
            border=ft.border.all(1, ft.Colors.with_opacity(0.1, COLOR_OCEANO)),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=10, color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK), offset=ft.Offset(0, 5)),
            width=245,  
            height=100,
            content=ft.Column([
                ft.Text(
                    full_title_with_icon, 
                    size=16,  
                    color=title_color, 
                    weight=ft.FontWeight.W_600, 
                    overflow=ft.TextOverflow.ELLIPSIS
                ),
                ft.Text(
                    amount, 
                    size=28,  
                    color=number_color, 
                    weight=ft.FontWeight.BOLD,
                    overflow=ft.TextOverflow.CLIP  
                )
            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.START)
        )
        
    def build_liquidity_section(self):
        payment_balances = get_balance_by_payment_method()
        
        cash_balance = 0
        bit_balance = 0
        
        for pb in payment_balances:
            p_type = pb.get("type", "")
            bal = pb.get("balance", 0)
            if p_type == "cash":
                cash_balance += bal
            elif p_type == "bank_account":
                bit_balance += bal
                
        liquidez_total = cash_balance + bit_balance
        
        str_cash = self._clean_decimals(format_currency(cash_balance))
        str_bit = self._clean_decimals(format_currency(bit_balance))
        str_liq = self._clean_decimals(format_currency(liquidez_total))
        
        return ft.Column(
            controls=[
                ft.Row([
                    ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED, color=COLOR_OCEANO, size=22),
                    ft.Text(t("general_liquidity_title"), size=20, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
                ], spacing=10),
                ft.ResponsiveRow(
                    controls=[
                        ft.Column([self.create_liquidity_item(label=t("general_liquidity_cash"), amount_str=str_cash, emoji_icon="💵", bg_color=ft.Colors.with_opacity(0.1, ft.Colors.GREEN))], col={"sm": 12, "md": 4}),
                        ft.Column([self.create_liquidity_item(label=t("general_liquidity_debit"), amount_str=str_bit, emoji_icon="🏦", bg_color=ft.Colors.with_opacity(0.1, ft.Colors.BLUE))], col={"sm": 12, "md": 4}),
                        ft.Column([self.create_liquidity_item(label=t("general_liquidity_total"), amount_str=str_liq, emoji_icon="💰", bg_color=ft.Colors.with_opacity(0.1, ft.Colors.AMBER))], col={"sm": 12, "md": 4})
                    ],
                    spacing=15
                )
            ],
            spacing=20
        )

    def create_liquidity_item(self, label, amount_str, emoji_icon, bg_color):
        is_negative = "-" in amount_str
        text_color = ft.Colors.RED_400 if is_negative else COLOR_OCEANO

        return ft.Container(
            padding=ft.padding.all(18), border_radius=15, bgcolor=COLOR_CREMA, 
            border=ft.border.all(1, ft.Colors.with_opacity(0.05, COLOR_OCEANO)),
            content=ft.Row(
                controls=[
                    ft.Container(content=ft.Text(emoji_icon, size=26), bgcolor=bg_color, padding=12, border_radius=12),
                    ft.Column(
                        controls=[
                            ft.Text(label, size=15, color=ft.Colors.GREY_700, weight=ft.FontWeight.W_600),
                            ft.Text(amount_str, size=22, weight=ft.FontWeight.BOLD, color=text_color)  
                        ],
                        spacing=3, alignment=ft.MainAxisAlignment.CENTER 
                    )
                ],
                alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=15
            )
        )

    def build_recent_transactions_table(self):
        """Construye el listado del mes actual con ordenación e introspección de texto localizado."""
        recent_transactions = self._get_dashboard_transactions()[:20]
        
        self.recurring_switch = ft.Switch(
            label=t("historial_filter_recurring", default="Solo recurrentes 🔄"),
            value=self.show_recurring_only,
            active_color=COLOR_OCEANO,
            on_change=self._toggle_recurring_filter
        )
        
        header_row = ft.Row(
            controls=[
                ft.Row([
                    ft.Icon(ft.Icons.HISTORY_ROUNDED, color=COLOR_OCEANO, size=22),
                    ft.Text(t("general_recent_transactions"), size=20, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
                ], spacing=10),
                self.recurring_switch
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        )
        
        if not recent_transactions:
            txt_empty = t("general_no_recurring_txs", default="Sin transacciones recurrentes en este mes") if self.show_recurring_only else t("general_no_transactions", "Sin transacciones en este mes")
            
            table_content = ft.Container(
                padding=40, alignment=ft.Alignment(0, 0),
                content=ft.Column([
                    ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED, size=48, color=ft.Colors.GREY_300),
                    ft.Text(txt_empty, size=16, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
            )
        else:
            rows = []
            for i, transaction in enumerate(recent_transactions):
                is_expense = transaction["type"] == "expense"
                amount_color = COLOR_ATARDECER if is_expense else ft.Colors.GREEN_400
                amount_prefix = "-" if is_expense else "+"
                indicador = "▼" if is_expense else "▲"
                row_bg_color = ft.Colors.TRANSPARENT if i % 2 == 0 else ft.Colors.with_opacity(0.02, COLOR_OCEANO)
                
                # Inyección del prefijo 🔄 junto al indicador de celda si el registro es recurrente activo
                is_rec = int(transaction.get("is_recurrence_active", 0)) == 2
                tipo_visual = f"🔄 {indicador}" if is_rec else indicador

                raw_desc = transaction.get("description") or transaction.get("category_name") or ""
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
                elif "pago a tarjeta:" in desc_text.lower():
                    parts = desc_text.split(":")
                    if len(parts) > 1:
                        desc_text = f"{t('pago_a_tarjeta', default='Pago a tarjeta')}: {parts[1].strip()}"
                elif "abono a préstamo:" in desc_text.lower():
                    parts = desc_text.split(":")
                    if len(parts) > 1:
                        desc_text = f"{t('abono a préstamo', default='Abono a préstamo')}: {parts[1].strip()}"
                else:
                    clean_key = desc_text.replace("✨", "").lower().strip().replace(" ", "_")
                    translated_lookup = t(clean_key, default="")
                    if translated_lookup: desc_text = translated_lookup

                if len(desc_text) > 30:
                    desc_text = desc_text[:27] + "..."
                
                str_amount = self._clean_decimals(format_currency(transaction['amount']))
                cat_translated = t(str(transaction["category_name"]).lower().strip().replace(" ", "_"), default=transaction["category_name"])
                
                raw_method = transaction.get("payment_method_name")
                method_translated = t(str(raw_method).lower().strip().replace(" ", "_"), default=str(raw_method)) if raw_method else t("deudas_unknown_account", default="Desconocido")
                
                rows.append(
                    ft.DataRow(
                        color=row_bg_color,
                        cells=[
                            ft.DataCell(ft.Text(tipo_visual, color=amount_color, size=16 if is_rec else 20, weight=ft.FontWeight.BOLD)),
                            ft.DataCell(ft.Text(transaction["date"].split("-")[2] + "/" + transaction["date"].split("-")[1], weight=ft.FontWeight.W_500)),
                            ft.DataCell(ft.Row([
                                ft.Container(content=ft.Text(transaction["category_icon"], size=14), bgcolor=COLOR_CREMA, padding=6, border_radius=6),
                                ft.Text(cat_translated, weight=ft.FontWeight.W_600, size=14)
                            ], spacing=10)),
                            ft.DataCell(ft.Text(desc_text, color=ft.Colors.GREY_700)),
                            ft.DataCell(ft.Row([
                                ft.Text(transaction["payment_method_icon"]),
                                ft.Text(method_translated, size=13, weight=ft.FontWeight.W_500)
                            ], spacing=8)),
                            ft.DataCell(ft.Text(f"{amount_prefix}{str_amount}", color=amount_color, weight=ft.FontWeight.BOLD))
                        ]
                    )
                )
                
            tabla = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("")),
                    ft.DataColumn(
                        ft.Row([
                            ft.Text(t("historial_table_date", "Fecha")),
                            ft.IconButton(icon=ft.Icons.ARROW_DOWNWARD if self.date_sort_desc else ft.Icons.ARROW_UPWARD, icon_size=14, padding=0, on_click=self._toggle_date_sort)
                        ], spacing=2)
                    ),
                    ft.DataColumn(ft.Text(t("historial_table_category", "Categoría"))),
                    ft.DataColumn(ft.Text(t("historial_table_description", "Descripción"))),
                    ft.DataColumn(ft.Text(t("historial_table_payment", "Método"))),
                    ft.DataColumn(
                        ft.Row([
                            ft.Text(t("historial_table_amount", "Monto")),
                            ft.IconButton(icon=ft.Icons.ARROW_DOWNWARD if self.amount_sort_desc else ft.Icons.ARROW_UPWARD, icon_size=14, padding=0, on_click=self._toggle_amount_sort)
                        ], spacing=2),
                        numeric=True
                    )
                ],
                rows=rows,
                heading_row_color=ft.Colors.with_opacity(0.05, COLOR_OCEANO),
                data_text_style=ft.TextStyle(size=14, color=ft.Colors.GREY_800),
                heading_text_style=ft.TextStyle(size=15, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
                column_spacing=35,
                horizontal_lines=ft.BorderSide(1, ft.Colors.with_opacity(0.05, ft.Colors.BLACK)),
            )
            
            table_content = ft.Column([ft.Row([tabla], scroll=ft.ScrollMode.AUTO)], scroll=ft.ScrollMode.AUTO)
            
        return ft.Column([header_row, table_content], spacing=15)

    def _fig_to_base64_image(self, fig) -> ft.Image:
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', transparent=True)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return ft.Image(src=f"data:image/png;base64,{img_base64}", fit="contain")

    def build_unified_chart_section(self):
        """Construye los gráficos analíticos basándose síncronamente en el set de datos en memoria (Incluyendo abonos)."""
        def handle_tab_change(index):
            self.selected_chart_tab = index
            self.chart_container.content = self.build_unified_chart_section()
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
                    content=ft.Text(label, color=COLOR_OCEANO if is_selected else ft.Colors.GREY_500, weight=ft.FontWeight.BOLD, size=16),
                    padding=ft.padding.symmetric(horizontal=15, vertical=10),
                    bgcolor=ft.Colors.with_opacity(0.08, COLOR_OCEANO) if is_selected else ft.Colors.TRANSPARENT,
                    border_radius=10,
                    on_click=lambda e, i=index: handle_tab_change(i),
                    ink=True
                )
            )
        
        # Mutación adaptativa del switch según pestaña activa unificando bilingüismo
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
                ft.Row(controls=tab_controls, spacing=8, scroll=ft.ScrollMode.AUTO),
                chart_switch
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

        chart_txs = self._ensure_correct_mapping_for_charts()
        chart_layout = None 
        metrics_panel = None
        
        if self.selected_chart_tab in [0, 1]:
            fig, ax = plt.subplots(figsize=(12, 5), dpi=100)
            fig.patch.set_alpha(0)
            ax.set_facecolor('none')
            
            trend_map = {}
            for tx in chart_txs:
                key = tx["date"][:10]
                if key not in trend_map:
                    trend_map[key] = {"date": key, "income": 0.0, "expense": 0.0, "rec_income": 0.0, "rec_expense": 0.0}
                
                amt = tx["amount"]
                is_rec = int(tx.get("is_recurrence_active", 0)) == 2
                
                category_clean = str(tx.get("category_name", "")).lower().strip()
                desc_clean = str(tx.get("description", "")).lower().strip()
                is_card_or_loan_payment = (category_clean in ["pago de tarjetas", "pago de deudas", "pago de tarjeta"] or "pago desde:" in desc_clean or "pago a tarjeta" in desc_clean or "abono a préstamo" in desc_clean)
                is_pure_transfer = (category_clean == "transferencia") or str(tx.get("id", "")).startswith("tf_in_") or (str(tx.get("id", "")).startswith("tf_out_") and not is_card_or_loan_payment)

                if tx["type"] == "income":
                    if not is_card_or_loan_payment and not is_pure_transfer: trend_map[key]["income"] += amt
                    if is_rec: trend_map[key]["rec_income"] += amt
                else:
                    if not is_pure_transfer: trend_map[key]["expense"] += amt
                    if is_rec: trend_map[key]["rec_expense"] += amt

            sorted_keys = sorted(trend_map.keys())
            data = [trend_map[k] for k in sorted_keys]

            if not data: 
                chart_layout = ft.Container(height=300, alignment=ft.Alignment(0, 0), content=ft.Text(t("general_no_data"), color=ft.Colors.GREY_400))
            else:
                x_labels = [k.split("-")[2] for k in sorted_keys]
                indices = list(range(len(data)))
                ax.yaxis.set_major_formatter(ticker.FuncFormatter(self._format_millions))

                net_flows_calc = [d["income"] - d["expense"] for d in data]
                expenses_list = [d["expense"] for d in data]
                avg_net_flow = sum(net_flows_calc) / len(net_flows_calc) if net_flows_calc else 0
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

                if self.selected_chart_tab == 0:
                    ax.plot(x_labels, [d["income"] for d in data], marker='o', color=COLOR_OCEANO, label='Ingresos', linewidth=3, markersize=5)
                    ax.plot(x_labels, [d["expense"] for d in data], marker='o', color=COLOR_ATARDECER, label='Gastos', linewidth=3, markersize=5)
                    if self.show_chart_filter:
                        ax.plot(x_labels, [d["rec_income"] for d in data], marker='s', linestyle='--', color='#218380', label='Ingresos Recurrentes', linewidth=1.5, alpha=0.8)
                        ax.plot(x_labels, [d["rec_expense"] for d in data], marker='s', linestyle='--', color='#E63946', label='Gastos Recurrentes', linewidth=1.5, alpha=0.8)
                    ax.legend(frameon=False, loc="upper left")
                    ax.grid(True, linestyle='--', alpha=0.2, color=COLOR_OCEANO)
                    ax.spines['top'].set_visible(False)
                    ax.spines['right'].set_visible(False)

                elif self.selected_chart_tab == 1:
                    colors_net = [COLOR_OCEANO if val >= 0 else COLOR_ATARDECER for val in net_flows_calc]
                    if self.show_chart_filter:
                        width = 0.35
                        rec_flows = [d["rec_income"] - d["rec_expense"] for d in data]
                        colors_rec = ["#2ECC71" if val >= 0 else "#FF8A8A" for val in rec_flows]
                        ax.bar([i - width/2 for i in indices], net_flows_calc, width=width, color=colors_net, label='Neto Total')
                        ax.bar([i + width/2 for i in indices], rec_flows, width=width, color=colors_rec, label='Neto Recurrente')
                        ax.legend(frameon=False)
                    else:
                        ax.bar(indices, net_flows_calc, color=colors_net, width=0.6, label='Neto Total')
                    ax.set_xticks(indices)
                    ax.set_xticklabels(x_labels)
                    ax.axhline(0, color=COLOR_OCEANO, linewidth=1, alpha=0.3)
                    ax.grid(axis='y', linestyle='--', alpha=0.2, color=COLOR_OCEANO)
                    ax.spines['top'].set_visible(False)
                    ax.spines['right'].set_visible(False)

                chart_layout = ft.Container(content=self._fig_to_base64_image(fig), height=350, alignment=ft.Alignment(0, 0))

        elif self.selected_chart_tab in [2, 3]:
            fig, ax = plt.subplots(figsize=(6, 6), dpi=100) 
            fig.patch.set_alpha(0)
            target_type = "expense" if self.selected_chart_tab == 2 else "income"
            
            cat_map = {}
            for tx in chart_txs:
                if tx["type"] != target_type: continue
                c_clean = str(tx.get("category_name", "")).lower().strip()
                d_clean = str(tx.get("description", "")).lower().strip()
                if (c_clean == "transferencia") or str(tx.get("id", "")).startswith("tf_in_") or (str(tx.get("id", "")).startswith("tf_out_") and c_clean == "transferencia"):
                    continue

                c_name = tx["category_name"]
                
                # Evaluación síncrona de coincidencia ante filtros de búsqueda contextuales
                is_search_match = False
                if self.search_query:
                    is_search_match = (self.search_query in d_clean or self.search_query in c_clean)

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
                chart_layout = ft.Container(height=300, alignment=ft.Alignment(0, 0), content=ft.Text("Sin movimientos en este mes", color=ft.Colors.GREY_400))
            else:
                sizes = [d["total"] for d in data]
                colors, explode = [], []
                
                # Determinar si el modo de resaltado está activo globalmente
                is_highlight_active = self.show_chart_filter or bool(self.search_query)

                for d in data:
                    # Lógica para evaluar si esta rebanada/categoría cumple con los criterios analíticos activos
                    should_explode = False
                    if self.show_chart_filter and d["rec_total"] > 0:
                        should_explode = True
                    if self.search_query and d["has_match"]:
                        should_explode = True

                    if is_highlight_active:
                        if should_explode:
                            colors.append(d["color"])
                            explode.append(0.12)  # Resalta hacia afuera de forma premium
                        else:
                            colors.append("#E0E0E0")  # Color desaturado y disminuido para el resto
                            explode.append(0)
                    else:
                        colors.append(d["color"])
                        explode.append(0)

                total_sum = sum(sizes)
                ax.pie(sizes, colors=colors, explode=explode, startangle=90, wedgeprops=dict(width=0.4, edgecolor='w', linewidth=2))
                ax.axis('equal')
                
                legend_rows = []
                for d in data:
                    pct = (d["total"] / total_sum) * 100 if total_sum > 0 else 0
                    category_name = t(str(d['category']).lower().replace(" ", "_"), default=d['category'])
                    
                    # Evaluar resaltado de texto e iconos para la tarjeta de leyenda correspondiente
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
                        text_color = ft.Colors.GREY_700
                        text_weight = ft.FontWeight.W_500
                        icon_color = d["color"]

                    legend_rows.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Container(width=12, height=12, bgcolor=icon_color, border_radius=4),
                                ft.Text(f"{category_name}", size=14, color=text_color, expand=True, weight=text_weight),
                                ft.Text(f"{pct:.1f}%", size=14, weight=ft.FontWeight.BOLD if should_highlight_text else ft.FontWeight.W_500, color=text_color if is_highlight_active and not should_highlight_text else COLOR_OCEANO),
                            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                            bgcolor=COLOR_CREMA, padding=10, border_radius=10
                        )
                    )
                
                legend_container = ft.Container(width=280, height=300, padding=ft.padding.only(left=20), content=ft.Column(controls=legend_rows, scroll=ft.ScrollMode.AUTO, spacing=8))
                chart_layout = ft.Row([ft.Container(content=self._fig_to_base64_image(fig), expand=True), legend_container], expand=True, alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=20)

        return ft.Container(
            bgcolor=COLOR_BLANCO, border_radius=20, padding=25,
            border=ft.border.all(1, ft.Colors.with_opacity(0.1, COLOR_OCEANO)),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=20, color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK), offset=ft.Offset(0, 10)),
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.INSERT_CHART_ROUNDED, color=COLOR_OCEANO, size=22),
                    ft.Text(t("general_chart_analysis", default="Análisis de Gráficos"), size=20, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
                ], spacing=10),
                ft.Container(height=10),
                header_row,
                ft.Container(height=10),
                ft.Container(content=chart_layout, height=350),
                metrics_panel if metrics_panel else ft.Container()
            ])
        )

    def _ensure_correct_mapping_for_charts(self):
        """Helper para extraer movimientos en memoria unificados para las gráficas analíticas."""
        start, end = get_current_month_dates()
        raw_txs = get_filtered_transactions(start, end, None, is_recurrence_view=False)
        txs = [dict(t_val) for t_val in raw_txs]
        
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
                    computed_desc = f"Abono a préstamo: {row['loan_name']}"
                    cat_name = "Pago de deudas"
                    cat_icon = "🏦"
                elif row["dest_type"] == "card":
                    computed_desc = f"Pago a tarjeta: {row['dest_name']}"
                    cat_name = "Pago de tarjetas"
                    cat_icon = "💳"
                else:
                    computed_desc = row["description"] if row["description"] else f"Transferencia"
                    cat_name = "Transferencia"
                    cat_icon = "🔀"

                txs.append({"id": f"tf_out_{row['id']}", "amount": float(row["amount"]), "description": computed_desc, "type": "expense", "date": row["date"], "category_name": cat_name, "category_icon": cat_icon, "category_color": "#34495E", "payment_method_id": row["source_method_id"], "payment_method_name": row["source_name"], "payment_method_icon": row["source_icon"] or "💳"})
                if row["destination_method_id"] is not None and row["dest_type"] != "card":
                    txs.append({"id": f"tf_in_{row['id']}", "amount": float(row["amount"]), "description": row["description"] or f"Transferencia", "type": "income", "date": row["date"], "category_name": "Transferencia", "category_icon": "🔀", "category_color": "#2ECC71", "payment_method_id": row["destination_method_id"], "payment_method_name": row["dest_name"], "payment_method_icon": row["dest_icon"] or "💳"})
            conn.close()
        except: pass
        return txs

    def get_view(self):
        return self.main_container

def create_general_view(page: ft.Page) -> ft.Container:
    view = GeneralView(page)
    return view.get_view()