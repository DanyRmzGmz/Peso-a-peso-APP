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
        
        self.history_sort_desc = True
        self.loan_sort_desc = True
        self.card_filter_expenses = True
        self.card_filter_incomes = True
        
        self._init_loan_dialog()
        self._init_credit_purchase_dialog()
        self._init_late_fee_dialog()
        self._init_delete_loan_dialog()
        self._init_loan_history_dialog() 
        self._init_card_history_dialog()

        self.center_wrapper = ft.Container(
            content=self.build_content(),
            width=1300,
            alignment=ft.Alignment(0, -1)
        )

        self.main_container = ft.Container(
            gradient=GRADIENTE_FONDO_SUAVE,
            expand=True,
            padding=20,
            alignment=ft.Alignment(0, -1),
            content=self.center_wrapper
        )

    def _init_credit_purchase_dialog(self):
        """Inicializa los campos de captura e inyecta el modal de compras a crédito con selectores de modo y formato de fecha adaptado."""
        decimal_filter = ft.InputFilter(allow=True, regex_string=r"^[0-9]*(?:\.[0-9]*)?$")
        int_filter = ft.InputFilter(allow=True, regex_string=r"^[0-9]*$")
        date_filter = ft.InputFilter(allow=True, regex_string=r"^[0-9]/]*$")

        self.purchase_date_picker = ft.DatePicker(
            on_change=self._on_purchase_date_change,
            first_date=datetime(2020, 1, 1),
            last_date=datetime(2035, 12, 31),
            keyboard_type=ft.KeyboardType.DATETIME
        )
        self.page.overlay.append(self.purchase_date_picker)

        self.purchase_name = ft.TextField(label=t("deudas_purchase_name", default="Concepto de la Compra (Ej. Computadora)"), max_length=30, color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=350)
        self.purchase_card = ft.Dropdown(label=t("deudas_purchase_card_select", default="Selecciona la Tarjeta de Crédito"), color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=350)
        
        self.purchase_months = ft.TextField(label=t("deudas_purchase_months", default="Mensualidades (Plazo)"), value="12", keyboard_type=ft.KeyboardType.NUMBER, input_filter=int_filter, max_length=5, color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=350, on_change=self._sync_from_total)
        self.purchase_interest = ft.TextField(label=t("deudas_purchase_interest", default="Tasa de Interés Total (%)"), keyboard_type=ft.KeyboardType.NUMBER, value="0", input_filter=decimal_filter, max_length=5, color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=350, on_change=self._sync_from_total)
        
        self.purchase_amount = ft.TextField(label=t("deudas_purchase_amount", default="Monto Total Original"), keyboard_type=ft.KeyboardType.NUMBER, input_filter=decimal_filter, max_length=25, prefix=ft.Text("$"), color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=300, on_change=self._sync_from_total)
        self.purchase_monthly_amount = ft.TextField(label=t("deudas_purchase_monthly_amount", default="Monto de la Mensualidad"), keyboard_type=ft.KeyboardType.NUMBER, input_filter=decimal_filter, max_length=25, prefix=ft.Text("$"), color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=300, on_change=self._sync_from_monthly, disabled=True)
        
        def open_purchase_picker(_):
            self.purchase_date_picker.open = True
            self.page.update()

        self.purchase_date = ft.TextField(label=t("deudas_loan_start_date", default="Fecha de Inicio (DD/MM/AAAA)"), input_filter=date_filter, max_length=10, color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=290)
        self.purchase_date_btn = ft.IconButton(icon=ft.Icons.CALENDAR_MONTH, icon_color=COLOR_OCEANO, on_click=open_purchase_picker)

        self.purchase_mode_radio = ft.RadioGroup(
            content=ft.Column([
                ft.Row([ft.Radio(value="total", label=""), self.purchase_amount], spacing=5, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([ft.Radio(value="monthly", label=""), self.purchase_monthly_amount], spacing=5, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            ], spacing=10),
            value="total",
            on_change=self._on_purchase_mode_change
        )

        self.credit_purchase_dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA,
            title=ft.Text(t("deudas_register_credit_purchase", default="Registrar Compra a Crédito"), color=COLOR_OCEANO, weight=ft.FontWeight.BOLD),
            content=ft.Column([
                self.purchase_name,
                self.purchase_card,
                self.purchase_months,
                self.purchase_interest,
                self.purchase_mode_radio,
                ft.Row([self.purchase_date, self.purchase_date_btn], spacing=10, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            ], tight=True, spacing=15),
            actions=[
                ft.TextButton(t("settings_cancel", default="Cancelar"), on_click=lambda _: self._close_dialog(self.credit_purchase_dialog)),
                ft.FilledButton(t("three_panel_save", default="Guardar"), bgcolor=COLOR_OCEANO, color=COLOR_BLANCO, on_click=self._save_credit_purchase)
            ]
        )
        self.page.overlay.append(self.credit_purchase_dialog)
        self._is_syncing = False
        self._is_saving = False

    def _on_purchase_mode_change(self, e):
        """Gestiona la conmutación de deshabilitado en caliente basándose en la selección del Radio Button."""
        self._is_syncing = True
        if self.purchase_mode_radio.value == "total":
            self.purchase_amount.disabled = False
            self.purchase_monthly_amount.disabled = True
            self.purchase_monthly_amount.value = ""
        else:
            self.purchase_amount.disabled = True
            self.purchase_monthly_amount.disabled = False
            self.purchase_amount.value = ""
        self._is_syncing = False
        self.page.update()

    def _on_purchase_date_change(self, e):
        """Manejador síncrono para el formateo e interceptación limpia de la fecha de la compra a crédito."""
        if e.control.value:
            val = e.control.value
            if hasattr(val, "strftime"):
                self.purchase_date.value = val.strftime("%d/%m/%Y")
            else:
                val_str = str(val).split("T")[0].split(" ")[0].strip()
                parsed = False
                for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"]:
                    try:
                        date_obj = datetime.strptime(val_str, fmt)
                        self.purchase_date.value = date_obj.strftime("%d/%m/%Y")
                        parsed = True
                        break
                    except ValueError:
                        continue
                if not parsed:
                    self.purchase_date.value = val_str
            self.page.update()

    def _sync_from_total(self, e):
        """Calcula el pago mensual basándose en el monto total ingresado por el usuario."""
        if self._is_syncing or self.purchase_mode_radio.value != "total":
            return
        self._is_syncing = True
        try:
            val_total = self.purchase_amount.value.strip() if self.purchase_amount.value else ""
            if val_total:
                total = float(val_total)
                months = int(self.purchase_months.value) if self.purchase_months.value else 1
                interest = float(self.purchase_interest.value) if self.purchase_interest.value else 0.0
                if months < 1: 
                    months = 1
                
                total_with_interest = total + (total * (interest / 100))
                monthly = total_with_interest / months
                self.purchase_monthly_amount.value = f"{monthly:.2f}"
            else:
                self.purchase_monthly_amount.value = ""
            self.purchase_monthly_amount.update()
        except ValueError:
            pass
        finally:
            self._is_syncing = False

    def _sync_from_monthly(self, e):
        """Calcula el monto original exacto en base a la cuota mensual digitada por el usuario."""
        if self._is_syncing or self.purchase_mode_radio.value != "monthly":
            return
        self._is_syncing = True
        try:
            val_monthly = self.purchase_monthly_amount.value.strip() if self.purchase_monthly_amount.value else ""
            if val_monthly:
                monthly = float(val_monthly)
                months = int(self.purchase_months.value) if self.purchase_months.value else 1
                interest = float(self.purchase_interest.value) if self.purchase_interest.value else 0.0
                if months < 1: 
                    months = 1
                
                total_pagar = monthly * months
                total_original = total_pagar / (1 + (interest / 100))
                self.purchase_amount.value = f"{total_original:.2f}"
            else:
                self.purchase_amount.value = ""
            self.purchase_amount.update()
        except ValueError:
            pass
        finally:
            self._is_syncing = False
    
    def _show_add_credit_purchase_dialog(self):
        """Popula las opciones de tarjetas de crédito y limpia de forma segura el estado de inicialización del modal."""
        balances = get_balance_by_payment_method()
        cards = [b for b in balances if b["type"] == "card" and b.get("status") != "frozen"]
        
        self.purchase_card.options = [
            ft.dropdown.Option(key=str(c["id"]), text=f"{c['icon']} {t(str(c['name']).lower().replace(' ', '_'), default=c['name'])}") 
            for c in cards
        ]
        
        self._is_syncing = True
        self._is_saving = False
        self.purchase_name.value = ""
        self.purchase_card.value = None
        self.purchase_amount.value = ""
        self.purchase_amount.disabled = False
        self.purchase_monthly_amount.value = ""
        self.purchase_monthly_amount.disabled = True
        self.purchase_mode_radio.value = "total"
        self.purchase_months.value = "12"
        self.purchase_interest.value = "0"
        self.purchase_date.value = datetime.now().strftime("%d/%m/%Y")
        self._is_syncing = False
        
        self.credit_purchase_dialog.open = True
        self.page.update()

    def _save_credit_purchase(self, e):
        """Valida, calcula en caliente bajo demanda según el modo activo y persiste de forma aislada e idempotente."""
        if self._is_saving:
            return
            
        name_val = self.purchase_name.value.strip() if self.purchase_name.value else ""
        card_val = self.purchase_card.value
        date_val = self.purchase_date.value.strip() if self.purchase_date.value else ""
        months_val = self.purchase_months.value.strip() if self.purchase_months.value else "12"
        interest_val = self.purchase_interest.value.strip() if self.purchase_interest.value else "0"
        
        if not name_val:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("deudas_err_missing_name", default="Falta ingresar el concepto de la compra")), bgcolor=ft.Colors.RED_700)
            self.page.snack_bar.open = True
            self.page.update()
            return
            
        if not card_val:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("deudas_err_missing_card", default="Debes seleccionar una tarjeta de crédito")), bgcolor=ft.Colors.RED_700)
            self.page.snack_bar.open = True
            self.page.update()
            return
            
        if not date_val:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("deudas_err_missing_date", default="Selecciona una fecha válida")), bgcolor=ft.Colors.RED_700)
            self.page.snack_bar.open = True
            self.page.update()
            return

        db_date = None
        for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"]:
            try:
                db_date = datetime.strptime(date_val, fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue

        if not db_date:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("transaction_form_invalid_date", default="Formato de fecha inválido. Usa DD/MM/AAAA")), bgcolor=ft.Colors.RED_700)
            self.page.snack_bar.open = True
            self.page.update()
            return

        self._is_saving = True
        
        try:
            card_id = int(card_val)
            months = int(months_val) if months_val else 1
            interest = float(interest_val) if interest_val else 0.0
            if months < 1: 
                months = 1
                
            if self.purchase_mode_radio.value == "total":
                amount = float(self.purchase_amount.value) if self.purchase_amount.value else 0.0
            else:
                monthly = float(self.purchase_monthly_amount.value) if self.purchase_monthly_amount.value else 0.0
                total_pagar = monthly * months
                amount = total_pagar / (1 + (interest / 100))

            if amount <= 0:
                self.page.snack_bar = ft.SnackBar(content=ft.Text(t("deudas_err_missing_amount", default="Ingresa un monto válido para calcular la operación")), bgcolor=ft.Colors.RED_700)
                self.page.snack_bar.open = True
                self._is_saving = False
                self.page.update()
                return
            
            add_loan(
                name=name_val,
                total_amount=amount,
                interest_rate=interest,
                term_months=months,
                term_unit="Meses",
                start_date=db_date,
                icon="🔄",
                color=COLOR_ATARDECER,
                card_id=card_id
            )
            
            self.credit_purchase_dialog.open = False
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("deudas_purchase_registered", default="Compra a crédito registrada con éxito")), bgcolor=ft.Colors.GREEN_700)
            self.page.snack_bar.open = True
            self.page.update()
            self._refresh_view()
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(f"Error interno al guardar: {ex}"), bgcolor=ft.Colors.RED_700)
            self.page.snack_bar.open = True
            self.page.update()
        finally:
            self._is_saving = False

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
    
    def _calculate_specific_corte_debt(self, item, statement_cutoff_dt) -> tuple[float, float, float]:
        """Calcula de forma exacta las métricas de un corte específico barriendo todo el historial acumulado para evitar saldos fantasmas."""
        from datetime import datetime, timedelta
        from dateutil.relativedelta import relativedelta

        # Delimitar el inicio del ciclo de facturación mensual actual
        start_period_dt = statement_cutoff_dt - relativedelta(months=1) + timedelta(days=1)
        
        past_expenses = 0.0
        past_payments = 0.0
        current_expenses = 0.0
        current_payments_during_cycle = 0.0
        payments_after_current_cutoff = 0.0
        
        try:
            # Escaneo absoluto desde el inicio de los tiempos para saldar el arrastre histórico real
            card_txs = get_card_transactions(item["id"], "1900-01-01", "2035-12-31")
            for tx in card_txs:
                if tx.get("is_credit_purchase_parent") is True:
                    continue
                    
                try:
                    tx_dt = datetime.strptime(tx["date"][:10], "%Y-%m-%d").date()
                    is_expense = tx.get("type", "expense") == "expense"
                    amount = tx["amount"]
                    
                    # A. Transacciones de meses antiguos (Arrastre)
                    if tx_dt < start_period_dt.date():
                        if is_expense:
                            past_expenses += amount
                        else:
                            past_payments += amount
                            
                    # B. Transacciones dentro del ciclo de facturación activo
                    elif start_period_dt.date() <= tx_dt <= statement_cutoff_dt.date():
                        if is_expense:
                            current_expenses += amount
                        else:
                            current_payments_during_cycle += amount
                            
                    # C. Abonos extemporáneos realizados después del corte
                    elif tx_dt > statement_cutoff_dt.date():
                        if not is_expense:
                            payments_after_current_cutoff += amount
                except:
                    pass
        except:
            pass

        deuda_arrastrada = max(0.0, past_expenses - past_payments)
        
        total_exigible = deuda_arrastrada + current_expenses
        
        deuda_total_ciclo = total_exigible - current_payments_during_cycle
        remaining_corte = max(0.0, deuda_total_ciclo - payments_after_current_cutoff)
        
        imputed_payments = total_exigible - remaining_corte
        
        return remaining_corte, total_exigible, imputed_payments

    def _calculate_corte_debt(self, item) -> tuple[float, float, float]:
        """Determina el ciclo actual que se debe pagar en base al día límite de facturación."""
        cutoff_day = item.get("cutoff_day", 1)
        payment_due_day = item.get("payment_due_day", 26)
        now = datetime.now()
        
        if now.day <= payment_due_day:
            statement_cutoff_dt = datetime(now.year, now.month, cutoff_day)
        else:
            next_month = now + relativedelta(months=1)
            statement_cutoff_dt = datetime(next_month.year, next_month.month, cutoff_day)
            
        return self._calculate_specific_corte_debt(item, statement_cutoff_dt)
    
    def _check_card_overdue(self, item) -> bool:
        """Comprueba matemáticamente si el periodo anterior inmediato superó la fecha límite de pago sin liquidarse."""
        cutoff_day = item.get("cutoff_day", 1)
        payment_due_day = item.get("payment_due_day", 26)
        now = datetime.now()
        
        if now.day > payment_due_day:
            overdue_cutoff_dt = datetime(now.year, now.month, cutoff_day)
        else:
            prev_month = now - relativedelta(months=1)
            overdue_cutoff_dt = datetime(prev_month.year, prev_month.month, cutoff_day)
            
        rem, _, _ = self._calculate_specific_corte_debt(item, overdue_cutoff_dt)
        return rem > 0.05
    
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
        """Construye el contenido principal de la sección de créditos segmentando compras a meses y préstamos."""
        all_loans = get_all_loans_with_progress()
        
        credit_purchases = [l for l in all_loans if l["card_id"] is not None and l["remaining"] > 0]
        active_loans = [l for l in all_loans if l["card_id"] is None and l["remaining"] > 0]
        completed_loans = [l for l in all_loans if l["remaining"] <= 0]

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
                
                ft.Text(t("deudas_credit_purchases_section", default="Compras a Crédito / Mensualidades (Activas)"), size=20, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
                self._build_loans_section(credit_purchases, t("deudas_no_credit_purchases", default="No tienes compras a mensualidades activas.")),
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
                    t("deudas_new_credit_purchase", default="Compra a Crédito"), 
                    icon=ft.Icons.ADD_SHOPPING_CART,          
                    bgcolor=COLOR_ATARDECER, 
                    color=COLOR_BLANCO,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _: self._show_add_credit_purchase_dialog()
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
        """Construye las tarjetas de crédito inyectando dinámicamente el Modo Alerta Atardecer si se encuentra en mora."""
        balances = get_balance_by_payment_method()
        cards_ui = []

        for item in balances:
            if item["type"] == "card":
                limit = item.get("credit_limit", 0)
                raw_balance = item["balance"]
                is_frozen = item.get("status") == "frozen"
                is_overdue = self._check_card_overdue(item)
                
                card_name = t(str(item["name"]).lower().replace(" ", "_"), default=item["name"])
                card_bgcolor = COLOR_BLANCO
                card_border = ft.border.all(1, ft.Colors.with_opacity(0.08, COLOR_CIAN))
                
                if is_frozen:
                    card_name += t("settings_frozen_badge", default=" ❄️ [Congelada]")
                    card_bgcolor = ft.Colors.BLUE_50
                elif is_overdue:
                    card_bgcolor = COLOR_CREMA
                    card_border = ft.border.all(2, COLOR_ATARDECER)

                cutoff_debt, original_corte_debt, payments_after_cutoff = self._calculate_corte_debt(item)

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
                    texto_deuda = f"{t('deudas_favor_balance', default='Saldo a Favor:')} {self._clean_decimals(format_currency(saldo_a_favor))}" if saldo_a_favor > 0 else f"{t('deudas_debt_label', default='Deuda Total:')} $0 / {self._clean_decimals(format_currency(limit))}"
                    disponible_real = limit + saldo_a_favor

                str_corte_restante = self._clean_decimals(format_currency(cutoff_debt))
                str_original_corte = self._clean_decimals(format_currency(original_corte_debt))
                str_pagado_corte = self._clean_decimals(format_currency(payments_after_cutoff))

                label_corte = t("deudas_pay_at_cutoff", default="Por pagar al corte:")
                if is_overdue:
                    label_corte = f"⚠️ {t('deudas_status_overdue', default='Vencida (No pagada)')}:"

                btn_info = ft.Container(
                    content=ft.Text("ℹ️", size=15, color=COLOR_OCEANO),
                    padding=6, border_radius=6, ink=True, 
                    on_click=lambda e, card=item: self._show_card_history_dialog(card)
                )

                cards_ui.append(ft.Container(
                    width=350, bgcolor=card_bgcolor, padding=20, border_radius=16, border=card_border,
                    shadow=ft.BoxShadow(spread_radius=0, blur_radius=12, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 6)),
                    content=ft.Column([
                        ft.Row([
                            ft.Row([ft.Text(item["icon"], size=26), ft.Text(card_name, size=16, weight=ft.FontWeight.BOLD, color=COLOR_ATARDECER if is_overdue else ft.Colors.BLACK)], spacing=8),
                            btn_info 
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(height=12, color=ft.Colors.BLACK12),
                        ft.Row([
                            ft.Column([ft.Text(t("deudas_cutoff_day", default="Día Corte"), size=11, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_500), ft.Text(f"{item.get('cutoff_day', '-')}", size=13, weight=ft.FontWeight.BOLD)], spacing=2),
                            ft.Column([ft.Text(t("deudas_due_day", default="Día Pago"), size=11, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_500), ft.Text(f"{item.get('payment_due_day', '-')}", size=13, weight=ft.FontWeight.BOLD)], spacing=2),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Container(height=2),
                        ft.Text(texto_deuda, size=13, weight=ft.FontWeight.W_600, color=ft.Colors.GREEN_600 if saldo_a_favor > 0 else ft.Colors.GREY_700),
                        
                        ft.Text(f"{label_corte} {str_corte_restante} ({str_corte_restante} = {str_original_corte} - {str_pagado_corte})", size=12, weight=ft.FontWeight.BOLD, color=COLOR_ATARDECER if is_overdue else (ft.Colors.RED_400 if cutoff_debt > 0 else ft.Colors.GREEN_600)),
                        
                        ft.ProgressBar(value=usage_ratio, color=ft.Colors.ORANGE_500 if is_overdue else progress_color, bgcolor=ft.Colors.GREY_100, height=8),
                        ft.Text(f"{t('deudas_available', default='Disponible:')} {self._clean_decimals(format_currency(disponible_real))}", size=12, color=ft.Colors.GREEN_600 if disponible_real > 0 else ft.Colors.GREY_600, weight=ft.FontWeight.W_600)
                    ], spacing=6)
                ))
                
        if not cards_ui:
            return ft.Text(t("deudas_no_cards", default="No tienes tarjetas configuradas."), color=ft.Colors.GREY_500, italic=True, size=14)
            
        return ft.Row(controls=cards_ui, wrap=True, spacing=15)

    def _build_loans_section(self, loans_list, empty_message):
        """Construye las tarjetas de créditos y mensualidades asociando visualmente el método de pago origen en una matriz estructurada."""
        if not loans_list:
            return ft.Text(empty_message, color=ft.Colors.GREY_500, italic=True, size=14)

        # Consultar catálogo maestro de cuentas para resolver alias relacionales
        methods = get_payment_methods()
        method_dict = {m["id"]: m for m in methods}

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

            # Detectar si corresponde a una compra a crédito o a un préstamo tradicional
            is_credit_purchase = loan.get("card_id") is not None

            # Construcción modular de la grilla de metadatos según el tipo de deuda
            if is_credit_purchase:
                card_obj = method_dict.get(loan["card_id"])
                card_name_trans = t(str(card_obj["name"]).lower().replace(" ", "_"), default=card_obj["name"]) if card_obj else ""
                
                meta_grid = ft.Column([
                    ft.Row([
                        ft.Text(f"{t('deudas_start_date', default='Inicio:')} {display_date}", size=12, color=ft.Colors.GREY_600, weight=ft.FontWeight.W_500),
                        ft.Text(f"{t('deudas_term', default='Plazo:')} {loan.get('term_months', 0)} {unit_text}", size=12, color=ft.Colors.GREY_600, weight=ft.FontWeight.W_500)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([
                        ft.Row([
                            ft.Text(card_obj['icon'] if card_obj else "💳", size=14),
                            ft.Text(card_name_trans, size=12, color=ft.Colors.GREY_600, weight=ft.FontWeight.W_500)
                        ], spacing=4) if card_obj else ft.Container(),
                        ft.Text(f"{t('deudas_interest', default='Int:')} {loan['interest_rate']}%", size=12, color=ft.Colors.GREY_600, weight=ft.FontWeight.W_500)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ], spacing=4)
            else:
                meta_grid = ft.Column([
                    ft.Row([
                        ft.Text(t('deudas_start_date', default='Inicio:'), size=12, color=ft.Colors.GREY_600, weight=ft.FontWeight.W_500),
                        ft.Text(f"{t('deudas_term', default='Plazo:')} {loan.get('term_months', 0)} {unit_text}", size=12, color=ft.Colors.GREY_600, weight=ft.FontWeight.W_500)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([
                        ft.Text(display_date, size=12, color=ft.Colors.GREY_600, weight=ft.FontWeight.W_500),
                        ft.Text(f"{t('deudas_interest', default='Int:')} {loan['interest_rate']}%", size=12, color=ft.Colors.GREY_600, weight=ft.FontWeight.W_500)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ], spacing=4)

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
                    
                    meta_grid,
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
        """Renderiza el historial sincronizando las etiquetas 'Al Corte' con el ciclo de facturación activo de la tarjeta."""
        card_name_translated = t(str(card["name"]).lower().replace(" ", "_"), default=card["name"])
        cutoff_day = card.get("cutoff_day", 1)
        payment_due_day = card.get("payment_due_day", 26)
        is_overdue = self._check_card_overdue(card)
        
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
        past_target = now - relativedelta(months=2)
        start_date = f"{past_target.year}-{past_target.month:02d}-01"
        
        future_target = now + relativedelta(months=2)
        end_date = f"{future_target.year}-{future_target.month:02d}-01"
        
        # Sincronización exacta del ciclo de corte activo bajo la regla comercial del vencimiento
        if now.day <= payment_due_day:
            next_cutoff_dt = datetime(now.year, now.month, cutoff_day)
        else:
            next_month = now + relativedelta(months=1)
            next_cutoff_dt = datetime(next_month.year, next_month.month, cutoff_day)
        current_start_dt = next_cutoff_dt - relativedelta(months=1) + timedelta(days=1)

        transactions = get_card_transactions(card["id"], start_date, end_date)
        transactions.sort(key=lambda x: x.get("date", ""), reverse=self.history_sort_desc)
        
        self.card_history_list_ui.controls.clear()

        # Inyección dinámica del Banner UX Premium si está en mora
        if is_overdue:
            banner_mora = ft.Container(
                bgcolor=ft.Colors.ORANGE_50, padding=12, border_radius=12,
                border=ft.border.all(1, COLOR_ATARDECER),
                content=ft.Column([
                    ft.Row([
                        ft.Text("🚨", size=18),
                        ft.Text(t("deudas_banner_mora_text", default="Periodo en Mora: No se detectó el pago completo antes de la fecha límite."), size=12, color=COLOR_ATARDECER, weight="bold", expand=True)
                    ], spacing=8),
                    ft.Container(height=2),
                    ft.FilledButton(
                        t("deudas_btn_apply_late_fee", default="Registrar Recargo"),
                        icon=ft.Icons.MONETIZATION_ON, bgcolor=COLOR_ATARDECER, color=COLOR_BLANCO,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=lambda _, c=card: self._show_late_fee_dialog(c)
                    )
                ], spacing=5, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            )
            self.card_history_list_ui.controls.append(banner_mora)
        
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
                        if t_idx.get("is_credit_purchase_parent") is True:
                            continue
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
                    if tx_dt and current_start_dt <= tx_dt <= next_cutoff_dt:
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
        """Construye una celda de transacción aplicando opacidad atenuada si es el registro maestro e inyectando la etiqueta de Corte a mensualidades vigentes."""
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
        
        is_parent = trans.get("is_credit_purchase_parent") is True
        is_inst = trans.get("is_credit_purchase_installment") is True
        
        if is_parent:
            title_translated = t("deudas_credit_purchase_label", default="Compra a Crédito")
            display_icon = trans.get('category_icon', '🔄')
        elif is_inst:
            title_translated = t("deudas_installment_label", default="Mensualidad Tarjeta")
            display_icon = trans.get('category_icon', '📅')
        elif is_expense:
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

        show_corte_badge = (border_color == ft.Colors.RED_400 and is_expense and not is_parent)

        return ft.Container(
            bgcolor=COLOR_BLANCO, padding=12, border_radius=12,
            border=ft.border.all(border_width, border_color),
            opacity=0.45 if is_parent else 1.0,
            content=ft.Row([
                ft.Row([
                    ft.Text(display_icon, size=22), 
                    ft.Column([
                        ft.Row([
                            ft.Text(title_translated, size=14, color=COLOR_OCEANO, weight=ft.FontWeight.BOLD),
                            ft.Container(
                                content=ft.Text(t("deudas_lbl_corte", default="Al Corte"), size=9, color="white", weight="bold"),
                                bgcolor=ft.Colors.RED_400, padding=ft.padding.symmetric(horizontal=5, vertical=1), border_radius=4
                            ) if show_corte_badge else ft.Container()
                        ], spacing=6),
                        ft.Text(short_desc, size=11, color=ft.Colors.GREY_600) if (short_desc and (is_expense or is_inst)) else ft.Container()
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
            if hasattr(val, "strftime"):
                self.loan_date.value = val.strftime("%d/%m/%Y")
            else:
                val_str = str(val).split("T")[0].split(" ")[0].strip()
                parsed = False
                
                for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
                    try:
                        date_obj = datetime.strptime(val_str, fmt)
                        self.loan_date.value = date_obj.strftime("%d/%m/%Y")
                        parsed = True
                        break
                    except ValueError:
                        continue
                
                if not parsed:
                    self.loan_date.value = val_str
                    
            self.page.update()

    def _init_loan_dialog(self):
        decimal_filter = ft.InputFilter(allow=True, regex_string=r"^[0-9]*(?:\.[0-9]*)?$")
        int_filter = ft.InputFilter(allow=True, regex_string=r"^[0-9]*$")
        date_filter = ft.InputFilter(allow=True, regex_string=r"^[0-9]/]*$")

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
        """Habilita limpiamente todas las entradas para préstamos tradicionales."""
        self.editing_loan_id = None
        self.loan_dialog.title.value = t("deudas_register_loan", default="Registrar Nuevo Préstamo")
        
        self.loan_name.disabled = False
        self.loan_amount.disabled = False
        self.loan_term_num.disabled = False
        self.loan_term_unit.disabled = False
        self.loan_interest.disabled = False
        
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
        """Abre el diálogo bloqueando todos los parámetros aritméticos si corresponde a una compra a crédito."""
        self.editing_loan_id = loan["id"]
        is_credit_purchase = loan.get("card_id") is not None
        
        if is_credit_purchase:
            self.loan_dialog.title.value = t("deudas_edit_credit_purchase", default="Editar Compra a Crédito")
            self.loan_name.disabled = False
            self.loan_amount.disabled = True
            self.loan_term_num.disabled = True
            self.loan_term_unit.disabled = True
            self.loan_interest.disabled = True
            self.loan_date.disabled = True
            self.loan_date_btn.disabled = True
        else:
            self.loan_dialog.title.value = t("three_panel_edit_card", default="Editar Préstamo")
            self.loan_name.disabled = False
            self.loan_amount.disabled = False
            self.loan_term_num.disabled = False
            self.loan_term_unit.disabled = False
            self.loan_interest.disabled = False
            self.loan_date.disabled = True
            self.loan_date_btn.disabled = True

        self.loan_name.value = loan["name"]
        self.loan_amount.value = str(loan["total_amount"])
        self.loan_term_num.value = str(loan.get("term_months", 12))
        self.loan_term_unit.value = loan.get("term_unit", "Meses")
        self.loan_interest.value = str(loan["interest_rate"])
        
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
        """Muestra el diálogo de amortización con RadioButtons fijos y comportamiento dinámico desempaquetando correctamente las tuplas analíticas."""
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
                    # Solución: Desempaquetado explícito de la tupla devuelta por el motor
                    corte_calculated, _, _ = self._calculate_corte_debt(card_item_full)
            
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
                    # Solución: Desempaquetado explícito de la tupla devuelta por el motor
                    real_corte, _, _ = self._calculate_corte_debt(dest_method)
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

    def _init_late_fee_dialog(self):
        """Inicializa el formulario autocontenido para el registro de recargos por morosidad."""
        decimal_filter = ft.InputFilter(allow=True, regex_string=r"^[0-9]*(?:\.[0-9]*)?$")
        date_filter = ft.InputFilter(allow=True, regex_string=r"^[0-9]/]*$")

        self.late_fee_date_picker = ft.DatePicker(
            on_change=self._on_late_fee_date_change,
            first_date=datetime(2020, 1, 1),
            last_date=datetime(2035, 12, 31)
        )
        self.page.overlay.append(self.late_fee_date_picker)

        self.late_fee_amount = ft.TextField(label=t("deudas_late_fee_amount", default="Monto del Recargo / Interés"), keyboard_type=ft.KeyboardType.NUMBER, input_filter=decimal_filter, max_length=25, prefix=ft.Text("$"), color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=350)
        self.late_fee_card_name = ft.TextField(label=t("deudas_late_fee_card_locked", default="Tarjeta Afectada (Bloqueada)"), disabled=True, color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=350)
        self.late_fee_date = ft.TextField(label=t("deudas_loan_start_date", default="Fecha (DD/MM/AAAA)"), input_filter=date_filter, max_length=10, color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=290)
        
        def open_late_fee_picker(_):
            self.late_fee_date_picker.open = True
            self.page.update()

        self.late_fee_date_btn = ft.IconButton(icon=ft.Icons.CALENDAR_MONTH, icon_color=COLOR_OCEANO, on_click=open_late_fee_picker)
        self.late_fee_note = ft.TextField(label=t("transaction_form_description", default="Nota (opcional)"), value=t("deudas_late_fee_default_note", default="Recargo por pago extemporáneo"), max_length=100, color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), width=350)

        self.late_fee_dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA,
            title=ft.Text(t("deudas_register_late_fee_title", default="Registrar Gastos por Mora"), color=COLOR_OCEANO, weight=ft.FontWeight.BOLD),
            content=ft.Column([
                self.late_fee_card_name,
                self.late_fee_amount,
                ft.Row([self.late_fee_date, self.late_fee_date_btn], spacing=10),
                self.late_fee_note
            ], tight=True, spacing=15),
            actions=[
                ft.TextButton(t("settings_cancel", default="Cancelar"), on_click=lambda _: self._close_dialog(self.late_fee_dialog)),
                ft.FilledButton(t("three_panel_save", default="Guardar"), bgcolor=COLOR_OCEANO, color=COLOR_BLANCO, on_click=self._save_late_fee)
            ]
        )
        self.page.overlay.append(self.late_fee_dialog)
        self._active_late_fee_card_id = None

    def _on_late_fee_date_change(self, e):
        """Manejador síncrono para el formateo del selector de fecha de recargos."""
        if e.control.value:
            val = e.control.value
            self.late_fee_date.value = val.strftime("%d/%m/%Y") if hasattr(val, "strftime") else str(val).split(" ")[0]
            self.page.update()

    def _show_late_fee_dialog(self, card):
        """Abre el formulario bloqueando el método de pago de forma segura a la tarjeta seleccionada."""
        self._active_late_fee_card_id = card["id"]
        self.late_fee_card_name.value = card["name"]
        self.late_fee_amount.value = ""
        self.late_fee_date.value = datetime.now().strftime("%d/%m/%Y")
        
        self.card_history_dialog.open = False
        self.late_fee_dialog.open = True
        self.page.update()

    def _save_late_fee(self, e):
        """Persiste el recargo bancario validando estrictamente que la fecha sea posterior o igual al corte del periodo en mora."""
        if not self.late_fee_amount.value or float(self.late_fee_amount.value or 0) <= 0:
            return
            
        try:
            input_dt = datetime.strptime(self.late_fee_date.value, "%d/%m/%Y").date()
            db_date = input_dt.strftime("%Y-%m-%d")
        except ValueError:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("transaction_form_invalid_date", default="Formato de fecha inválido. Usa DD/MM/AAAA")), bgcolor=ft.Colors.RED_700)
            self.page.snack_bar.open = True
            self.page.update()
            return

        import sqlite3
        from database.connection import get_connection
        
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Obtener el día de corte de la tarjeta activa para validar la regla de UX Senior
            cursor.execute("SELECT cutoff_day FROM payment_methods WHERE id = ?", (self._active_late_fee_card_id,))
            c_row = cursor.fetchall()
            cutoff_day = int(c_row[0]["cutoff_day"]) if c_row and c_row[0]["cutoff_day"] else 1
            
            # El recargo debe pertenecer al ciclo de facturación cerrado o posterior
            from dateutil.relativedelta import relativedelta
            from datetime import date
            now = datetime.now()
            prev_month = now - relativedelta(months=1)
            cutoff_boundary_dt = date(prev_month.year, prev_month.month, cutoff_day)
            
            if input_dt < cutoff_boundary_dt:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(t("deudas_late_fee_date_error", default="La fecha del recargo debe ser igual o posterior al día de corte de la factura vencida.")),
                    bgcolor=ft.Colors.RED_700
                )
                self.page.snack_bar.open = True
                self.page.update()
                conn.close()
                return

            cursor.execute("SELECT id FROM categories WHERE name IN ('Otros gastos', 'Pago de tarjetas') AND type = 'expense' LIMIT 1")
            cat_row = cursor.fetchone()
            category_id = cat_row["id"] if cat_row else 1
            
            cursor.execute("""
                INSERT INTO transactions (category_id, payment_method_id, amount, description, type, date, is_recurrence_active)
                VALUES (?, ?, ?, ?, 'expense', ?, 0)
            """, (category_id, self._active_late_fee_card_id, float(self.late_fee_amount.value), self.late_fee_note.value, db_date))
            
            conn.commit()
            self.late_fee_dialog.open = False
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("deudas_late_fee_success", default="Recargo por morosidad registrado con éxito")), bgcolor=ft.Colors.GREEN_700)
            self.page.snack_bar.open = True
            self._refresh_view()
        except sqlite3.Error:
            conn.rollback()
        finally:
            conn.close()

def create_deudas_view(page: ft.Page) -> ft.Container:
    view = DeudasView(page)
    return view.get_view()