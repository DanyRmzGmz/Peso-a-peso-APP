"""
Vista de Deudas de la aplicación.
Permite gestionar y abonar a préstamos a plazos y monitorear tarjetas de crédito revolventes.
Refactorizado con tipografía premium, secciones colapsables interactivas y auto-llenado inteligente.
"""
import flet as ft
from datetime import datetime, timedelta
import calendar
from dateutil.relativedelta import relativedelta
from core.colors import COLOR_OCEANO, COLOR_ATARDECER, COLOR_CREMA, COLOR_BLANCO, COLOR_ARENA, COLOR_CIAN, GRADIENTE_FONDO_SUAVE
from core.formatters import format_currency
from core.translations import t 
from database.connection import (
    get_all_loans_with_progress,
    get_balance_by_payment_method,
    get_payment_methods,
    add_loan,
    update_loan,
    delete_loan,
    add_transfer,
    get_loan_payments,
    get_setting,
    get_current_month_dates, 
    get_card_transactions    
)

MONTH_NAMES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

MONTH_NAMES_EN = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
}

class DeudasView:
    def __init__(self, page: ft.Page):
        self.page = page
        
        # Estados de control interactivo de UI/UX
        self.history_sort_desc = True
        self.loan_sort_desc = True
        self.card_filter_expenses = True
        self.card_filter_incomes = True
        
        # Inicialización estricta de modales para evitar fugas de memoria
        self._init_loan_dialog()
        self._init_delete_loan_dialog()
        self._init_loan_history_dialog() 
        self._init_card_history_dialog()

        # Wrapper centrado con ancho máximo
        self.center_wrapper = ft.Container(
            content=self.build_content(),
            width=1300,
            alignment=ft.Alignment(0, -1)
        )

        # Contenedor global con gradiente de marca
        self.main_container = ft.Container(
            gradient=GRADIENTE_FONDO_SUAVE,
            expand=True,
            padding=20,
            alignment=ft.Alignment(0, -1),
            content=self.center_wrapper
        )

    def _clean_decimals(self, currency_str: str) -> str:
        """Remueve los decimales de la cadena formateada únicamente si terminan en .00"""
        if currency_str.endswith(".00"):
            return currency_str[:-3]
        return currency_str

    def _get_localized_month_name(self, month_int: int) -> str:
        """Devuelve el nombre del mes adaptado al locale actual del usuario configurado."""
        lang = get_setting("language", "es")
        if lang == "es":
            return MONTH_NAMES_ES.get(month_int, "")
        return MONTH_NAMES_EN.get(month_int, "")

    def _calculate_corte_debt(self, item) -> float:
        """Calcula la deuda perteneciente al periodo de corte aplicando la acumulación inversa exacta."""
        cutoff_day = item.get("cutoff_day", 1)
        now = datetime.now()
        
        if now.day >= cutoff_day:
            last_cutoff_dt = datetime(now.year, now.month, cutoff_day)
        else:
            prev_month = now - relativedelta(months=1)
            last_cutoff_dt = datetime(prev_month.year, prev_month.month, cutoff_day)
            
        start_period_dt = last_cutoff_dt - relativedelta(months=1) + timedelta(days=1)
        
        start_scan = start_period_dt.strftime("%Y-%m-%d")
        end_scan = (last_cutoff_dt + relativedelta(months=1) + timedelta(days=1)).strftime("%Y-%m-%d")

        original_corte_debt = 0.0
        payments_after_cutoff = 0.0
        
        try:
            card_txs = get_card_transactions(item["id"], start_scan, end_scan)
            for tx in card_txs:
                try:
                    tx_dt = datetime.strptime(tx["date"][:10], "%Y-%m-%d")
                    if start_period_dt <= tx_dt <= last_cutoff_dt:
                        if tx.get("type", "expense") == "expense":
                            original_corte_debt += tx["amount"]
                        else:
                            original_corte_debt -= tx["amount"]
                    elif tx_dt > last_cutoff_dt:
                        if tx.get("type", "expense") != "expense":
                            payments_after_cutoff += tx["amount"]
                except:
                    pass
        except:
            pass

        remaining_corte = max(0.0, original_corte_debt - payments_after_cutoff)
        if item["balance"] < 0:
            return max(0.0, min(remaining_corte, abs(item["balance"])))
        return 0.0

    def _build_liquidity_summary(self):
        """Construye el cinturón de liquidez con reactividad de color ante números negativos."""
        balances = get_balance_by_payment_method()
        
        liquidez_efectivo = sum(item["balance"] for item in balances if item["type"] == "cash")
        liquidez_debito = sum(item["balance"] for item in balances if item["type"] == "bank_account")
        liquidez_total = liquidez_efectivo + liquidez_debito
        
        str_efectivo = self._clean_decimals(format_currency(liquidez_efectivo))
        str_debito = self._clean_decimals(format_currency(liquidez_debito))
        str_total = self._clean_decimals(format_currency(liquidez_total))

        color_efectivo = ft.Colors.RED_500 if liquidez_efectivo < 0 else COLOR_OCEANO
        color_debito = ft.Colors.RED_500 if liquidez_debito < 0 else COLOR_OCEANO
        color_total = ft.Colors.RED_500 if liquidez_total < 0 else COLOR_OCEANO

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Row([
                        ft.Text("💵", size=16),
                        ft.Text(f"{t('historial_kpi_cash', default='Efectivo')}: {str_efectivo}", size=14, weight=ft.FontWeight.W_600, color=color_efectivo)
                    ], spacing=6),
                    
                    ft.Container(width=1, height=16, bgcolor=ft.Colors.with_opacity(0.2, COLOR_CIAN), margin=ft.padding.symmetric(horizontal=15)),
                    
                    ft.Row([
                        ft.Text("🏦", size=16),
                        ft.Text(f"{t('settings_account_type_debit', default='Débito')}: {str_debito}", size=14, weight=ft.FontWeight.W_600, color=color_debito)
                    ], spacing=6),
                    
                    ft.Container(width=1, height=16, bgcolor=ft.Colors.with_opacity(0.2, COLOR_CIAN), margin=ft.padding.symmetric(horizontal=15)),
                    
                    ft.Row([
                        ft.Text("💰", size=16),
                        ft.Text(f"{t('deudas_available', default='Total Disponible:')} {str_total}", size=14, weight=ft.FontWeight.BOLD, color=color_total)
                    ], spacing=6),
                ],
                alignment=ft.MainAxisAlignment.CENTER, 
            ),
            bgcolor=COLOR_BLANCO,
            padding=16,
            border_radius=12,
            border=ft.border.all(1, ft.Colors.with_opacity(0.08, COLOR_CIAN)),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=10, color=ft.Colors.with_opacity(0.02, ft.Colors.BLACK), offset=ft.Offset(0, 4))
        )

    def build_content(self):
        """Construye el contenido principal de la sección de créditos."""
        all_loans = get_all_loans_with_progress()
        active_loans = [l for l in all_loans if l["remaining"] > 0]
        completed_loans = [l for l in all_loans if l["remaining"] <= 0]

        # Detectar el idioma actual para el fallback dinámico inline en caso de que no encuentre la clave
        current_lang = get_setting("language", "es")
        default_empty_msg = (
            "Aún no tienes préstamos liquidados al 100%." 
            if current_lang == "es" 
            else "You don't have any 100% paid off loans yet."
        )

        return ft.Column(
            controls=[
                self._build_header_actions(),
                ft.Container(height=5),
                self._build_liquidity_summary(),
                ft.Container(height=10),
                
                ft.Text(t("deudas_credit_cards", default="Tarjetas de Crédito (Revolventes)"), size=20, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
                self._build_credit_cards_section(),
                ft.Container(height=10),
                
                ft.Text(t("deudas_active_loans", default="Préstamos y Créditos a Plazos (Activos)"), size=20, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
                self._build_loans_section(active_loans, t("deudas_no_active_loans", default="No tienes préstamos activos.")),
                ft.Container(height=10),
                
                ft.Text(t("deudas_completed_loans", default="Deudas y Préstamos Concluidos"), size=20, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
                self._build_loans_section(completed_loans, t("deudas_no_completed_loans", default=default_empty_msg)),
            ],
            spacing=15, expand=True, scroll=ft.ScrollMode.AUTO
        )

    def _build_header_actions(self):
        """Sección de botones de acciones principales con iconos nativos unificados."""
        return ft.Row(
            controls=[
                ft.FilledButton(
                    t("deudas_new_loan", default="Nuevo Préstamo"), 
                    icon=ft.Icons.ADD_CARD,          
                    bgcolor=COLOR_OCEANO, 
                    color=COLOR_BLANCO,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _: self._show_add_loan_dialog()
                ),
                ft.FilledButton(
                    t("deudas_payment_loan", default="Abonar Préstamo"), 
                    icon=ft.Icons.ACCOUNT_BALANCE,          
                    bgcolor=ft.Colors.GREEN_600, 
                    color=COLOR_BLANCO,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _: self._show_loan_payment_dialog()
                ),
                ft.FilledButton(
                    t("deudas_payment_card", default="Abonar Tarjeta"), 
                    icon=ft.Icons.CREDIT_SCORE,          
                    bgcolor=ft.Colors.BLUE_600, 
                    color=COLOR_BLANCO,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _: self._show_card_payment_dialog()
                ),
                ft.FilledButton(
                    t("deudas_own_transfer", default="Transferencia Propia"), 
                    icon=ft.Icons.SWAP_HORIZ,          
                    bgcolor=ft.Colors.CYAN, 
                    color=COLOR_BLANCO,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _: self._show_own_transfer_dialog()
                )
            ],
            spacing=12,
            wrap=True
        )

    def _build_credit_cards_section(self):
        """Construye las tarjetas de crédito mostrando la deuda total y la ecuación desglosada del corte actual."""
        balances = get_balance_by_payment_method()
        cards_ui = []

        for item in balances:
            if item["type"] == "card":
                limit = item.get("credit_limit", 0)
                raw_balance = item["balance"]
                is_frozen = item.get("status") == "frozen"
                
                card_name = t(str(item["name"]).lower().replace(" ", "_"), default=item["name"])
                card_bgcolor = COLOR_BLANCO
                
                if is_frozen:
                    card_name += t("settings_frozen_badge", default=" ❄️ [Congelada]")
                    card_bgcolor = ft.Colors.BLUE_50

                cutoff_debt = self._calculate_corte_debt(item)

                if raw_balance < 0:
                    debt = abs(raw_balance)
                    saldo_a_favor = 0
                    usage_ratio = (debt / limit) if limit > 0 else 0
                    progress_color = ft.Colors.RED_400 if usage_ratio > 0.8 else COLOR_OCEANO
                    texto_deuda = f"{t('deudas_debt_label', default='Deuda Total:')} {self._clean_decimals(format_currency(debt))} / {self._clean_decimals(format_currency(limit))}"
                    disponible_real = max(0, limit - debt)
                else:
                    debt = 0
                    saldo_a_favor = raw_balance
                    usage_ratio = 0
                    progress_color = ft.Colors.GREEN_400
                    if saldo_a_favor > 0:
                        texto_deuda = f"{t('deudas_favor_balance', default='Saldo a Favor:')} {self._clean_decimals(format_currency(saldo_a_favor))}"
                    else:
                        texto_deuda = f"{t('deudas_debt_label', default='Deuda Total:')} $0 / {self._clean_decimals(format_currency(limit))}"
                    disponible_real = limit + saldo_a_favor

                cutoff_day = item.get("cutoff_day", 1)
                now = datetime.now()
                if now.day >= cutoff_day:
                    last_cutoff_dt = datetime(now.year, now.month, cutoff_day)
                else:
                    prev_month = now - relativedelta(months=1)
                    last_cutoff_dt = datetime(prev_month.year, prev_month.month, cutoff_day)
                start_period_dt = last_cutoff_dt - relativedelta(months=1) + timedelta(days=1)
                
                start_scan = start_period_dt.strftime("%Y-%m-%d")
                end_scan = (last_cutoff_dt + relativedelta(months=1) + timedelta(days=1)).strftime("%Y-%m-%d")

                original_corte_debt = 0.0
                payments_after_cutoff = 0.0
                try:
                    card_txs = get_card_transactions(item["id"], start_scan, end_scan)
                    for tx in card_txs:
                        tx_dt = datetime.strptime(tx["date"][:10], "%Y-%m-%d")
                        if start_period_dt <= tx_dt <= last_cutoff_dt:
                            if tx.get("type", "expense") == "expense":
                                original_corte_debt += tx["amount"]
                            else:
                                original_corte_debt -= tx["amount"]
                        elif tx_dt > last_cutoff_dt:
                            if tx.get("type", "expense") != "expense":
                                payments_after_cutoff += tx["amount"]
                except:
                    pass

                str_corte_restante = self._clean_decimals(format_currency(cutoff_debt))
                str_original_corte = self._clean_decimals(format_currency(original_corte_debt))
                str_pagado_corte = self._clean_decimals(format_currency(payments_after_cutoff))

                btn_info = ft.Container(
                    content=ft.Text("ℹ️", size=15, color=COLOR_OCEANO),
                    padding=6, border_radius=6, ink=True, 
                    on_click=lambda e, card=item: self._show_card_history_dialog(card)
                )

                cards_ui.append(ft.Container(
                    width=350, bgcolor=card_bgcolor, padding=20, border_radius=16,
                    border=ft.border.all(1, ft.Colors.with_opacity(0.12, COLOR_CIAN) if is_frozen else (ft.Colors.with_opacity(0.08, COLOR_CIAN) if saldo_a_favor == 0 else ft.Colors.GREEN_300)),
                    shadow=ft.BoxShadow(spread_radius=0, blur_radius=12, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 6)),
                    content=ft.Column([
                        ft.Row([
                            ft.Row([ft.Text(item["icon"], size=26), ft.Text(card_name, size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK)], spacing=8),
                            btn_info 
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(height=12, color=ft.Colors.BLACK12),
                        ft.Row([
                            ft.Column([ft.Text(t("deudas_cutoff_day", default="Día Corte"), size=11, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_500), ft.Text(f"{item.get('cutoff_day', '-')}", size=13, weight=ft.FontWeight.BOLD)], spacing=2),
                            ft.Column([ft.Text(t("deudas_due_day", default="Día Pago"), size=11, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_500), ft.Text(f"{item.get('payment_due_day', '-')}", size=13, weight=ft.FontWeight.BOLD)], spacing=2),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Container(height=2),
                        ft.Text(texto_deuda, size=13, weight=ft.FontWeight.W_600, color=ft.Colors.GREEN_600 if saldo_a_favor > 0 else ft.Colors.GREY_700),
                        
                        ft.Text(f"{t('deudas_pay_at_cutoff', default='Por pagar al corte:')} {str_corte_restante} ({str_corte_restante} = {str_original_corte} - {str_pagado_corte})", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400 if cutoff_debt > 0 else ft.Colors.GREEN_600),
                        
                        ft.ProgressBar(value=usage_ratio, color=progress_color, bgcolor=ft.Colors.GREY_100, height=8),
                        ft.Text(f"{t('deudas_available', default='Disponible:')} {self._clean_decimals(format_currency(disponible_real))}", size=12, color=ft.Colors.GREEN_600 if disponible_real > 0 else ft.Colors.GREY_600, weight=ft.FontWeight.W_600)
                    ], spacing=6)
                ))
                
        if not cards_ui:
            return ft.Text(t("deudas_no_cards", default="No tienes tarjetas configuradas."), color=ft.Colors.GREY_500, italic=True, size=14)
            
        return ft.Row(controls=cards_ui, wrap=True, spacing=15)

    def _build_loans_section(self, loans_list, empty_message):
        if not loans_list:
            return ft.Text(empty_message, color=ft.Colors.GREY_500, italic=True, size=14)

        loans_ui = []
        for loan in loans_list:
            total_con_interes = loan["total_amount"] + (loan["total_amount"] * (loan["interest_rate"] / 100))
            progress = min(1.0, loan["total_paid"] / total_con_interes) if total_con_interes > 0 else 1.0
            
            bar_color = ft.Colors.GREEN_400 if progress >= 1.0 else (ft.Colors.GREEN_400 if progress > 0.75 else (ft.Colors.ORANGE_400 if progress > 0.3 else ft.Colors.RED_400))
            
            db_date = loan.get('start_date', '')
            try:
                display_date = datetime.strptime(db_date, "%Y-%m-%d").strftime("%d/%m/%Y")
            except ValueError:
                display_date = "N/A"

            db_unit = loan.get('term_unit', 'Meses')
            unit_key = {"Semanas": "deudas_weeks", "Meses": "deudas_months", "Años": "deudas_years"}.get(db_unit, db_unit)
            unit_text = t(unit_key, default=db_unit)

            btn_info = ft.Container(content=ft.Text("ℹ️", size=15, color=COLOR_OCEANO), padding=4, border_radius=4, ink=True, on_click=lambda e, l=loan: self._show_loan_history_dialog(l))
            
            is_completed = loan["remaining"] <= 0
            btn_editar = ft.Container(
                content=ft.Text("✏️", size=15, color=ft.Colors.GREY_400 if is_completed else COLOR_OCEANO), 
                padding=4, 
                border_radius=4, 
                ink=not is_completed,
                opacity=0.4 if is_completed else 1.0,
                on_click=(lambda e, l=loan: self._show_edit_loan_dialog(l)) if not is_completed else None
            )
            
            btn_eliminar = ft.Container(content=ft.Text("🗑️", size=15, color=ft.Colors.RED_400), padding=4, border_radius=4, ink=True, on_click=lambda e, l=loan: self._confirm_delete_loan(l))

            str_paid = self._clean_decimals(format_currency(loan['total_paid']))
            resta_real = max(0.0, total_con_interes - loan['total_paid'])
            str_remaining = self._clean_decimals(format_currency(resta_real))

            loan_name_raw = loan["name"]
            loan_name_display = (loan_name_raw[:17] + "...") if len(loan_name_raw) > 20 else loan_name_raw

            loans_ui.append(ft.Container(
                width=365, bgcolor=COLOR_BLANCO, padding=18, border_radius=16,
                border=ft.border.all(1, ft.Colors.with_opacity(0.06, COLOR_OCEANO)),
                shadow=ft.BoxShadow(spread_radius=0, blur_radius=12, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 6)),
                content=ft.Column([
                    ft.Row([
                        ft.Row([ft.Text(loan["icon"], size=22), ft.Text(loan_name_display, size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK, tooltip=loan_name_raw)], spacing=6),
                        ft.Row([btn_info, btn_editar, btn_eliminar], spacing=4)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    
                    ft.Text(f"{t('deudas_start_date', default='Inicio:')} {display_date} | {t('deudas_term', default='Plazo:')} {loan.get('term_months', 0)} {unit_text} | {t('deudas_interest', default='Int:')} {loan['interest_rate']}%", size=12, color=ft.Colors.GREY_600, weight=ft.FontWeight.W_500),
                    ft.Container(height=4),
                    ft.ProgressBar(value=progress, color=bar_color, bgcolor=ft.Colors.GREY_200, height=8),
                    ft.Container(height=4),
                    ft.Row([
                        ft.Text(f"{t('deudas_paid', default='Pagado:')} {str_paid}", size=13, color=ft.Colors.GREEN_600, weight=ft.FontWeight.BOLD),
                        ft.Text(f"{t('deudas_remaining', default='Resta:')} {str_remaining}", size=13, color=ft.Colors.RED_500, weight=ft.FontWeight.BOLD),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ], spacing=6)
            ))
            
        return ft.Row(controls=loans_ui, wrap=True, spacing=15)

    def _init_card_history_dialog(self):
        self.card_history_list_ui = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, height=450, width=420)
        self.card_history_dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA,
            title=ft.Text("", color=COLOR_OCEANO, weight=ft.FontWeight.BOLD),
            content=self.card_history_list_ui,
            actions=[
                ft.TextButton(t("settings_cancel", default="Cerrar"), on_click=lambda _: self._close_dialog(self.card_history_dialog))
            ]
        )
        self.page.overlay.append(self.card_history_dialog)

    def _toggle_history_sort(self, card):
        self.history_sort_desc = not self.history_sort_desc
        self._show_card_history_dialog(card)

    def _toggle_card_filter(self, filter_type, card):
        if filter_type == "expenses":
            self.card_filter_expenses = not self.card_filter_expenses
        elif filter_type == "incomes":
            self.card_filter_incomes = not self.card_filter_incomes
        self._show_card_history_dialog(card)

    def _show_card_history_dialog(self, card):
        """Renderiza el historial con los filtros unificados como iconos nativos de tendencia en la cabecera."""
        card_name_translated = t(str(card["name"]).lower().replace(" ", "_"), default=card["name"])
        cutoff_day = card.get("cutoff_day", 1)
        
        btn_gastos_icon = ft.Container(
            content=ft.Icon(ft.Icons.TRENDING_DOWN, color="white" if self.card_filter_expenses else "black", size=14),
            bgcolor=ft.Colors.RED_500 if self.card_filter_expenses else ft.Colors.GREY_300,
            padding=6, border_radius=6, ink=True,
            on_click=lambda _: self._toggle_card_filter("expenses", card),
            tooltip=t("deudas_filter_expenses", default="Gastos")
        )
        btn_ingresos_icon = ft.Container(
            content=ft.Icon(ft.Icons.SHOW_CHART, color="white" if self.card_filter_incomes else "black", size=14),
            bgcolor=ft.Colors.GREEN_600 if self.card_filter_incomes else ft.Colors.GREY_300,
            padding=6, border_radius=6, ink=True,
            on_click=lambda _: self._toggle_card_filter("incomes", card),
            tooltip=t("deudas_filter_incomes", default="Ingresos")
        )
        
        self.card_history_dialog.title = ft.Row([
            ft.Text(card_name_translated, color=COLOR_OCEANO, weight=ft.FontWeight.BOLD, size=16),
            ft.Row([
                btn_gastos_icon,
                btn_ingresos_icon,
                ft.IconButton(
                    icon=ft.Icons.SWAP_VERT,
                    icon_color=COLOR_OCEANO,
                    icon_size=20,
                    tooltip="Invertir orden cronológico",
                    on_click=lambda _: self._toggle_history_sort(card)
                )
            ], spacing=6)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, width=410)
        
        now = datetime.now()
        if now.month == 1:
            start_date = f"{now.year - 1}-12-01"
        else:
            start_date = f"{now.year}-{now.month - 1:02d}-01"
            
        if now.month == 12:
            end_date = f"{now.year + 1}-01-01"
        else:
            end_date = f"{now.year}-{now.month + 1:02d}-01"
        
        if now.day >= cutoff_day:
            current_cutoff_dt = datetime(now.year, now.month, cutoff_day)
        else:
            prev_month = now - relativedelta(months=1)
            current_cutoff_dt = datetime(prev_month.year, prev_month.month, cutoff_day)
        current_start_dt = current_cutoff_dt - relativedelta(months=1) + timedelta(days=1)

        transactions = get_card_transactions(card["id"], start_date, end_date)
        transactions.sort(key=lambda x: x.get("date", ""), reverse=self.history_sort_desc)
        
        self.card_history_list_ui.controls.clear()
        
        if not transactions:
            self.card_history_list_ui.controls.append(
                ft.Text(t("deudas_no_card_transactions", default="No hay movimientos registrados."), color=ft.Colors.GREY_600, italic=True, size=14)
            )
            self.card_history_dialog.open = True
            self.page.update()
            return

        grouped_data = {}
        for trans in transactions:
            try:
                tx_dt = datetime.strptime(trans.get('date', '')[:10], "%Y-%m-%d")
                tx_month_name = self._get_localized_month_name(tx_dt.month)
                group_key = f"{tx_month_name} {tx_dt.year}"
            except:
                group_key = "Otros Periodos"
                tx_dt = None
            
            if group_key not in grouped_data:
                grouped_data[group_key] = {"txs": []}
            grouped_data[group_key]["txs"].append(trans)

        for label, group in grouped_data.items():
            try:
                parts = label.split()
                g_month = 1
                for m_num, m_name in MONTH_NAMES_ES.items():
                    if m_name.lower() == parts[0].lower(): g_month = m_num; break
                for m_num, m_name in MONTH_NAMES_EN.items():
                    if m_name.lower() == parts[0].lower(): g_month = m_num; break
                g_year = int(parts[1])
                
                g_cutoff_dt = datetime(g_year, g_month, cutoff_day)
                g_start_dt = g_cutoff_dt - relativedelta(months=1) + timedelta(days=1)
                g_next_cutoff_dt = g_cutoff_dt + relativedelta(months=1)
                
                corte_expenses = 0.0
                corte_incomes = 0.0
                
                for t_idx in transactions:
                    try:
                        t_dt = datetime.strptime(t_idx["date"][:10], "%Y-%m-%d")
                        if g_start_dt <= t_dt <= g_cutoff_dt and t_idx.get("type", "expense") == "expense":
                            corte_expenses += t_idx["amount"]
                        if g_cutoff_dt < t_dt <= g_next_cutoff_dt and t_idx.get("type", "expense") != "expense":
                            corte_incomes += t_idx["amount"]
                    except: pass
                    
                restante_corte = max(0.0, corte_expenses - corte_incomes)
                str_restante = self._clean_decimals(format_currency(restante_corte))
                str_original_corte = self._clean_decimals(format_currency(corte_expenses))
                str_pagado_corte = self._clean_decimals(format_currency(corte_incomes))
            except:
                str_restante, str_original_corte, str_pagado_corte = "$0", "$0", "$0"

            items_column = ft.Column(spacing=8, visible=True)
            has_content = False
            
            for trans in group["txs"]:
                is_exp = trans.get("type", "expense") == "expense"
                if is_exp and not self.card_filter_expenses: continue
                if not is_exp and not self.card_filter_incomes: continue
                
                has_content = True
                is_in_active_cutoff_cycle = False
                try:
                    tx_dt = datetime.strptime(trans.get('date', '')[:10], "%Y-%m-%d")
                    if tx_dt and current_start_dt <= tx_dt <= current_cutoff_dt:
                        is_in_active_cutoff_cycle = True
                except: pass

                border_color = ft.Colors.RED_400 if (is_in_active_cutoff_cycle and is_exp) else ft.Colors.with_opacity(0.06, COLOR_CIAN)
                border_width = 1.8 if (is_in_active_cutoff_cycle and is_exp) else 1.0
                items_column.controls.append(self._build_transaction_card_custom(trans, border_color, border_width))

            if not has_content: continue

            def toggle_section(e, target_col=items_column):
                target_col.visible = not target_col.visible
                e.control.icon = ft.Icons.KEYBOARD_ARROW_DOWN if not target_col.visible else ft.Icons.KEYBOARD_ARROW_UP
                self.card_history_list_ui.update()

            arrow_btn = ft.IconButton(icon=ft.Icons.KEYBOARD_ARROW_UP, icon_size=20, icon_color=COLOR_OCEANO, on_click=toggle_section)

            formula_row = ft.Row([
                ft.Text(str_restante, size=12, color=ft.Colors.RED_400, weight=ft.FontWeight.BOLD),
                ft.Text("=", size=11, color=ft.Colors.GREY_400),
                ft.Text(str_original_corte, size=12, color=ft.Colors.GREY_600, weight=ft.FontWeight.W_500),
                ft.Text("-", size=11, color=ft.Colors.GREY_400),
                ft.Text(str_pagado_corte, size=12, color=ft.Colors.GREEN_600, weight=ft.FontWeight.BOLD)
            ], spacing=2)

            header_row = ft.Row([
                ft.Row([ft.Text(f"📅 {label}", size=13, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO), formula_row], spacing=8),
                arrow_btn
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

            self.card_history_list_ui.controls.append(
                ft.Container(content=ft.Column([header_row, items_column], spacing=5), padding=ft.padding.only(bottom=10))
            )

        self.card_history_dialog.open = True
        self.page.update()

    def _build_transaction_card_custom(self, trans, border_color, border_width):
        """Construye una celda de transacción para soportar identificadores de corte y abonos."""
        try:
            disp_date = datetime.strptime(trans.get('date', '')[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            disp_date = trans.get('date', '')
            
        desc = trans.get('description', '') or ""
        short_desc = (desc[:25] + '...') if len(desc) > 25 else desc
        
        is_expense = trans.get("type", "expense") == "expense"
        amount_color = ft.Colors.RED_500 if is_expense else ft.Colors.GREEN_500
        amount_prefix = "-" if is_expense else "+"
        clean_amount = self._clean_decimals(format_currency(trans.get('amount', 0.0)))
        
        if is_expense:
            category_name = trans.get('category_name', 'Otros')
            title_translated = t(str(category_name).lower().replace(" ", "_"), default=category_name)
            display_icon = trans.get('category_icon', '📦')
        else:
            if trans.get('source_name'):
                source_name = trans.get('source_name')
                title_translated = f"{t('deudas_pay_from', default='Pago desde')}: {t(str(source_name).lower().replace(' ', '_'), default=source_name)}"
                display_icon = trans.get('source_icon') or '💳'
            else:
                title_translated = trans.get('description') or t("deudas_lbl_pago", default="Pago Recibido")
                display_icon = '✨'  

        return ft.Container(
            bgcolor=COLOR_BLANCO, padding=12, border_radius=12,
            border=ft.border.all(border_width, border_color),
            content=ft.Row([
                ft.Row([
                    ft.Text(display_icon, size=22), 
                    ft.Column([
                        ft.Row([
                            ft.Text(title_translated, size=14, color=COLOR_OCEANO, weight=ft.FontWeight.BOLD),
                            ft.Container(
                                content=ft.Text(t("deudas_lbl_corte", default="Al Corte"), size=9, color="white", weight="bold"),
                                bgcolor=ft.Colors.RED_400, padding=ft.padding.symmetric(horizontal=5, vertical=1), border_radius=4
                            ) if (border_color == ft.Colors.RED_400 and is_expense) else ft.Container()
                        ], spacing=6),
                        ft.Text(short_desc, size=11, color=ft.Colors.GREY_600) if (short_desc and is_expense) else ft.Container()
                    ], spacing=1)
                ], spacing=10),
                ft.Column([
                    ft.Text(f"{amount_prefix}{clean_amount}", size=14, color=amount_color, weight=ft.FontWeight.BOLD),
                    ft.Text(disp_date, size=11, color=ft.Colors.GREY_500)
                ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        )

    def _init_loan_history_dialog(self):
        self.history_list_ui = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, height=350, width=420)
        self.loan_history_dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA,
            title=ft.Text("", color=COLOR_OCEANO, weight=ft.FontWeight.BOLD),
            content=self.history_list_ui,
            actions=[
                ft.TextButton(t("settings_cancel", default="Cerrar"), on_click=lambda _: self._close_dialog(self.loan_history_dialog))
            ]
        )
        self.page.overlay.append(self.loan_history_dialog)

    def _toggle_loan_sort(self, loan):
        self.loan_sort_desc = not self.loan_sort_desc
        self._show_loan_history_dialog(loan)

    def _show_loan_history_dialog(self, loan):
        """Agrupación colapsable idéntica para deudas con sumas acumuladas en verde positivo."""
        self.loan_history_dialog.title = ft.Row([
            ft.Text(f"{t('three_panel_history', default='Historial')}: {loan['name']}", color=COLOR_OCEANO, weight=ft.FontWeight.BOLD, size=15),
            ft.IconButton(
                icon=ft.Icons.SWAP_VERT,
                icon_color=COLOR_OCEANO,
                icon_size=20,
                tooltip="Invertir orden cronológico",
                on_click=lambda _: self._toggle_loan_sort(loan)
            )
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, width=400)
        
        payments = get_loan_payments(loan["id"])
        payments.sort(key=lambda x: x.get("date", ""), reverse=self.loan_sort_desc)
        self.history_list_ui.controls.clear()

        if not payments:
            self.history_list_ui.controls.append(
                ft.Text(t("deudas_no_loan_payments", default="No hay abonos registrados para esta deuda."), color=ft.Colors.GREY_600, italic=True, size=14)
            )
            self.loan_history_dialog.open = True
            self.page.update()
            return

        grouped_loans = {}
        for p in payments:
            try:
                p_dt = datetime.strptime(p['date'][:10], "%Y-%m-%d")
                month_name = self._get_localized_month_name(p_dt.month)
                group_key = f"{month_name} {p_dt.year}"
            except:
                group_key = "Otros Periodos"
            
            if group_key not in grouped_loans:
                grouped_loans[group_key] = {"items": [], "total_sum": 0.0}
            
            grid_loans = grouped_loans[group_key]
            grid_loans["items"].append(p)
            grid_loans["total_sum"] += p.get("amount", 0.0)

        for label, group in grouped_loans.items():
            str_suma_verde = self._clean_decimals(format_currency(group["total_sum"]))
            
            items_col = ft.Column(spacing=8, visible=True)
            for p in group["items"]:
                try:
                    disp_date = datetime.strptime(p['date'][:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                except ValueError:
                    disp_date = p['date']

                method_name_translated = t(str(p.get('method_name', 'Desconocido')).lower().replace(" ", "_"), default=p.get('method_name', 'Desconocido'))
                clean_amount = self._clean_decimals(format_currency(p['amount']))

                card = ft.Container(
                    bgcolor=COLOR_BLANCO, padding=12, border_radius=12,
                    border=ft.border.all(1, ft.Colors.with_opacity(0.06, COLOR_CIAN)),
                    content=ft.Row([
                        ft.Row([
                            ft.Text(p.get('method_icon', '💳'), size=22), 
                            ft.Text(method_name_translated, size=14, color=COLOR_OCEANO, weight=ft.FontWeight.BOLD)
                        ], spacing=10),
                        ft.Column([
                            ft.Text(f"+ {clean_amount}", size=14, color=ft.Colors.GREEN_500, weight=ft.FontWeight.BOLD),
                            ft.Text(disp_date, size=11, color=ft.Colors.GREY_500)
                        ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                )
                items_col.controls.append(card)

            def toggle_loan_section(e, target_col=items_col):
                target_col.visible = not target_col.visible
                e.control.icon = ft.Icons.KEYBOARD_ARROW_DOWN if not target_col.visible else ft.Icons.KEYBOARD_ARROW_UP
                self.history_list_ui.update()

            arrow_btn = ft.IconButton(
                icon=ft.Icons.KEYBOARD_ARROW_DOWN if not items_col.visible else ft.Icons.KEYBOARD_ARROW_UP,
                icon_size=20,
                icon_color=COLOR_OCEANO,
                on_click=toggle_loan_section
            )

            header_row = ft.Row([
                ft.Row([
                    ft.Text(f"📅 {label}", size=14, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
                    ft.Text(f" ({str_suma_verde})", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_600)
                ], spacing=4),
                arrow_btn
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

            self.history_list_ui.controls.append(
                ft.Container(
                    content=ft.Column([header_row, items_col], spacing=5),
                    padding=ft.padding.only(bottom=10)
                )
            )

        self.loan_history_dialog.open = True
        self.page.update()

    def _on_loan_date_change(self, e):
        """Manejador síncrono para el evento de selección del DatePicker con formateo seguro a DD/MM/AAAA."""
        if e.control.value:
            val = e.control.value
            # Si Flet devuelve un objeto datetime formal
            if hasattr(val, "strftime"):
                self.loan_date.value = val.strftime("%d/%m/%Y")
            else:
                # Si devuelve una cadena, limpiamos remanentes de horas o formatos ISO
                val_str = str(val).split("T")[0].split(" ")[0].strip()
                parsed = False
                
                # Intentar parsear los formatos de cadena más comunes para reordenarlos
                for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
                    try:
                        date_obj = datetime.strptime(val_str, fmt)
                        self.loan_date.value = date_obj.strftime("%d/%m/%Y")
                        parsed = True
                        break
                    except ValueError:
                        continue
                
                # Si no coincide con ninguno, preserva la cadena limpia original
                if not parsed:
                    self.loan_date.value = val_str
                    
            self.page.update()

    def _init_loan_dialog(self):
        decimal_filter = ft.InputFilter(allow=True, regex_string=r"^[0-9]*(?:\.[0-9]*)?$")
        int_filter = ft.InputFilter(allow=True, regex_string=r"^[0-9]*$")
        date_filter = ft.InputFilter(allow=True, regex_string=r"^[0-9]/]*$")

        # Inicialización del selector de fecha dinámico nativo
        self.loan_date_picker = ft.DatePicker(
            on_change=self._on_loan_date_change,
            first_date=datetime(2020, 1, 1),
            last_date=datetime(2035, 12, 31)
        )
        self.page.overlay.append(self.loan_date_picker)

        self.loan_name = ft.TextField(label=t("deudas_loan_name", default="Nombre del Préstamo (Ej. Auto)"), max_length=30, color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=350)
        self.loan_amount = ft.TextField(label=t("deudas_loan_amount", default="Monto Total Original"), keyboard_type=ft.KeyboardType.NUMBER, input_filter=decimal_filter, max_length=25, prefix=ft.Text("$"), color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=350)
        self.loan_interest = ft.TextField(label=t("deudas_loan_interest", default="Tasa de Interés (%)"), keyboard_type=ft.KeyboardType.NUMBER, value="0", input_filter=decimal_filter, max_length=5, color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=350)
        
        self.loan_term_num = ft.TextField(label=t("deudas_loan_term", default="Plazo"), value="12", keyboard_type=ft.KeyboardType.NUMBER, input_filter=int_filter, color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=170)
        self.loan_term_unit = ft.Dropdown(
            label=t("deudas_loan_unit", default="Unidad"),
            options=[
                ft.dropdown.Option(key="Semanas", text=t("deudas_weeks", default="Semanas")), 
                ft.dropdown.Option(key="Meses", text=t("deudas_months", default="Meses")), 
                ft.dropdown.Option(key="Años", text=t("deudas_years", default="Años"))
            ],
            value="Meses", color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=170
        )
        
        def open_picker_compat(_):
            self.loan_date_picker.open = True
            self.page.update()
        
        self.loan_date = ft.TextField(label=t("deudas_loan_start_date", default="Fecha de Inicio (DD/MM/AAAA)"), input_filter=date_filter, max_length=10, color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=290)
        self.loan_date_btn = ft.IconButton(icon=ft.Icons.CALENDAR_MONTH, icon_color=COLOR_OCEANO, on_click=open_picker_compat)

        self.loan_dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA,
            title=ft.Text(t("deudas_register_loan", default="Registrar Préstamo"), color=COLOR_OCEANO, weight=ft.FontWeight.BOLD),
            content=ft.Column([
                self.loan_name, 
                self.loan_amount, 
                ft.Row([self.loan_term_num, self.loan_term_unit], spacing=10),
                ft.Row([self.loan_date, self.loan_date_btn], spacing=10, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self.loan_interest
            ], tight=True),
            actions=[
                ft.TextButton(t("settings_cancel", default="Cancelar"), on_click=lambda _: self._close_dialog(self.loan_dialog)),
                ft.FilledButton(t("three_panel_save", default="Guardar"), bgcolor=COLOR_OCEANO, color=COLOR_BLANCO, on_click=self._save_loan)
            ]
        )
        self.page.overlay.append(self.loan_dialog)
        self.editing_loan_id = None

    def _show_add_loan_dialog(self):
        self.editing_loan_id = None
        self.loan_dialog.title.value = t("deudas_register_loan", default="Registrar Nuevo Préstamo")
        self.loan_name.value = ""
        self.loan_amount.value = ""
        self.loan_term_num.value = "12"
        self.loan_term_unit.value = "Meses"
        self.loan_interest.value = "0"
        self.loan_date.value = datetime.now().strftime("%d/%m/%Y") 
        self.loan_date.disabled = False
        self.loan_date_btn.disabled = False
        
        self.loan_dialog.open = True
        self.page.update()

    def _show_edit_loan_dialog(self, loan):
        self.editing_loan_id = loan["id"]
        self.loan_dialog.title.value = t("three_panel_edit_card", default="Editar Préstamo")
        self.loan_name.value = loan["name"]
        self.loan_amount.value = str(loan["total_amount"])
        self.loan_term_num.value = str(loan.get("term_months", 12))
        self.loan_term_unit.value = loan.get("term_unit", "Meses")
        self.loan_interest.value = str(loan["interest_rate"])
        
        self.loan_date.disabled = True
        self.loan_date_btn.disabled = True
        
        db_date = loan.get("start_date", "")
        try:
            self.loan_date.value = datetime.strptime(db_date, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            self.loan_date.value = db_date
            
        self.loan_dialog.open = True
        self.page.update()

    def _save_loan(self, e):
        if not self.loan_name.value or not self.loan_amount.value:
            return
            
        try:
            db_date = datetime.strptime(self.loan_date.value, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("transaction_form_invalid_date", default="Formato de fecha inválido. Usa DD/MM/AAAA")), bgcolor=ft.Colors.RED_700)
            self.page.snack_bar.open = True
            self.page.update()
            return

        try:
            if self.editing_loan_id:
                update_loan(
                    loan_id=self.editing_loan_id,
                    name=self.loan_name.value,
                    total_amount=float(self.loan_amount.value),
                    interest_rate=float(self.loan_interest.value),
                    term_months=int(self.loan_term_num.value),
                    term_unit=self.loan_term_unit.value,
                    start_date=db_date
                )
                mensaje = t("deudas_loan_updated", default="Préstamo actualizado exitosamente")
            else:
                add_loan(
                    name=self.loan_name.value,
                    total_amount=float(self.loan_amount.value),
                    interest_rate=float(self.loan_interest.value),
                    term_months=int(self.loan_term_num.value),
                    term_unit=self.loan_term_unit.value,
                    start_date=db_date,
                    icon="🏦",
                    color=COLOR_ATARDECER
                )
                mensaje = t("deudas_loan_registered", default="Préstamo registrado exitosamente")
                
            self.loan_dialog.open = False
            self.page.snack_bar = ft.SnackBar(content=ft.Text(mensaje), bgcolor=ft.Colors.GREEN_700)
            self.page.snack_bar.open = True
            self.page.update()
            self._refresh_view()
        except ValueError:
            pass 

    def _init_delete_loan_dialog(self):
        self.delete_loan_dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA,
            title=ft.Text(t("deudas_delete_loan", default="Eliminar Préstamo"), color=COLOR_OCEANO, weight=ft.FontWeight.BOLD),
            content=ft.Text(t("deudas_confirm_delete_loan", default="¿Estás seguro de borrar este préstamo?")),
            actions=[
                ft.TextButton(t("settings_cancel", default="Cancelar"), on_click=lambda _: self._close_dialog(self.delete_loan_dialog)),
                ft.FilledButton(t("deudas_delete", default="Eliminar"), bgcolor=ft.Colors.RED, color=COLOR_BLANCO, on_click=self._execute_delete_loan)
            ]
        )
        self.page.overlay.append(self.delete_loan_dialog)
        self.loan_to_delete = None

    def _confirm_delete_loan(self, loan):
        self.loan_to_delete = loan["id"]
        self.delete_loan_dialog.open = True
        self.page.update()

    def _execute_delete_loan(self, e):
        if self.loan_to_delete:
            delete_loan(self.loan_to_delete)
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("deudas_loan_deleted", default="Préstamo eliminado")), bgcolor=ft.Colors.RED_700)
            self.page.snack_bar.open = True
            
        self.delete_loan_dialog.open = False
        self._refresh_view()

    def _close_dialog(self, dialog):
        dialog.open = False
        self.page.update()

    def _show_frozen_error_modal(self, account_name):
        """Despliega un cuadro de advertencia bloqueando transacciones sobre métodos congelados."""
        title = t("deudas_frozen_error_title", default="Operación Bloqueada ❄️")
        msg = t("deudas_frozen_error_body", default="Esta cuenta o tarjeta se encuentra congelada. No es posible realizar transferencias, abonos ni movimientos con ella hasta que sea descongelada desde el panel de Configuración.")
        lbl_ok = "Entendido"

        error_dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA,
            shape=ft.RoundedRectangleBorder(radius=20),
            title=ft.Text(title, weight=ft.FontWeight.BOLD, color=COLOR_ATARDECER, size=18),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(account_name, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK87),
                    ft.Text(msg, color=ft.Colors.BLACK54, size=14)
                ], tight=True, spacing=5),
                width=420,
                padding=5
            ),
            actions=[
                ft.FilledButton(lbl_ok, bgcolor=COLOR_OCEANO, color=COLOR_BLANCO, on_click=lambda _: setattr(error_dialog, "open", False) or self.page.update())
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        self.page.overlay.append(error_dialog)
        error_dialog.open = True
        self.page.update()

    def _show_loan_payment_dialog(self):
        methods = get_payment_methods()
        loans = get_all_loans_with_progress()
        active_loans = [l for l in loans if l["remaining"] > 0]
        
        if not active_loans:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("deudas_no_active_loans_to_pay", default="No tienes préstamos activos para abonar.")), bgcolor=ft.Colors.ORANGE_700)
            self.page.snack_bar.open = True
            self.page.update()
            return
            
        source_dropdown = ft.Dropdown(
            label=t("deudas_loan_payment_source", default="¿De dónde sale el dinero?"), 
            options=[ft.dropdown.Option(key=str(m["id"]), text=f"{m['icon']} {t(str(m['name']).lower().replace(' ', '_'), default=m['name'])}{' ❄️' if m.get('status') == 'frozen' else ''}") for m in methods if m["type"] != "card"],
            color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=350
        )
        
        dest_dropdown = ft.Dropdown(
            label=t("deudas_loan_payment_destination", default="¿A qué préstamo abonas?"), 
            options=[ft.dropdown.Option(key=str(l['id']), text=f"{l['icon']} {l['name']}") for l in active_loans],
            color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=350
        )
        
        amount_input = ft.TextField(
            label=t("deudas_loan_payment_amount", default="Monto a Abonar"), 
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(allow=True, regex_string=r"^[0-9]*(?:\.[0-9]*)?$"),
            max_length=25,
            prefix=ft.Text("$"), color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=350
        )

        dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA,
            title=ft.Text(t("deudas_loan_payment_title", default="Abonar a Préstamo"), color=COLOR_OCEANO, weight=ft.FontWeight.BOLD),
            content=ft.Column([source_dropdown, dest_dropdown, amount_input], tight=True),
        )

        def close_payment(e=None):
            dialog.open = False
            self.page.update()

        def save_payment(e):
            if not source_dropdown.value or not dest_dropdown.value or not amount_input.value:
                return
            try:
                source_id = int(source_dropdown.value)
                source_method = next((m for m in methods if m["id"] == source_id), None)
                
                # Control de integridad contra cuentas congeladas
                if source_method and source_method.get("status") == "frozen":
                    self._show_frozen_error_modal(source_method["name"])
                    return

                amount = float(amount_input.value)
                dest_loan_id = int(dest_dropdown.value)
                
                permitir_sobregiro = get_setting("allow_overdraft", "0") == "1"
                balances_actualizados = get_balance_by_payment_method()
                source_balance = next((b["balance"] for b in balances_actualizados if b["id"] == source_id), 0)
                
                if not permitir_sobregiro and amount > source_balance:
                    err_txt = t("deudas_insufficient_funds", default="Fondos insuficientes.").replace("{available}", format_currency(source_balance))
                    self.page.snack_bar = ft.SnackBar(content=ft.Text(err_txt), bgcolor=ft.Colors.RED_700)
                    self.page.snack_bar.open = True
                    self.page.update()
                    return

                selected_loan = next((l for l in active_loans if l["id"] == dest_loan_id), None)
                if selected_loan and amount > selected_loan["remaining"]:
                    err_txt = t("deudas_insufficient_loan_funds", default="El abono supera la deuda restante.").replace("{remaining}", format_currency(selected_loan['remaining']))
                    self.page.snack_bar = ft.SnackBar(content=ft.Text(err_txt), bgcolor=ft.Colors.RED_700)
                    self.page.snack_bar.open = True
                    self.page.update()
                    return

                current_date = datetime.now().strftime("%Y-%m-%d")
                add_transfer(source_id, amount, current_date, "Abono a préstamo", dest_loan_id=dest_loan_id)
                    
                dialog.open = False
                self.page.snack_bar = ft.SnackBar(content=ft.Text(t("deudas_loan_payment_success", default="Abono registrado con éxito")), bgcolor=ft.Colors.GREEN_700)
                self.page.snack_bar.open = True
                self._refresh_view()
            except ValueError:
                pass

        dialog.actions = [
            ft.TextButton(t("deudas_loan_payment_cancel", default="Cancelar"), on_click=close_payment),
            ft.FilledButton(t("deudas_loan_payment_save", default="Registrar Abono"), on_click=save_payment, bgcolor=COLOR_OCEANO, color=COLOR_BLANCO)
        ]
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def _show_card_payment_dialog(self):
        """Muestra el diálogo de amortización con RadioButtons fijos y comportamiento dinámico."""
        balances = get_balance_by_payment_method()
        cards = [b for b in balances if b["type"] == "card"]
        
        if not cards:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("deudas_no_cards_to_pay", default="No tienes tarjetas de crédito registradas.")), bgcolor=ft.Colors.ORANGE_700)
            self.page.snack_bar.open = True
            self.page.update()
            return
            
        source_dropdown = ft.Dropdown(
            label=t("deudas_card_payment_source", default="¿De dónde sale el dinero?"), 
            options=[ft.dropdown.Option(key=str(b["id"]), text=f"{b['icon']} {t(str(b['name']).lower().replace(' ', '_'), default=b['name'])}{' ❄️' if b.get('status') == 'frozen' else ''}") for b in balances if b["type"] != "card"],
            color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=350
        )
        
        dest_dropdown = ft.Dropdown(
            label=t("deudas_card_payment_destination", default="¿Qué tarjeta estás pagando?"), 
            options=[ft.dropdown.Option(key=str(c['id']), text=f"{c['icon']} {t(str(c['name']).lower().replace(' ', '_'), default=c['name'])}{' ❄️' if c.get('status') == 'frozen' else ''}") for c in cards],
            color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=350
        )
        
        amount_input = ft.TextField(
            label=t("deudas_card_payment_amount", default="Monto Pagado"), 
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(allow=True, regex_string=r"^[0-9]*(?:\.[0-9]*)?$"),
            max_length=25,
            prefix=ft.Text("$"), color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=350
        )

        radio_group = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="manual", label=t("deudas_radio_manual", default="Monto personalizado")),
                ft.Radio(value="no_interest", label=f"{t('deudas_radio_no_interest', default='Pago para no generar intereses 🛡️')} ($0.00)")
            ], spacing=8),
            value="manual"
        )

        dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA,
            title=ft.Text(t("deudas_card_payment_title", default="Pagar Tarjeta"), color=COLOR_OCEANO, weight=ft.FontWeight.BOLD),
            content=ft.Column([source_dropdown, dest_dropdown, amount_input, radio_group], tight=True, spacing=15),
        )

        def sync_calculated_debt():
            """Calcula la deuda al corte de la tarjeta activa y actualiza la UI correspondientemente."""
            corte_calculated = 0.0
            if dest_dropdown.value:
                selected_card_id = int(dest_dropdown.value)
                card_item = next((c for c in cards if c["id"] == selected_card_id), None)
                if card_item:
                    card_item_full = next((b for b in get_balance_by_payment_method() if b["id"] == selected_card_id), card_item)
                    corte_calculated = self._calculate_corte_debt(card_item_full)
            
            radio_group.content.controls[1].label = f"{t('deudas_radio_no_interest', default='Pago para no generar intereses 🛡️')} (${corte_calculated:.2f})"
            
            amount_input.disabled = False
            if radio_group.value == "no_interest":
                amount_input.value = f"{corte_calculated:.2f}"
                amount_input.disabled = True
            
            radio_group.update()
            amount_input.update()

        def on_card_selected(e):
            radio_group.value = "manual"
            amount_input.value = ""
            amount_input.disabled = False
            sync_calculated_debt()
            self.page.update()

        def on_radio_changed(e):
            if radio_group.value == "manual":
                amount_input.value = ""
            sync_calculated_debt()
            self.page.update()

        dest_dropdown.on_change = on_card_selected
        radio_group.on_change = on_radio_changed

        def close_payment(e=None):
            dialog.open = False
            self.page.update()

        def save_payment(e):
            if not source_dropdown.value or not dest_dropdown.value or not amount_input.value:
                return
            try:
                val_str = amount_input.value.strip() if amount_input.value else ""
                if not val_str or val_str == ".":
                    return
                
                source_id = int(source_dropdown.value)
                dest_method_id = int(dest_dropdown.value)
                source_method = next((b for b in balances if b["id"] == source_id), None)
                dest_method = next((c for c in cards if c["id"] == dest_method_id), None)

                # Control de integridad: Bloqueo absoluto si el origen o el destino están congelados
                if source_method and source_method.get("status") == "frozen":
                    self._show_frozen_error_modal(source_method["name"])
                    return
                if dest_method and dest_method.get("status") == "frozen":
                    self._show_frozen_error_modal(dest_method["name"])
                    return

                amount = float(val_str)
                if amount <= 0:
                    def close_zero_warning(_):
                        zero_warning_dialog.open = False
                        self.page.update()

                    zero_warning_dialog = ft.AlertDialog(
                        bgcolor=COLOR_CREMA,
                        title=ft.Text(t("deudas_error_zero_title", default="⚠️ Monto Inválido"), color=ft.Colors.RED_700, weight=ft.FontWeight.BOLD),
                        content=ft.Column([
                            ft.Text(t("deudas_error_zero_body_1", default="El monto a amortizar no puede ser $0.00.")),
                            ft.Text(t("deudas_error_zero_body_2", default="Por favor, ingresa una cantidad válida o selecciona otra tarjeta que presente saldo pendiente."))
                        ], tight=True, spacing=5),
                        actions=[
                            ft.TextButton(t("settings_ok", default="Entendido"), on_click=close_zero_warning)
                        ]
                    )
                    self.page.overlay.append(zero_warning_dialog)
                    zero_warning_dialog.open = True
                    self.page.update()
                    return
                
                if dest_method and radio_group.value == "no_interest":
                    real_corte = self._calculate_corte_debt(dest_method)
                    if abs(amount - real_corte) > 0.01:
                        def close_warning(_):
                            warning_dialog.open = False
                            amount_input.disabled = False
                            amount_input.value = f"{real_corte:.2f}"
                            amount_input.disabled = True
                            if real_corte <= 0:
                                radio_group.value = "manual"
                                amount_input.value = ""
                                amount_input.disabled = False
                            sync_calculated_debt()
                            self.page.update()

                        warning_dialog = ft.AlertDialog(
                            bgcolor=COLOR_CREMA,
                            title=ft.Text(t("deudas_warning_title", default="⚠️ Ajuste por Desfase"), color=ft.Colors.ORANGE_700, weight=ft.FontWeight.BOLD),
                            content=ft.Column([
                                ft.Text(t("deudas_warning_b1", default="El monto detectado no coincidía con la tarjeta activa debido a un cambio rápido.")),
                                ft.Text(t("deudas_warning_b2", default="El sistema actualizará el campo automáticamente al valor correcto de esta tarjeta:")),
                                ft.Text(f"${real_corte:.2f}", size=16, weight="bold", color=COLOR_OCEANO),
                                ft.Text(t("deudas_warning_b3", default="Por favor revisa el monto antes de confirmar."))
                            ], tight=True, spacing=8),
                            actions=[
                                ft.TextButton(t("settings_ok", default="Entendido"), on_click=close_warning)
                            ]
                        )
                        self.page.overlay.append(warning_dialog)
                        warning_dialog.open = True
                        self.page.update()
                        return
                
                permitir_sobregiro = get_setting("allow_overdraft", "0") == "1"
                balances_actualizados = get_balance_by_payment_method()
                source_balance = next((b["balance"] for b in balances_actualizados if b["id"] == source_id), 0)
                
                if not permitir_sobregiro and amount > source_balance:
                    err_txt = t("deudas_insufficient_funds", default="Fondos insuficientes.").replace("{available}", format_currency(source_balance))
                    self.page.snack_bar = ft.SnackBar(content=ft.Text(err_txt), bgcolor=ft.Colors.RED_700)
                    self.page.snack_bar.open = True
                    self.page.update()
                    return

                current_date = datetime.now().strftime("%Y-%m-%d")
                add_transfer(source_id, amount, current_date, "Pago a tarjeta", dest_method_id=dest_method_id)
                    
                dialog.open = False
                self.page.snack_bar = ft.SnackBar(content=ft.Text(t("deudas_card_payment_success", default="Pago de tarjeta registrado con éxito")), bgcolor=ft.Colors.GREEN_700)
                self.page.snack_bar.open = True
                self._refresh_view()
            except ValueError:
                pass

        dialog.actions = [
            ft.TextButton(t("deudas_card_payment_cancel", default="Cancelar"), on_click=close_payment),
            ft.FilledButton(t("deudas_card_payment_save", default="Pagar Tarjeta"), on_click=save_payment, bgcolor=COLOR_OCEANO, color=COLOR_BLANCO)
        ]
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def _show_own_transfer_dialog(self):
        """Abre un modal para transferir fondos propios entre Efectivo y Débito sin alterar balances macros."""
        methods = get_balance_by_payment_method()
        allowed_methods = [m for m in methods if m["type"] != "card"]
        
        if len(allowed_methods) < 2:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("deudas_min_accounts_error", default="Necesitas al menos dos cuentas para realizar una transferencia.")), bgcolor=ft.Colors.ORANGE_700)
            self.page.snack_bar.open = True
            self.page.update()
            return
            
        source_dropdown = ft.Dropdown(
            label=t("deudas_transfer_source", default="¿De dónde sale el dinero?"), 
            options=[ft.dropdown.Option(key=str(m["id"]), text=f"{m['icon']} {t(str(m['name']).lower().replace(' ', '_'), default=m['name'])}{' ❄️' if m.get('status') == 'frozen' else ''}") for m in allowed_methods],
            color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=350
        )
        
        dest_dropdown = ft.Dropdown(
            label=t("deudas_transfer_destination", default="¿A dónde se envía el dinero?"), 
            options=[ft.dropdown.Option(key=str(m["id"]), text=f"{m['icon']} {t(str(m['name']).lower().replace(' ', '_'), default=m['name'])}{' ❄️' if m.get('status') == 'frozen' else ''}") for m in allowed_methods],
            color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=350
        )
        
        amount_input = ft.TextField(
            label=t("deudas_transfer_amount", default="Monto a Transferir"), 
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(allow=True, regex_string=r"^[0-9]*(?:\.[0-9]*)?$"),
            max_length=25,
            prefix=ft.Text("$"), color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=350
        )

        dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA,
            title=ft.Text(t("deudas_own_transfer_title", default="Transferencia Propia"), color=COLOR_OCEANO, weight=ft.FontWeight.BOLD),
            content=ft.Column([source_dropdown, dest_dropdown, amount_input], tight=True, spacing=15),
        )

        def close_dialog(e=None):
            dialog.open = False
            self.page.update()

        def save_transfer(e):
            if not source_dropdown.value or not dest_dropdown.value or not amount_input.value:
                return
            if source_dropdown.value == dest_dropdown.value:
                self.page.snack_bar = ft.SnackBar(content=ft.Text(t("deudas_transfer_same_account", default="La cuenta de origen y destino no pueden ser la misma.")), bgcolor=ft.Colors.RED_700)
                self.page.snack_bar.open = True
                self.page.update()
                return
            try:
                source_id = int(source_dropdown.value)
                dest_id = int(dest_dropdown.value)
                source_method = next((m for m in allowed_methods if m["id"] == source_id), None)
                dest_method = next((m for m in allowed_methods if m["id"] == dest_id), None)

                # Control de integridad: Validación asimétrica si el origen o el destino están congelados
                if source_method and source_method.get("status") == "frozen":
                    self._show_frozen_error_modal(source_method["name"])
                    return
                if dest_method and dest_method.get("status") == "frozen":
                    self._show_frozen_error_modal(dest_method["name"])
                    return

                amount = float(amount_input.value)
                if amount <= 0:
                    return
                    
                permitir_sobregiro = get_setting("allow_overdraft", "0") == "1"
                balances_actualizados = get_balance_by_payment_method()
                source_balance = next((b["balance"] for b in balances_actualizados if b["id"] == source_id), 0)
                
                if not permitir_sobregiro and amount > source_balance:
                    err_txt = t("deudas_insufficient_funds", default="Fondos insuficientes.").replace("{available}", format_currency(source_balance))
                    self.page.snack_bar = ft.SnackBar(content=ft.Text(err_txt), bgcolor=ft.Colors.RED_700)
                    self.page.snack_bar.open = True
                    self.page.update()
                    return

                current_date = datetime.now().strftime("%Y-%m-%d")
                add_transfer(source_id, amount, current_date, "Transferencia", dest_method_id=dest_id)
                
                dialog.open = False
                self.page.snack_bar = ft.SnackBar(content=ft.Text(t("deudas_transfer_success", default="Transferencia realizada con éxito")), bgcolor=ft.Colors.GREEN_700)
                self.page.snack_bar.open = True
                self._refresh_view()
            except ValueError:
                pass

        dialog.actions = [
            ft.TextButton(t("deudas_loan_payment_cancel", default="Cancelar"), on_click=close_dialog),
            ft.FilledButton(t("three_panel_save", default="Guardar"), on_click=save_transfer, bgcolor=COLOR_OCEANO, color=COLOR_BLANCO)
        ]
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def _refresh_view(self):
        self.center_wrapper.content = self.build_content()
        self.page.update()

    def get_view(self):
        return self.main_container

def create_deudas_view(page: ft.Page) -> ft.Container:
    view = DeudasView(page)
    return view.get_view()