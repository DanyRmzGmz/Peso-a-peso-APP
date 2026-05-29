"""
Vista de Configuración (Settings) de la aplicación.
Permite gestionar variables de entorno, cuentas bancarias, PIN de acceso, 
sincronización de Google Authenticator (TOTP), respaldos y purga de base de datos.
Refactorizado con dimensiones extendidas para bilingüismo y persistencia de foco en refresco.
"""
import flet as ft
import os
import tkinter as tk 
from tkinter import filedialog
from datetime import datetime
import hashlib
import pyotp
import qrcode
import base64
from io import BytesIO
from core.colors import COLOR_CREMA, COLOR_OCEANO, COLOR_BLANCO, COLOR_ATARDECER, COLOR_ARENA, COLOR_CIAN, GRADIENTE_FONDO_SUAVE, GRADIENTE_DESTACADO
from database.connection import (
    set_initial_balance, get_initial_balance, save_setting, get_setting, hard_reset_database,
    get_payment_methods, add_payment_method, delete_payment_method, update_payment_method,
    save_transaction, get_initial_balance_category_id, backup_database, restore_database,
    get_balance_by_payment_method, freeze_payment_method, archive_payment_method, get_connection
)
from core.translations import t

class SettingsView:
    def __init__(self, page: ft.Page):
        self.page = page
        self.current_edit_id = None
        self.int_filter = ft.InputFilter(allow=True, regex_string=r"^[0-9]*$")
        self.decimal_filter = ft.InputFilter(allow=True, regex_string=r"^[0-9]*(?:\.[0-9]*)?$")
        
        self.is_verify_totp_mode = False
        
        self._init_add_method_dialog()
        self._init_delete_dialog()
        self._init_delete_account_dialog()
        self._init_security_dialog()
        self._init_verify_dialog()
        self._init_totp_dialog()
        
        self.setup_ui()

    def setup_ui(self):
        self.main_column = self.build_content()
        self.main_container = ft.Container(
            gradient=GRADIENTE_FONDO_SUAVE, expand=True, padding=ft.padding.only(left=25, right=25, top=15, bottom=25),
            alignment=ft.Alignment(0, -1),
            content=ft.Container(content=self.main_column, width=1300, alignment=ft.Alignment(0, -1))
        )

    # =========================================================================
    # INICIALIZACIÓN DE DIÁLOGOS (MODALES) OPTIMIZADOS
    # =========================================================================
    def _init_add_method_dialog(self):
        self.tipo_radio = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="card", label=t("settings_credit_card"), active_color=COLOR_OCEANO), 
                ft.Radio(value="bank_account", label=t("settings_debit_account"), active_color=COLOR_OCEANO)
            ]), 
            value="card", 
            on_change=self._on_tipo_radio_change
        )
        self.banco_dropdown = ft.Dropdown(label=t("settings_bank"), options=[], value="BBVA", color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO))
        self.banco_custom = ft.TextField(label="Otro banco", color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO))
        self.terminacion = ft.TextField(label=t("settings_last_4_digits"), max_length=4, input_filter=self.int_filter, color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO))
        
        # Nuevo campo opcional de Alias limitado a 15 caracteres
        self.alias_input = ft.TextField(
            label=t("settings_alias", default="Alias de la cuenta (Opcional)"), 
            max_length=15, 
            color=COLOR_OCEANO, 
            label_style=ft.TextStyle(color=COLOR_OCEANO), 
            border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO)
        )
        
        self.saldo_inicial_input = ft.TextField(label=t("settings_initial_balance_input"), input_filter=self.decimal_filter, prefix=ft.Text("$"), color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO), visible=False)
        self.limite_input = ft.TextField(label=t("settings_credit_limit"), input_filter=self.decimal_filter, prefix=ft.Text("$"), color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO))
        self.corte_input = ft.TextField(label=t("settings_cutoff_day"), input_filter=self.int_filter, max_length=2, expand=True, color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO))
        self.pago_input = ft.TextField(label=t("settings_due_day"), input_filter=self.int_filter, max_length=2, expand=True, color=COLOR_OCEANO, label_style=ft.TextStyle(color=COLOR_OCEANO), border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO))
        
        self.seccion_credito = ft.Column([
            ft.Container(height=10), 
            ft.Text(t("settings_credit_card_details"), size=14, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO), 
            self.limite_input, 
            ft.Row([self.corte_input, self.pago_input], spacing=10)
        ])
        
        self.dialog_content_col = ft.Column([
            ft.Text(t("settings_account_type"), weight=ft.FontWeight.BOLD, color=COLOR_OCEANO), 
            self.tipo_radio, self.banco_dropdown, self.banco_custom, self.terminacion, self.alias_input, 
            self.saldo_inicial_input, self.seccion_credito
        ], tight=True, scroll=ft.ScrollMode.AUTO, spacing=12)
        
        self.add_dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA, 
            title=ft.Text(t("settings_add_new_account"), weight=ft.FontWeight.BOLD, color=COLOR_OCEANO), 
            content=self.dialog_content_col, 
            actions=[
                ft.TextButton(t("settings_cancel"), on_click=self._close_add_dialog), 
                ft.FilledButton(t("settings_save_account"), on_click=self._save_action, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), bgcolor=COLOR_OCEANO, color=COLOR_BLANCO)
            ]
        )
        self.page.overlay.append(self.add_dialog)

    def _init_delete_account_dialog(self):
        self.delete_acc_dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA,
            title=ft.Text(t("settings_delete_account"), weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
            content=ft.Text(t("settings_confirm_delete_account"), color=COLOR_OCEANO),
            actions=[
                ft.TextButton(t("settings_cancel"), on_click=self._close_delete_acc_dialog),
                ft.FilledButton(t("settings_delete"), on_click=self._confirm_delete_account, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), bgcolor=COLOR_OCEANO, color=COLOR_BLANCO)
            ]
        )
        self.page.overlay.append(self.delete_acc_dialog)
        self.account_id_to_delete = None

    def _init_security_dialog(self):
        # Corregido can_reveal por can_reveal_password para compatibilidad nativa con Flet
        self.pin_input1 = ft.TextField(label=t("settings_pin_new"), password=True, can_reveal_password=True, keyboard_type=ft.KeyboardType.NUMBER, color=COLOR_OCEANO, border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO))
        self.pin_input2 = ft.TextField(label=t("settings_pin_confirm"), password=True, can_reveal_password=True, keyboard_type=ft.KeyboardType.NUMBER, color=COLOR_OCEANO, border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO))
        self.pin_error = ft.Text(t("settings_pin_error_match"), color=ft.Colors.RED_500, visible=False, weight=ft.FontWeight.BOLD)
        self.security_dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA,
            modal=True, 
            title=ft.Text(t("settings_pin_setup"), weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
            content=ft.Column([self.pin_input1, self.pin_input2, self.pin_error], tight=True, spacing=12),
            actions=[
                ft.TextButton(t("settings_cancel"), on_click=self._cancel_security_setup), 
                ft.FilledButton(t("settings_save"), on_click=self._save_security_pin, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), bgcolor=COLOR_OCEANO, color=COLOR_BLANCO)
            ]
        )
        self.page.overlay.append(self.security_dialog)

    def _init_verify_dialog(self):
        self.verify_pin_input = ft.TextField(label=t("settings_enter_current_pin"), password=True, can_reveal_password=True, keyboard_type=ft.KeyboardType.NUMBER, color=COLOR_OCEANO, border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO))
        self.verify_error = ft.Text(t("settings_pin_incorrect"), color=ft.Colors.RED_500, visible=False, weight=ft.FontWeight.BOLD)
        
        self.btn_verify_recovery = ft.TextButton(
            content=ft.Row([ft.Text("📱"), ft.Text(t("auth_recovery_title", "Usar Authenticator"), color=COLOR_OCEANO, weight=ft.FontWeight.BOLD)], tight=True),
            on_click=self._toggle_verify_mode,
            visible=False
        )

        self.verify_dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA,
            modal=True, 
            title=ft.Text(t("settings_verify_pin"), weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
            content=ft.Column([self.verify_pin_input, self.verify_error, self.btn_verify_recovery], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
            actions=[
                ft.TextButton(t("settings_cancel"), on_click=self._cancel_verify), 
                ft.FilledButton(t("settings_confirm"), on_click=self._confirm_verify, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), bgcolor=COLOR_OCEANO, color=COLOR_BLANCO)
            ]
        )
        self.page.overlay.append(self.verify_dialog)
        self.action_after_verify = None

    def _init_totp_dialog(self):
        self.qr_container = ft.Container(alignment=ft.Alignment(0,0))
        self.secret_text = ft.Text(weight=ft.FontWeight.BOLD, size=16, color=COLOR_OCEANO, selectable=True)
        self.totp_input = ft.TextField(label=t("settings_totp_verify"), keyboard_type=ft.KeyboardType.NUMBER, max_length=6, width=200, text_align=ft.TextAlign.CENTER, color=COLOR_OCEANO, border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO))
        self.totp_error = ft.Text(t("settings_totp_error"), color=ft.Colors.RED_500, visible=False, weight=ft.FontWeight.BOLD)
        self.totp_dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA,
            modal=True, 
            title=ft.Text(t("settings_setup_authenticator"), weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
            content=ft.Column([ft.Text(t("settings_totp_instructions"), color=COLOR_OCEANO, text_align=ft.TextAlign.CENTER), self.qr_container, ft.Row([ft.Text("Clave manual: ", color=COLOR_OCEANO), self.secret_text], alignment=ft.MainAxisAlignment.CENTER), ft.Container(height=5), self.totp_input, self.totp_error], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            actions=[
                ft.TextButton(t("settings_cancel"), on_click=lambda e: self._close_totp_dialog()), 
                ft.FilledButton(t("settings_confirm"), on_click=self._save_totp, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), bgcolor=COLOR_OCEANO, color=COLOR_BLANCO)
            ],
            actions_alignment=ft.MainAxisAlignment.CENTER
        )
        self.page.overlay.append(self.totp_dialog)
        self.current_totp_secret = None

    def _init_delete_dialog(self):
        self.delete_dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA, 
            modal=True,
            title=ft.Text(t("settings_irreversible_action"), color=COLOR_ATARDECER, weight=ft.FontWeight.BOLD),
            content=ft.Text(t("settings_confirm_delete_history"), color=COLOR_OCEANO),
            actions=[
                ft.TextButton(
                    content=ft.Text(t("settings_cancel"), color=COLOR_OCEANO, weight=ft.FontWeight.W_500), 
                    on_click=self._close_delete_dialog
                ), 
                ft.TextButton(
                    content=ft.Text(t("settings_confirm_delete"), weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400),
                    on_click=self._confirm_delete
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.overlay.append(self.delete_dialog)

    # =========================================================================
    # LÓGICA DE SEGURIDAD (NIP Y TOTP HÍBRIDO)
    # =========================================================================
    def _toggle_security(self, e):
        if self.switch_seguridad.value:
            self._open_security_dialog()
        else:
            self.switch_seguridad.value = True 
            self.page.update()
            self._open_verify_dialog(action="disable")

    def _open_verify_dialog(self, action: str):
        self.action_after_verify = action
        is_pin_enabled = get_setting("security_enabled", "0") == "1"
        has_totp = bool(get_setting("totp_secret", ""))
        lang = get_setting("language", "es")
        
        self.verify_error.visible = False
        self.verify_pin_input.value = ""
        
        if is_pin_enabled:
            self.is_verify_totp_mode = False
            self.verify_dialog.title.value = t("settings_verify_pin")
            self.verify_pin_input.label = t("settings_enter_current_pin")
            self.verify_pin_input.password = True
            self.verify_pin_input.max_length = None
            self.btn_verify_recovery.visible = has_totp
        else:
            self.is_verify_totp_mode = True
            self.verify_dialog.title.value = t("auth_totp_dialog_title", default="Validación via Authenticator" if lang == "es" else "Authenticator Verification")
            self.verify_pin_input.label = t("auth_totp_input_label", default="Ingresa código de 6 dígitos" if lang == "es" else "Enter 6-digit code")
            self.verify_pin_input.password = False
            self.verify_pin_input.max_length = 6
            self.btn_verify_recovery.visible = False
            
        self.verify_dialog.open = True
        self.page.update()

    def _toggle_verify_mode(self, e):
        self.is_verify_totp_mode = True
        lang = get_setting("language", "es")
        self.verify_dialog.title.value = t("auth_totp_dialog_title", default="Validación via Authenticator" if lang == "es" else "Authenticator Verification")
        self.verify_pin_input.label = t("auth_totp_input_label", default="Ingresa código de 6 dígitos" if lang == "es" else "Enter 6-digit code")
        self.verify_pin_input.password = False
        self.verify_pin_input.max_length = 6
        self.verify_error.visible = False
        self.btn_verify_recovery.visible = False
        self.page.update()

    def _cancel_verify(self, e):
        self.verify_dialog.open = False
        self.page.update()

    def _confirm_verify(self, e):
        input_code = self.verify_pin_input.value.strip().replace(" ", "").replace("-", "")
        if not input_code: return

        is_valid = False

        if self.is_verify_totp_mode:
            totp_secret = get_setting("totp_secret", "")
            if totp_secret:
                is_valid = pyotp.TOTP(totp_secret).verify(input_code)
        else:
            input_hash = hashlib.sha256(input_code.encode()).hexdigest()
            is_valid = (input_hash == get_setting("app_pin_hash"))

        if is_valid:
            self.verify_error.visible = False
            self.verify_dialog.open = False
            
            if self.action_after_verify == "disable":
                save_setting("security_enabled", "0")
                save_setting("app_pin_hash", "")
                
                self.switch_seguridad.value = False
                self.btn_change_pin.visible = False
                self.btn_setup_totp.visible = False
            elif self.action_after_verify == "change": 
                self._open_security_dialog()
            elif self.action_after_verify == "backup": 
                self._export_backup(None)
            elif self.action_after_verify == "restore":
                self._restore_backup(None)
            elif self.action_after_verify == "disable_backup_safety":
                save_setting("require_2fa_backup", "0")
                self.switch_2fa_backup.value = False

            self.page.update()
        else:
            self.verify_error.value = "Código Authenticator inválido" if self.is_verify_totp_mode else t("settings_pin_incorrect")
            self.verify_error.visible = True
            self.verify_pin_input.value = ""
            self.page.update()
            self.verify_pin_input.focus()

    def _open_security_dialog(self):
        self.pin_input1.value = ""
        self.pin_input2.value = ""
        self.pin_error.visible = False
        self.security_dialog.open = True
        self.page.update()

    def _cancel_security_setup(self, e):
        self.security_dialog.open = False
        if get_setting("security_enabled", "0") == "0": 
            self.switch_seguridad.value = False
        self.page.update()

    def _save_security_pin(self, e):
        pin1 = self.pin_input1.value.strip()
        pin2 = self.pin_input2.value.strip()
        
        if not pin1:
            self.pin_error.value = "El NIP no puede estar vacío."
            self.pin_error.visible = True
            self.page.update()
            return
            
        if pin1 != pin2: 
            self.pin_error.value = t("settings_pin_error_match", "Los NIPs no coinciden.")
            self.pin_error.visible = True
            self.page.update()
            return
            
        pin_hash = hashlib.sha256(pin1.encode()).hexdigest()
        save_setting("security_enabled", "1")
        save_setting("app_pin_hash", pin_hash)
        self.security_dialog.open = False
        self.btn_change_pin.visible = True
        self.btn_setup_totp.visible = True
        self.page.snack_bar = ft.SnackBar(content=ft.Text(t("settings_pin_success", "NIP guardado con éxito.")), bgcolor=ft.Colors.GREEN_700)
        self.page.snack_bar.open = True
        self.page.update()

    def _open_totp_dialog(self, e):
        self.current_totp_secret = pyotp.random_base32()
        uri = pyotp.totp.TOTP(self.current_totp_secret).provisioning_uri(name="Peso a Peso", issuer_name="Finanzas")
        img = qrcode.make(uri)
        buf = BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        
        self.qr_container.content = ft.Image(src=f"data:image/png;base64,{b64}", width=200, height=200, fit="contain")
        self.secret_text.value = self.current_totp_secret
        self.totp_input.value = ""
        self.totp_error.visible = False
        self.totp_dialog.open = True
        self.page.update()

    def _close_totp_dialog(self): 
        self.totp_dialog.open = False
        self.page.update()

    def _save_totp(self, e):
        code = self.totp_input.value.replace(" ", "").replace("-", "").strip()
        if not code: return
        if pyotp.TOTP(self.current_totp_secret).verify(code):
            save_setting("totp_secret", self.current_totp_secret)
            self.totp_dialog.open = False
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("settings_totp_success")), bgcolor=ft.Colors.GREEN_700)
            self.page.snack_bar.open = True
            self.page.update()
        else: 
            self.totp_error.visible = True
            self.totp_input.value = ""
            self.page.update()
            self.totp_input.focus()

    # =========================================================================
    # LÓGICA PROTECTORA DE RESPALDOS
    # =========================================================================
    def _toggle_backup_safety(self, e):
        if self.switch_2fa_backup.value:
            save_setting("require_2fa_backup", "1")
        else:
            self.switch_2fa_backup.value = True
            self.page.update()
            self._open_verify_dialog("disable_backup_safety")

    def _request_security_for_backup(self, e):
        if get_setting("require_2fa_backup", "0") == "1":
            self._open_verify_dialog("backup")
        else:
            self._export_backup(None)

    def _request_security_for_restore(self, e):
        if get_setting("require_2fa_backup", "0") == "1":
            self._open_verify_dialog("restore")
        else:
            self._restore_backup(None)

    def _export_backup(self, e):
        root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"peso_a_peso_backup_{timestamp}.db"
        ruta_destino = filedialog.asksaveasfilename(title=t("settings_export_backup"), initialfile=default_name, defaultextension=".db", filetypes=[("SQLite Database", "*.db")])
        root.destroy()
        if ruta_destino:
            try:
                backup_database(ruta_destino)
                self.page.snack_bar = ft.SnackBar(content=ft.Text(t("settings_backup_success")), bgcolor=ft.Colors.GREEN_700)
                self.page.snack_bar.open = True
                self.page.update()
            except Exception:
                self.page.snack_bar = ft.SnackBar(content=ft.Text(t("settings_backup_error")), bgcolor=ft.Colors.RED_700)
                self.page.snack_bar.open = True
                self.page.update()

    def _restore_backup(self, e):
        root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
        ruta_origen = filedialog.askopenfilename(title=t("settings_restore_backup"), filetypes=[("SQLite Database", "*.db")])
        root.destroy()
        if ruta_origen:
            try:
                restore_database(ruta_origen)
                self.page.snack_bar = ft.SnackBar(content=ft.Text(t("settings_restore_success")), bgcolor=ft.Colors.GREEN_700)
                self.page.snack_bar.open = True
                self._refresh_view()
            except Exception:
                self.page.snack_bar = ft.SnackBar(content=ft.Text(t("settings_restore_error")), bgcolor=ft.Colors.RED_700)
                self.page.snack_bar.open = True
                self.page.update()

    # =========================================================================
    # CONSTRUCCIÓN DE LA INTERFAZ DE USUARIO (UI) CARD PREMIUM
    # =========================================================================
    def build_content(self):
        current_username = get_setting("username", "Usuario")
        
        self.username_field = ft.TextField(
            label=t("settings_username", "Nombre del Usuario"),
            value=current_username,
            width=300,   
            height=45,   
            bgcolor=COLOR_BLANCO,
            color=ft.Colors.BLACK,
            border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO),
            focused_border_color=COLOR_OCEANO,
            label_style=ft.TextStyle(color=ft.Colors.GREY_600)
        )

        header_main_row = ft.Row(
            controls=[
                ft.Row([
                    ft.Icon(ft.Icons.SETTINGS_ROUNDED, color=COLOR_OCEANO, size=28),
                    ft.Text(t("settings_title", "Configuración"), size=26, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
                ], spacing=10),
                ft.Container(content=self.username_field, padding=ft.padding.only(top=5))
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

        current_balance = get_initial_balance()
        self.balance_field = ft.TextField(label=t("settings_initial_balance"), value=str(current_balance), prefix=ft.Text("$ "), keyboard_type=ft.KeyboardType.NUMBER, width=370, height=45, content_padding=10, disabled=(current_balance > 0), bgcolor=COLOR_BLANCO, border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO), focused_border_color=COLOR_OCEANO)
        
        current_lang = get_setting("language", "es")
        self.lang_dropdown = ft.Dropdown(label=t("settings_lang"), options=[ft.dropdown.Option("es", t("settings_lang_spanish")), ft.dropdown.Option("en", t("settings_lang_english"))], value=current_lang, width=370, bgcolor=COLOR_BLANCO, border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO))
        
        current_currency = get_setting("currency", "MXN")
        self.currency_dropdown = ft.Dropdown(
            label=t("settings_currency"), 
            options=[
                ft.dropdown.Option("MXN", t("settings_currency_mxn", "MXN (Peso Mexicano)")), 
                ft.dropdown.Option("USD", t("settings_currency_usd", "USD (Dólar)")),
                ft.dropdown.Option("EUR", t("settings_currency_eur", "EUR (Euro)"))
            ], 
            value=current_currency, width=370, bgcolor=COLOR_BLANCO, border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO)
        )
        
        current_rows = get_setting("table_rows_per_page", "20")
        opciones_filas = ["10","20", "30", "40", "50", "60", "70", "80", "90", "100"]
        if current_rows not in opciones_filas:
            opciones_filas.insert(0, current_rows)
            
        self.rows_dropdown = ft.Dropdown(
            label=t("settings_rows_per_page", default="Registros por página" if current_lang == "es" else "Rows per page"),
            options=[ft.dropdown.Option(val) for val in opciones_filas],
            value=current_rows,
            width=370,
            bgcolor=COLOR_BLANCO,
            border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO)
        )
        
        ruta_actual = get_setting("export_path", "")
        self.path_input = ft.TextField(label=t("settings_export_path"), value=ruta_actual, hint_text="C:\\Users\\...", prefix=ft.Text("📁 "), width=275, height=45, content_padding=10, bgcolor=COLOR_BLANCO, border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO), focused_border_color=COLOR_OCEANO)
        btn_explorar = ft.Container(content=ft.Text(t("settings_browse"), color=COLOR_BLANCO, weight=ft.FontWeight.BOLD, size=13), bgcolor=COLOR_OCEANO, padding=ft.padding.symmetric(horizontal=15, vertical=12), border_radius=8, ink=True, on_click=self.seleccionar_carpeta)
        fila_ruta = ft.Row([self.path_input, btn_explorar], alignment=ft.MainAxisAlignment.START, spacing=8)
        
        self.switch_sobregiro = ft.Switch(label=t("settings_allow_overdraft"), value=(get_setting("allow_overdraft", "0") == "1"), on_change=self._toggle_sobregiro, active_color=COLOR_OCEANO)
        self.switch_ajuste_quincena = ft.Switch(label=t("settings_adjust_biweekly_weekend"), value=(get_setting("adjust_biweekly_weekend", "0") == "1"), on_change=self._toggle_ajuste_quincena, active_color=COLOR_OCEANO)
        
        is_security_on = get_setting("security_enabled", "0") == "1"
        self.switch_seguridad = ft.Switch(label=t("settings_enable_pin"), value=is_security_on, on_change=self._toggle_security, active_color=COLOR_OCEANO)
        self.btn_change_pin = ft.TextButton(content=ft.Row([ft.Text("🔒", size=14), ft.Text(t("settings_change_pin"), color=COLOR_OCEANO, weight=ft.FontWeight.BOLD)], tight=True), on_click=lambda _: self._open_verify_dialog("change"), visible=is_security_on)
        self.btn_setup_totp = ft.TextButton(content=ft.Row([ft.Text("📱", size=14), ft.Text(t("settings_setup_authenticator"), color=COLOR_OCEANO, weight=ft.FontWeight.BOLD)], tight=True), on_click=self._open_totp_dialog, visible=is_security_on)
        
        save_button = ft.FilledButton(
            content=ft.Text(t("settings_save"), weight=ft.FontWeight.BOLD), 
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), 
            bgcolor=COLOR_OCEANO, color=COLOR_BLANCO, 
            on_click=self.save_all_settings,
            width=370, height=44
        )
        
        self.switch_2fa_backup = ft.Switch(label=t("settings_require_2fa_backup"), value=(get_setting("require_2fa_backup", "0") == "1"), on_change=self._toggle_backup_safety, active_color=COLOR_OCEANO)
        
        btn_backup = ft.FilledButton(content=ft.Text(f"💾 {t('settings_export_backup')}", weight=ft.FontWeight.BOLD), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), bgcolor=COLOR_OCEANO, color=COLOR_BLANCO, on_click=self._request_security_for_backup, height=40, width=180)
        btn_restore = ft.OutlinedButton(
            content=ft.Text(f"📂 {t('settings_restore_backup')}", weight=ft.FontWeight.BOLD, color=COLOR_OCEANO), 
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                side=ft.BorderSide(1, COLOR_OCEANO)
            ), 
            on_click=self._request_security_for_restore, 
            height=40,
            width=180
        )

        card_preferences = ft.Container(
            bgcolor=COLOR_BLANCO, padding=20, border_radius=16,
            border=ft.border.all(1, ft.Colors.with_opacity(0.06, COLOR_CIAN)),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=12, color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK), offset=ft.Offset(0, 6)),
            content=ft.Column([
                ft.Text(t("settings_prefs", "Preferencias Básicas"), size=16, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
                self.balance_field,
                self.lang_dropdown, self.currency_dropdown, self.rows_dropdown, fila_ruta,
                self.switch_sobregiro,
                self.switch_ajuste_quincena,
                ft.Container(height=4),
                save_button
            ], spacing=12)
        )

        card_security = ft.Container(
            bgcolor=COLOR_BLANCO, padding=20, border_radius=16,
            border=ft.border.all(1, ft.Colors.with_opacity(0.06, COLOR_CIAN)),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=12, color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK), offset=ft.Offset(0, 6)),
            content=ft.Column([
                ft.Text(t("settings_security_section", "Seguridad de Acceso"), size=16, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
                self.switch_seguridad,
                ft.Row([self.btn_change_pin, self.btn_setup_totp], spacing=5),
            ], spacing=10)
        )

        card_backup = ft.Container(
            bgcolor=COLOR_BLANCO, padding=20, border_radius=16,
            border=ft.border.all(1, ft.Colors.with_opacity(0.06, COLOR_CIAN)),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=12, color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK), offset=ft.Offset(0, 6)),
            content=ft.Column([
                ft.Text(t("settings_backup_restore", "Respaldos de Información"), size=16, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
                self.switch_2fa_backup,
                ft.Row([btn_backup, btn_restore], spacing=10),
            ], spacing=10)
        )

        left_column = ft.Container(
            width=410,
            content=ft.Column([
                ft.Text(t("settings_general_settings", "Ajustes del Sistema"), size=22, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO),
                card_preferences,
                card_security,
                card_backup,
            ], spacing=15)
        )
        
        btn_agregar = ft.FilledButton(t("settings_add_account"), icon="add_card", bgcolor=COLOR_OCEANO, color=COLOR_BLANCO, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), on_click=lambda _: self._show_add_method_dialog())
        
        right_column = ft.Container(
            expand=True, 
            content=ft.Column([
                ft.Row([ft.Text(t("settings_accounts_cards", "Cuentas y Tarjetas"), size=22, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO), btn_agregar], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), 
                ft.Divider(color=ft.Colors.BLACK12), 
                self._build_methods_list()
            ], spacing=15)
        )
        
        return ft.Column([
            header_main_row,
            ft.Divider(height=10, color=ft.Colors.with_opacity(0.06, COLOR_CIAN)),
            ft.Row([left_column, right_column], vertical_alignment=ft.CrossAxisAlignment.START, spacing=35), 
            ft.Container(height=10),
            self.build_danger_zone()
        ], spacing=25, scroll=ft.ScrollMode.AUTO)

    def build_danger_zone(self):
        return ft.Container(
            bgcolor=ft.Colors.RED_50, padding=20, border_radius=16,
            border=ft.border.all(1, ft.Colors.RED_200),
            content=ft.Column([
                ft.Text(t("settings_danger_zone", "Zona de Peligro Irreversible"), size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_700),
                ft.Text(t("settings_danger_desc", "Al realizar la purga, eliminarás transacciones, deudas, cuentas y configuraciones de forma definitiva."), size=13, color=ft.Colors.GREY_700),
                ft.Container(height=2),
                ft.Row([
                    ft.ElevatedButton(t("settings_delete_all_data"), on_click=self.show_delete_confirmation, style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.RED_600, shape=ft.RoundedRectangleBorder(radius=10))),
                    ft.Text("v.1.0", size=12, color=ft.Colors.GREY_400, weight=ft.FontWeight.W_600, opacity=0.6)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            ], spacing=8)
        )
    def _build_methods_list(self):
        methods = get_payment_methods()
        editable_methods = [m for m in methods if m.get("type") != "cash"]
        if not editable_methods: return ft.Text(t("settings_no_accounts"), color=ft.Colors.GREY_500, italic=True, size=14)
        
        balances_map = {}
        try:
            p_balances = get_balance_by_payment_method()
            for pb in p_balances:
                balances_map[int(pb["id"])] = float(pb.get("balance", 0.0))
        except Exception as ex:
            print(f"[SettingsList] Error leyendo balances: {ex}")

        items_ui = []
        total_methods = len(editable_methods)
        
        for i, m in enumerate(editable_methods):
            m_id = int(m["id"])
            current_bal = balances_map.get(m_id, 0.0)
            is_balance_zero = abs(current_bal) < 0.01
            is_frozen = m.get("status") == "frozen"

            display_name = m["name"]
            card_bgcolor = COLOR_BLANCO
            if is_frozen:
                display_name += t("settings_frozen_badge", default=" ❄️ [Congelada]")
                card_bgcolor = ft.Colors.BLUE_50 

            if is_balance_zero and not is_frozen:
                delete_btn = ft.Container(
                    content=ft.Text("🗑️", size=15, color=ft.Colors.RED_400), 
                    on_click=lambda e, method=m: self._delete_method_dialog(e, method), 
                    padding=6, border_radius=6, ink=True, tooltip=t("historial_delete")
                )
            else:
                delete_btn = ft.Container(
                    content=ft.Text("🗑️", size=15, color=ft.Colors.BLUE_GREY_400 if is_frozen else ft.Colors.RED_300), 
                    on_click=lambda e, method=m, bal=current_bal: self._show_smart_delete_modal(method, bal), 
                    padding=6, border_radius=6, ink=True, tooltip=t("historial_delete"),
                    opacity=0.7 if is_frozen else 0.4
                )

            if is_frozen:
                edit_btn = ft.Container(
                    content=ft.Text("✏️", size=15, color=ft.Colors.GREY_400),
                    on_click=lambda e, method=m: self._show_frozen_warning_modal(method),
                    padding=6, border_radius=6, ink=True, tooltip=t("historial_edit"),
                    opacity=0.4
                )
            else:
                edit_btn = ft.Container(
                    content=ft.Text("✏️", size=15), 
                    on_click=lambda e, method=m: self._edit_method_dialog(e, method), 
                    padding=6, border_radius=6, ink=True, tooltip=t("historial_edit")
                )

            action_buttons = [
                edit_btn,
                delete_btn
            ]
            
            order_buttons = []
            if i > 0:
                if is_frozen:
                    order_buttons.append(ft.Container(content=ft.Text("▲", size=14, color=ft.Colors.GREY_300), padding=5, opacity=0.3))
                else:
                    order_buttons.append(ft.Container(content=ft.Text("▲", size=14, color=COLOR_OCEANO), on_click=lambda e, mid=m["id"]: self._move_method(mid, "up"), padding=5, ink=True))
            if i < total_methods - 1:
                order_buttons.append(ft.Container(content=ft.Text("▼", size=14, color=COLOR_OCEANO), on_click=lambda e, mid=m["id"]: self._move_method(mid, "down"), padding=5, ink=True))
                
            controls = ft.Row(order_buttons + action_buttons, spacing=6)
            
            card = ft.Container(
                bgcolor=card_bgcolor, 
                padding=ft.padding.symmetric(horizontal=18, vertical=12), 
                border_radius=14, 
                border=ft.border.all(1, ft.Colors.with_opacity(0.12, COLOR_CIAN) if is_frozen else ft.Colors.with_opacity(0.06, COLOR_CIAN)), 
                shadow=ft.BoxShadow(spread_radius=0, blur_radius=10, color=ft.Colors.with_opacity(0.02, ft.Colors.BLACK), offset=ft.Offset(0, 4)),
                content=ft.Row([
                    ft.Row([
                        ft.Text(m.get("icon", "GRID"), size=24), 
                        ft.Column([
                            ft.Text(display_name, size=15, weight="bold", color=ft.Colors.BLACK), 
                            ft.Text(t("settings_account_type_credit") if m["type"] == "card" else t("settings_account_type_debit"), size=12, color=COLOR_OCEANO, weight=ft.FontWeight.W_600)
                        ], spacing=1)
                    ], spacing=12), 
                    controls
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )
            items_ui.append(card)
        return ft.Column(controls=items_ui, spacing=10)

    def _show_frozen_warning_modal(self, method_data):
        """Muestra un cuadro de advertencia indicando que la cuenta está bloqueada y congelada."""
        lang = get_setting("language", "es")
        title = t("settings_frozen_edit_title", default="Cuenta Bloqueada")
        msg = t("settings_frozen_edit_msg", default="Esta cuenta está bloqueada. No se puede editar ni realizar movimientos en ella hasta que se descongele, para evitar que se alteren las gráficas, métricas de saldo y errores colaterales.")
        lbl_dismiss = "Volver" if lang == "es" else "Dismiss"
        lbl_unfreeze = "Descongelar Cuenta ☀️" if lang == "es" else "Unfreeze Account ☀️"

        def handle_unfreeze_from_warning(e):
            try:
                freeze_payment_method(method_data["id"])
                self.page.snack_bar = ft.SnackBar(content=ft.Text(t("lbl_freeze_success", default="Estado de cuenta actualizado con éxito.")), bgcolor=ft.Colors.BLUE_700)
                self.page.snack_bar.open = True
            except Exception as ex:
                print(f"Error conmutando congelamiento desde advertencia: {ex}")
            warning_dialog.open = False
            self._refresh_view()

        warning_dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA,
            shape=ft.RoundedRectangleBorder(radius=20),
            title=ft.Text(f"❄️ {title}: {method_data['name']}", weight=ft.FontWeight.BOLD, color=COLOR_OCEANO, size=18),
            content=ft.Container(content=ft.Text(msg, color=ft.Colors.BLACK87, size=14), width=460, padding=5),
            actions=[
                ft.TextButton(content=ft.Text(lbl_unfreeze, color=ft.Colors.BLUE_600, weight=ft.FontWeight.BOLD), on_click=handle_unfreeze_from_warning),
                ft.OutlinedButton(content=ft.Text(lbl_dismiss, color=COLOR_OCEANO, weight=ft.FontWeight.BOLD), on_click=lambda _: setattr(warning_dialog, "open", False) or self.page.update(), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), side=ft.BorderSide(1, COLOR_OCEANO)))
            ],
            border_radius=20,
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        )
        self.page.overlay.append(warning_dialog)
        warning_dialog.open = True
        self.page.update()

    def _show_smart_delete_modal(self, method_data, balance):
        """Despliega el modal interactivo conmutando dinámicamente entre congelar/descongelar y vaciado."""
        lang = get_setting("language", "es")
        is_frozen = method_data.get("status") == "frozen"
        is_card = method_data["type"] == "card"

        if lang == "es":
            lbl_freeze_card = "Descongelar Tarjeta ☀️" if is_frozen else "Congelar Tarjeta ❄️"
            lbl_freeze_acc = "Descongelar Cuenta ☀️" if is_frozen else "Congelar Cuenta ❄️"
            lbl_dismiss = "Volver"
            lbl_go_debt = "Ir a Liquidar Deuda 🔍"
            lbl_empty_archive = "Vaciar y Archivar ⚡"
            
            title_credit = f"Gestión de Tarjeta: {method_data['name']}"
            msg_credit = f"Esta tarjeta se encuentra congelada." if is_frozen else f"Esta tarjeta tiene un saldo deudor pendiente de ${abs(balance):,.2f}. Para poder archivarla de forma segura, primero debes saldar la cuenta en deudas."
            
            title_debit = f"Gestión de Cuenta: {method_data['name']}"
            msg_debit = f"Esta cuenta de débito se encuentra congelada." if is_frozen else f"Esta cuenta posee un capital activo de ${balance:,.2f}. Para archivarla sin romper tus métricas históricas, debes transferir y vaciar el saldo."
        else:
            lbl_freeze_card = "Unfreeze Card ☀️" if is_frozen else "Freeze Card ❄️"
            lbl_freeze_acc = "Unfreeze Account ☀️" if is_frozen else "Freeze Account ❄️"
            lbl_dismiss = "Dismiss"
            lbl_go_debt = "Go to Clear Debt 🔍"
            lbl_empty_archive = "Empty & Archive ⚡"
            
            title_credit = f"Card Management: {method_data['name']}"
            msg_credit = f"This credit card is currently frozen." if is_frozen else f"This card has a pending debt of ${abs(balance):,.2f}. To safely archive it, you must settle the account parameters in debts view."
            
            title_debit = f"Account Management: {method_data['name']}"
            msg_debit = f"This bank account is currently frozen." if is_frozen else f"This account currently holds ${balance:,.2f}. To archive it without losing your historical metrics, the funds must be evacuated."

        def handle_freeze(e):
            try:
                freeze_payment_method(method_data["id"])
                self.page.snack_bar = ft.SnackBar(content=ft.Text(t("lbl_freeze_success", default="Estado de cuenta actualizado con éxito.")), bgcolor=ft.Colors.BLUE_700)
                self.page.snack_bar.open = True
            except Exception as ex:
                print(f"Error conmutando congelamiento: {ex}")
            smart_dialog.open = False
            self._refresh_view()

        def handle_empty_archive(e):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT
                        (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE payment_method_id = ? AND type = 'income' AND is_recurrence_active != 1 AND category_id != (SELECT id FROM categories WHERE name = 'Pago de tarjetas' LIMIT 1)) as total_income,
                        (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE payment_method_id = ? AND type = 'expense' AND is_recurrence_active != 1) as total_expense,
                        (SELECT COALESCE(SUM(amount), 0) FROM transfers WHERE destination_method_id = ?) as transfers_in,
                        (SELECT COALESCE(SUM(amount), 0) FROM transfers WHERE source_method_id = ?) as transfers_out
                """, (method_data["id"], method_data["id"], method_data["id"], method_data["id"]))
                row = cursor.fetchone()
                real_balance = float(row["total_income"]) - float(row["total_expense"]) + float(row["transfers_in"]) - float(row["transfers_out"])
                
                if real_balance > 0.01:
                    cursor.execute("SELECT id FROM payment_methods WHERE type = 'cash' LIMIT 1")
                    cash_row = cursor.fetchone()
                    cash_id = cash_row["id"] if cash_row else 1
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    
                    desc_evac = t("evacuacion_fondos_auto", default="Evacuación de fondos automática por cierre de cuenta")
                    cursor.execute("""
                        INSERT INTO transfers (source_method_id, destination_method_id, amount, date, description)
                        VALUES (?, ?, ?, ?, ?)
                    """, (method_data["id"], cash_id, real_balance, today_str, desc_evac))
                
                timestamp = datetime.now().strftime("%d%m%Y")
                new_name = f"{method_data['name']} [Archived_{timestamp}]"
                cursor.execute("UPDATE payment_methods SET status = 'archived', name = ? WHERE id = ?", (new_name, method_data["id"]))
                conn.commit()
                conn.close()
                
                self.page.snack_bar = ft.SnackBar(content=ft.Text("Fondos evacuados a efectivo y cuenta archivada." if lang == "es" else "Funds evacuated to cash and account archived."), bgcolor=ft.Colors.GREEN_700)
                self.page.snack_bar.open = True
            except Exception as ex:
                print(f"Error procesando soft delete: {ex}")
            smart_dialog.open = False
            self._refresh_view()

        def handle_go_debt(e):
            smart_dialog.open = False
            self.page.update()
            try:
                from components.three_panel_layout import ThreePanelLayout
                from views.deudas_view import create_deudas_view
                
                nuevo_layout = ThreePanelLayout(self.page)
                nuevo_layout.current_menu_item = "Deudas" if lang == "es" else "Debts"
                nuevo_layout._rebuild_sidebar()
                nuevo_layout.tab_body_container.content = create_deudas_view(self.page)
                
                self.page.controls.clear()
                self.page.add(nuevo_layout.get_layout())
                self.page.update()
            except Exception:
                pass

        title_txt = title_credit if is_card else title_debit
        msg_txt = msg_credit if is_card else msg_debit
        
        btn_freeze = ft.TextButton(content=ft.Text(lbl_freeze_card if is_card else lbl_freeze_acc, color=ft.Colors.BLUE_600 if is_frozen else ft.Colors.BLUE_400, weight=ft.FontWeight.BOLD), on_click=handle_freeze)
        btn_dismiss = ft.OutlinedButton(content=ft.Text(lbl_dismiss, color=COLOR_OCEANO, weight=ft.FontWeight.BOLD), on_click=lambda _: setattr(smart_dialog, "open", False) or self.page.update(), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), side=ft.BorderSide(1, COLOR_OCEANO)))
        
        if is_frozen:
            btn_action = ft.Container()
        else:
            if is_card:
                btn_action = ft.FilledButton(content=ft.Text(lbl_go_debt, color=COLOR_BLANCO, weight=ft.FontWeight.BOLD), bgcolor=COLOR_OCEANO, on_click=handle_go_debt, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)))
            else:
                btn_action = ft.FilledButton(content=ft.Text(lbl_empty_archive, color=COLOR_BLANCO, weight=ft.FontWeight.BOLD), bgcolor=COLOR_OCEANO, on_click=handle_empty_archive, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)))

        smart_dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA,
            shape=ft.RoundedRectangleBorder(radius=20),
            title=ft.Text(title_txt, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO, size=18),
            content=ft.Container(content=ft.Text(msg_txt, color=ft.Colors.BLACK87, size=14), width=460, padding=5),
            actions=[
                btn_freeze,
                ft.Row([btn_dismiss, btn_action], spacing=10, tight=True)
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        )
        
        self.page.overlay.append(smart_dialog)
        smart_dialog.open = True
        self.page.update()

    def _on_tipo_radio_change(self, e):
        es_credito = (self.tipo_radio.value == "card")
        es_edicion = self.current_edit_id is not None
        self.seccion_credito.visible = es_credito
        self.saldo_inicial_input.visible = not es_credito and not es_edicion
        self.page.update()

    def _get_dynamic_bank_options(self):
        default_banks = ["BBVA", "Santander", "Banorte", "Citibanamex", "HSBC", "Nu", "Stori", "RappiCard", "Genérica"]
        existing_methods = get_payment_methods()
        custom_banks = set()
        for m in existing_methods:
            if m["type"] != "cash":
                name = m["name"]
                if " - *" in name: 
                    custom_banks.add(name.split(" - *")[0].strip())
                elif " - " in name: 
                    custom_banks.add(name.split(" - ")[0].strip())
        all_banks = sorted(list(set(default_banks) | custom_banks))
        return [ft.dropdown.Option(b) for b in all_banks]

    def _show_add_method_dialog(self):
        self.current_edit_id = None
        self.add_dialog.title.value = t("settings_add_new_account")
        self.banco_dropdown.options = self._get_dynamic_bank_options()
        self.tipo_radio.value = "card"
        self.tipo_radio.disabled = False # Permitir selección libre al crear un registro nuevo
        opciones = [o.key for o in self.banco_dropdown.options]
        self.banco_dropdown.value = opciones[0] if opciones else "BBVA"
        self.banco_custom.value = ""; self.terminacion.value = ""; self.alias_input.value = ""
        self.limite_input.value = ""; self.corte_input.value = ""; self.pago_input.value = ""; self.saldo_inicial_input.value = ""
        self.seccion_credito.visible = True; self.saldo_inicial_input.visible = False
        self.add_dialog.open = True
        self.page.update()

    def _close_add_dialog(self, e=None): 
        self.add_dialog.open = False
        self.page.update()

    def _show_explicit_alert_modal(self, title_text, body_text):
        """Helper formal de UI para inyectar un modal de alerta premium e interactivo."""
        lang = get_setting("language", "es")
        lbl_ok = "Entendido" if lang == "es" else "Got it"
        
        alert_dialog = ft.AlertDialog(
            bgcolor=COLOR_CREMA,
            shape=ft.RoundedRectangleBorder(radius=20),
            title=ft.Text(title_text, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO, size=18),
            content=ft.Container(content=ft.Text(body_text, color=ft.Colors.BLACK87, size=14), width=440, padding=5),
            actions=[
                ft.FilledButton(lbl_ok, bgcolor=COLOR_OCEANO, color=COLOR_BLANCO, on_click=lambda _: setattr(alert_dialog, "open", False) or self.page.update(), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)))
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        self.page.overlay.append(alert_dialog)
        alert_dialog.open = True
        self.page.update()

    def _save_action(self, e):
        # Regla de Negocio de Entrada: Si es tarjeta de crédito, todos los parámetros financieros son mandatorios
        if self.tipo_radio.value == "card":
            limite_val = self.limite_input.value.strip() if self.limite_input.value else ""
            corte_val = self.corte_input.value.strip() if self.corte_input.value else ""
            pago_val = self.pago_input.value.strip() if self.pago_input.value else ""
            
            if not limite_val or not corte_val or not pago_val:
                title_err = t("settings_card_validation_title", default="Detalles Faltantes ⚠️")
                msg_err = t("settings_card_validation_error", default="Para registrar una tarjeta de crédito debes completar obligatoriamente todos los Detalles de Tarjeta de Crédito (Límite de crédito, Día de corte y Día de pago) con valores válidos.")
                self._show_explicit_alert_modal(title_err, msg_err)
                return

        valor_personalizado = self.banco_custom.value.strip()
        nombre_banco = valor_personalizado if valor_personalizado else self.banco_dropdown.value
        if not nombre_banco:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("settings_please_enter_bank")), bgcolor=ft.Colors.RED_700); self.page.snack_bar.open = True; self.page.update(); return
        
        # AJUSTE: El alias ahora se almacena de forma independiente sin concatenar el banco
        alias_val = self.alias_input.value.strip()
        if alias_val:
            nombre_final = alias_val
        else:
            nombre_final = f"{nombre_banco} - *{self.terminacion.value}" if self.terminacion.value else nombre_banco
            
        icono = "💳" if self.tipo_radio.value == "card" else "🏦"
        try:
            limite = float(self.limite_input.value) if self.limite_input.value and self.tipo_radio.value == "card" else 0
            corte = int(self.corte_input.value) if self.corte_input.value and self.tipo_radio.value == "card" else 1
            pago = int(self.pago_input.value) if self.pago_input.value and self.tipo_radio.value == "card" else 1
        except ValueError: limite, corte, pago = 0, 1, 1
        if self.current_edit_id is not None: 
            update_payment_method(method_id=self.current_edit_id, name=nombre_final, type_=self.tipo_radio.value, icon=icono, credit_limit=limite, cutoff=corte, due=pago)
            mensaje = t("settings_account_updated")
        else:
            method_id = add_payment_method(name=nombre_final, type_=self.tipo_radio.value, icon=icono, credit_limit=limite, cutoff=corte, due=pago)
            if self.tipo_radio.value == "bank_account" and self.saldo_inicial_input.value:
                try:
                    saldo = float(self.saldo_inicial_input.value)
                    if saldo != 0:
                        cat_id = get_initial_balance_category_id()
                        if cat_id: save_transaction(category_id=cat_id, payment_method_id=method_id, amount=abs(saldo), description=f"Saldo inicial: {nombre_final}", type="income" if saldo > 0 else "expense", date=datetime.now().strftime("%Y-%m-%d"))
                except ValueError: pass
            mensaje = t("settings_account_registered")
        self.page.snack_bar = ft.SnackBar(content=ft.Text(mensaje), bgcolor=ft.Colors.GREEN_700); self.page.snack_bar.open = True; self._close_add_dialog(); self._refresh_view()

    def _edit_method_dialog(self, e, method_data):
        self.current_edit_id = method_data["id"]
        self.add_dialog.title.value = t("settings_edit_account")
        self.tipo_radio.value = method_data["type"]
        self.tipo_radio.disabled = True # Bloqueo operativo estricto de cambio de tipo de cuenta
        self.banco_dropdown.options = self._get_dynamic_bank_options()
        raw_name = method_data["name"]
        
        # Catálogo base para distinguir nombres de bancos nativos frente a un Alias puro de usuario
        default_banks = ["BBVA", "Santander", "Banorte", "Citibanamex", "HSBC", "Nu", "Stori", "RappiCard", "Genérica"]
        
        if " - *" in raw_name:
            partes = raw_name.split(" - *")
            banco_str = partes[0]
            self.terminacion.value = partes[1]
            self.alias_input.value = ""
        elif raw_name in default_banks:
            banco_str = raw_name
            self.terminacion.value = ""
            self.alias_input.value = ""
        else:
            # Al no contener separadores técnicos ni ser un banco por defecto, se parsea como Alias puro aislado
            banco_str = "Genérica"
            self.alias_input.value = raw_name
            self.terminacion.value = ""
            
        opciones_banco = [opt.key for opt in self.banco_dropdown.options]
        if banco_str in opciones_banco: self.banco_dropdown.value = banco_str; self.banco_custom.value = ""
        else: self.banco_dropdown.value = opciones_banco[0] if opciones_banco else "BBVA"; self.banco_custom.value = banco_str
        self.limite_input.value = str(method_data.get("credit_limit", "")) if method_data.get("credit_limit") else ""
        self.corte_input.value = str(method_data.get("cutoff_day", "")) if method_data.get("cutoff_day") else ""
        self.pago_input.value = str(method_data.get("payment_due_day", "")) if method_data.get("payment_due_day") else ""
        self.seccion_credito.visible = (self.tipo_radio.value == "card"); self.saldo_inicial_input.visible = False
        self.add_dialog.open = True; self.page.update()

    def _toggle_sobregiro(self, e):
        save_setting("allow_overdraft", "1" if self.switch_sobregiro.value else "0"); self.page.update()

    def _toggle_ajuste_quincena(self, e):
        save_setting("adjust_biweekly_weekend", "1" if self.switch_ajuste_quincena.value else "0"); self.page.update()

    def _move_method(self, method_id, direction):
        from database.connection import reorder_payment_method
        reorder_payment_method(method_id, direction); self._refresh_view()

    def seleccionar_carpeta(self, e):
        root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True); carpeta_seleccionada = filedialog.askdirectory(title=t("settings_select_folder")); root.destroy()
        if carpeta_seleccionada: self.path_input.value = os.path.normpath(carpeta_seleccionada); self.page.update()

    def save_all_settings(self, e):
        new_username = self.username_field.value.strip()
        current_language = get_setting("language", "es")
        
        if not new_username:
            default_name = "Usuario" if current_language == "es" else "User"
            new_username = default_name
            self.username_field.value = default_name 

        save_setting("username", new_username)

        if not self.balance_field.disabled:
            raw_val = str(self.balance_field.value).replace("$", "").replace(",", "").strip()
            try:
                if raw_val: set_initial_balance(float(raw_val))
            except ValueError: pass

        new_language = self.lang_dropdown.value
        language_changed = current_language != new_language
        save_setting("language", new_language)
        save_setting("currency", self.currency_dropdown.value)
        
        save_setting("table_rows_per_page", self.rows_dropdown.value)
        
        nueva_ruta = self.path_input.value.strip()
        if nueva_ruta and not os.path.exists(nueva_ruta): 
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("settings_csv_path_error")), bgcolor=ft.Colors.RED_700)
            self.page.snack_bar.open = True
            self.page.update()
            return 
        else: 
            save_setting("export_path", nueva_ruta)

        if language_changed:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("settings_restart_required")), bgcolor=ft.Colors.GREEN_700)
            self.page.snack_bar.open = True
            
            self.page.controls.clear()
            
            from components.three_panel_layout import ThreePanelLayout
            
            nuevo_layout = ThreePanelLayout(self.page)
            nuevo_layout.current_menu_item = "Configuración"
            nuevo_layout._rebuild_sidebar()  
            nuevo_layout.tab_body_container.content = self.get_view()
            
            self.page.add(nuevo_layout.get_layout())
            self.page.update()
        else: 
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("settings_success")), bgcolor=ft.Colors.GREEN_700)
            self.page.snack_bar.open = True
            self._refresh_view()

    def _close_delete_dialog(self, e=None): self.delete_dialog.open = False; self.page.update()
    def _confirm_delete(self, e): self._close_delete_dialog(); hard_reset_database(); self.page.snack_bar = ft.SnackBar(content=ft.Text(t("settings_database_reset")), bgcolor=ft.Colors.GREEN_700); self.page.snack_bar.open = True; self._refresh_view()
    def show_delete_confirmation(self, e): self.delete_dialog.open = True; self.page.update()
    def _delete_method_dialog(self, e, method_data): self.account_id_to_delete = method_data["id"]; self.delete_acc_dialog.open = True; self.page.update()
    def _close_delete_acc_dialog(self, e=None): self.delete_acc_dialog.open = False; self.page.update()
    
    def _confirm_delete_account(self, e):
        if self.account_id_to_delete is not None:
            methods = get_payment_methods()
            credit_cards = [m for m in methods if m["type"] == "card"]
            target_method = next((m for m in methods if m["id"] == self.account_id_to_delete), None)
            
            # Bloqueo formal mediante AlertDialog en lugar de SnackBar silencioso
            if target_method and target_method["type"] == "card" and len(credit_cards) <= 1:
                title_err = t("settings_last_card_title", default="Acción Restringida ⚠️")
                msg_err = t("settings_last_card_error_modal", default="No es posible eliminar esta tarjeta. La aplicación requiere que mantengas al menos una tarjeta de crédito activa (aunque sea genérica) para la correcta consistencia de las proyecciones de deudas y métricas históricas.")
                self._close_delete_acc_dialog()
                self._show_explicit_alert_modal(title_err, msg_err)
                return
            
            delete_payment_method(self.account_id_to_delete)
            self.page.snack_bar = ft.SnackBar(content=ft.Text(t("settings_account_deleted")), bgcolor=ft.Colors.RED_700)
            self.page.snack_bar.open = True
        self._close_delete_acc_dialog()
        self._refresh_view()

    def _refresh_view(self): 
        self.main_column = self.build_content()
        self.main_container.content.content = self.main_column
        self.page.update()

    def get_view(self): return self.main_container

def create_settings_view(page: ft.Page): 
    return SettingsView(page).get_view()