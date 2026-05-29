"""
Vista de Autenticación y Bloqueo de la aplicación.
Protege el acceso mediante NIP o recuperación con Google Authenticator (TOTP).
Corregido: Visibilidad estricta de subtextos y traducción completa de componentes.
"""
import flet as ft
import hashlib
import pyotp
from core.colors import COLOR_CREMA, COLOR_OCEANO, COLOR_ATARDECER, COLOR_BLANCO, COLOR_CIAN, GRADIENTE_FONDO_SUAVE, GRADIENTE_DESTACADO
from database.connection import get_setting, save_setting
from core.translations import t

class AuthView:
    def __init__(self, page: ft.Page, on_success):
        self.page = page
        self.on_success = on_success
        self.is_recovery_mode = False

        # 1. Título e Instrucción Inicial (Traducidos correctamente)
        self.title_text = ft.Text(t("auth_locked_title", "App Bloqueada"), size=26, weight=ft.FontWeight.BOLD, color=COLOR_OCEANO)
        
        self.instruction_text = ft.Text(
            value="", 
            size=13, 
            color=ft.Colors.GREY_600, 
            text_align=ft.TextAlign.CENTER, 
            width=320, 
            visible=False  # Estrictamente oculto en la pantalla del NIP
        )
        self.lock_icon = ft.Text("🔒", size=70)

        # 2. Campo de Entrada de NIP
        self.pin_input = ft.TextField(
            label=t("auth_enter_pin", "Ingresa tu NIP"),
            password=True,
            can_reveal_password=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            text_align=ft.TextAlign.CENTER,
            width=320,
            height=50,
            content_padding=12,
            color=ft.Colors.BLACK,
            border_color=ft.Colors.with_opacity(0.15, COLOR_OCEANO),
            focused_border_color=COLOR_OCEANO,
            label_style=ft.TextStyle(color=ft.Colors.GREY_600, size=14),
            on_submit=self._verify
        )
        
        self.error_text = ft.Text("", color=ft.Colors.RED_500, size=13, weight=ft.FontWeight.W_600, visible=False)

        # 3. Botones Secundarios Traducidos
        self.has_totp = bool(get_setting("totp_secret", ""))
        self.forgot_btn = ft.TextButton(
            content=ft.Row([
                ft.Text("🔑", size=14), 
                ft.Text(t("auth_forgot_pin", "¿Olvidaste tu NIP?"), color=COLOR_OCEANO, weight=ft.FontWeight.W_600, size=14)
            ], tight=True),
            on_click=self._toggle_recovery,
            visible=self.has_totp 
        )

        self.back_to_pin_btn = ft.TextButton(
            content=ft.Row([
                ft.Text("⬅️", size=14),
                ft.Text(t("auth_back_to_pin", "Volver al NIP"), color=COLOR_OCEANO, weight=ft.FontWeight.W_600, size=14)
            ], tight=True),
            on_click=self._toggle_pin_mode,
            visible=False
        )

        # 4. Botón de Acción Principal Traducido con Gradiente
        active_shadow = ft.BoxShadow(
            spread_radius=1,
            blur_radius=12,
            color=ft.Colors.with_opacity(0.25, COLOR_ATARDECER),
            offset=ft.Offset(0, 4)
        )
        
        self.unlock_button_text = ft.Text(t("auth_unlock_button", "Desbloquear"), color=COLOR_OCEANO, weight=ft.FontWeight.BOLD, size=15)
        
        self.unlock_button = ft.Container(
            content=ft.Container(
                content=self.unlock_button_text,
                alignment=ft.Alignment(0, 0),
            ),
            width=320,
            height=46,
            border_radius=23, 
            gradient=GRADIENTE_DESTACADO,
            shadow=active_shadow,
            ink=True,
            on_click=self._verify
        )

    def _toggle_recovery(self, e):
        """Cambia la interfaz al modo de autenticación por Google Authenticator."""
        self.is_recovery_mode = True
        self.title_text.value = t("auth_recovery_title", "Recuperación de Acceso")
        self.lock_icon.value = "📱"
        
        # Seteamos e inyectamos el subtexto explicativo traducido
        self.instruction_text.value = t("auth_recovery_instruction", "Por favor, ingresa el código de 6 dígitos generado por tu aplicación Google Authenticator o similar.")
        self.instruction_text.visible = True
        
        # Ajustes de idioma del Input y botón principal
        self.pin_input.label = t("auth_recovery_label", "Código de Verificación")
        self.unlock_button_text.value = t("auth_unlock_button", "Desbloquear")
        
        self.pin_input.password = False
        self.pin_input.max_length = 6
        self.pin_input.value = ""
        self.error_text.visible = False
        
        # Intercambio de botones
        self.forgot_btn.visible = False
        self.back_to_pin_btn.visible = True
        self.page.update()

    def _toggle_pin_mode(self, e):
        """Regresa de forma segura a la interfaz clásica de desbloqueo por NIP."""
        self.is_recovery_mode = False
        self.title_text.value = t("auth_locked_title", "App Bloqueada")
        self.lock_icon.value = "🔒"
        
        # Ocultamos por completo y limpiamos el subtexto del Authenticator
        self.instruction_text.value = ""
        self.instruction_text.visible = False
        
        # Re-traducimos el input y botón principal al estado NIP
        self.pin_input.label = t("auth_enter_pin", "Ingresa tu NIP")
        self.unlock_button_text.value = t("auth_unlock_button", "Desbloquear")
        
        self.pin_input.password = True
        self.pin_input.max_length = None  
        self.pin_input.value = ""
        self.error_text.visible = False
        
        # Intercambio de botones
        self.forgot_btn.visible = self.has_totp
        self.back_to_pin_btn.visible = False
        self.page.update()

    def _verify(self, e):
        input_val = self.pin_input.value.strip().replace(" ", "").replace("-", "")
        if not input_val: return

        if self.is_recovery_mode:
            secret = get_setting("totp_secret", "")
            totp = pyotp.TOTP(secret, interval=30, digits=6)
            
            if totp.verify(input_val):
                self.on_success()
            else:
                self.error_text.value = t("auth_invalid_totp", "Código inválido. Revisa tu App.")
                self.error_text.visible = True
                self.page.update()
        else:
            input_hash = hashlib.sha256(input_val.encode()).hexdigest()
            if input_hash == get_setting("app_pin_hash"):
                self.on_success()
            else:
                self.error_text.value = t("auth_wrong_pin", "NIP Incorrecto.")
                self.error_text.visible = True
                self.pin_input.value = ""
                self.page.update()

    def get_view(self):
        """Construye la vista de bloqueo envuelta en una tarjeta flotante y fondo en gradiente."""
        auth_card = ft.Container(
            bgcolor=COLOR_BLANCO,
            padding=ft.padding.symmetric(vertical=40, horizontal=35),
            border_radius=24,
            border=ft.border.all(1, ft.Colors.with_opacity(0.05, COLOR_CIAN)),
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=30, color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK), offset=ft.Offset(0, 15)),
            width=400,
            content=ft.Column([
                self.lock_icon,
                self.title_text,
                self.instruction_text,  # Insertado de forma dinámica
                ft.Container(height=10 if self.is_recovery_mode else 0), # Ajuste de espacio inteligente
                self.pin_input,
                self.error_text,
                ft.Container(height=15),
                self.unlock_button,
                ft.Container(height=5),
                self.forgot_btn,
                self.back_to_pin_btn  
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
        )

        return ft.Container(
            expand=True,
            gradient=GRADIENTE_FONDO_SUAVE,
            alignment=ft.Alignment(0, 0),
            content=auth_card
        )

def create_auth_view(page: ft.Page, on_success) -> ft.Container: 
    return AuthView(page, on_success).get_view()