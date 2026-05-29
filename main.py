import flet as ft
import os
import sys
import ctypes

# Solución de UI/UX: Fuerza a Windows a desvincular el proceso de Flet y mostrar tu propio logo en la barra de tareas
if sys.platform == "win32":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("pesoapeso.gestor.app.1.0")
    except:
        pass

# Resolución global de la ruta de assets compatible de forma nativa con VS Code y el desempaque de PyInstaller
if hasattr(sys, '_MEIPASS'):
    ruta_assets = os.path.join(sys._MEIPASS, "assets")
else:
    ruta_assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.colors import COLOR_BLANCO, GRADIENTE_FONDO_SUAVE
from components.three_panel_layout import create_three_panel_layout
from database.connection import (get_setting, save_setting, process_recurring_transactions, init_database)
from views.auth_view import create_auth_view


def main(page: ft.Page) -> None:
    page.title = "Peso a Peso - Gestor de Gastos"
    
    # Inyección formal del Icono de Ventana y Barra de Tareas (Prioriza .ico para romper la caché de Windows)
    path_ico = os.path.abspath(os.path.join(ruta_assets, "logo.ico"))
    path_png = os.path.abspath(os.path.join(ruta_assets, "logo.png"))
    
    if os.path.exists(path_ico):
        page.window.icon = path_ico
    elif os.path.exists(path_png):
        page.window.icon = path_png
        
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = COLOR_BLANCO
    page.window_width = 1400
    page.window_height = 1000
    page.padding = 0
    page.spacing = 0
    page.window.min_width = 1200
    page.window.min_height = 750
    page.window_resizable = True

    def handle_window_event(e):
        if e.data == "close":
            os._exit(0)            
            
    page.on_window_event = handle_window_event

    try:
        init_database()
        print("[Arranque] Base de datos verificada e inicializada con éxito.")

    except Exception as db_err:
        print(f"[Arranque Crítico] Error al levantar el archivo de persistencia: {db_err}")
        page.add(ft.SafeArea(ft.Text(f"Error crítico de inicialización: {db_err}", color=ft.Colors.RED_700)))
        page.update()
        return

    try:
        process_recurring_transactions()
        print("[Arranque] Motor de Eslabones Encadenados procesado de forma idempotente.")
    except Exception as rec_err:
        print(f"[Arranque Error] Error en procesamiento preventivo de recurrencias: {rec_err}")

    def load_main_app():
        page.controls.clear()
        
        main_wrapper = ft.Container(
            content=create_three_panel_layout(page),
            gradient=GRADIENTE_FONDO_SUAVE,
            expand=True,
            margin=0,
            padding=0
        )
        
        page.add(main_wrapper)
        
        if os.path.exists(path_ico):
            page.window.icon = path_ico
            
        page.update()

    security_enabled = get_setting("security_enabled", "0") == "1"
    
    if security_enabled:
        page.add(create_auth_view(page, on_success=load_main_app))
    else:
        load_main_app()


if __name__ == "__main__":
    ft.run(main, assets_dir=ruta_assets)