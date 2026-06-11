import sqlite3
import os
import sys
import shutil
import uuid
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import flet as ft

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(BASE_DIR, "finance_tracker.db")

def get_connection() -> sqlite3.Connection:
    """
    Obtiene una conexión a la base de datos SQLite de forma segura en la ruta de ejecución real.
    
    Returns:
        sqlite3.Connection: Objeto de conexión a la base de datos.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row 
    return conn

def _ensure_custom_column() -> None:
    """Garantiza que exista la columna is_custom en la tabla categories sin romper bases de datos existentes."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE categories ADD COLUMN is_custom BOOLEAN DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass # La columna ya existe
    finally:
        conn.close()

def _ensure_status_column() -> None:
    """Garantiza que exista la columna status en la tabla payment_methods para gestionar borrado suave y congelamiento."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE payment_methods ADD COLUMN status TEXT DEFAULT 'active'")
        conn.commit()
    except sqlite3.OperationalError:
        pass # La columna ya existe
    finally:
        conn.close()

def _ensure_debt_tables_and_columns() -> None:
    """Prepara el esquema de base de datos para manejar deudas y abonos sin romper datos existentes."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Añadir columnas a payment_methods para Tarjetas de Crédito
    try:
        cursor.execute("ALTER TABLE payment_methods ADD COLUMN credit_limit REAL DEFAULT 0")
        cursor.execute("ALTER TABLE payment_methods ADD COLUMN cutoff_day INTEGER DEFAULT 1")
        cursor.execute("ALTER TABLE payment_methods ADD COLUMN payment_due_day INTEGER DEFAULT 1")
        conn.commit()
    except sqlite3.OperationalError:
        pass # Las columnas ya existen
        
    # 2. Crear tabla de Préstamos (Deudas a plazos como hipotecas, auto, personales)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            total_amount REAL NOT NULL CHECK(total_amount > 0),
            interest_rate REAL DEFAULT 0,
            term_months INTEGER DEFAULT 1,
            term_unit TEXT DEFAULT 'Meses',
            start_date DATE NOT NULL,
            icon TEXT,
            color TEXT,
            card_id INTEGER,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 3. Migración Segura: Agrega la columna term_unit si no existe en bases viejas
    try:
        cursor.execute("ALTER TABLE loans ADD COLUMN term_unit TEXT DEFAULT 'Meses'")
        conn.commit()
    except sqlite3.OperationalError:
        pass # La columna ya existe

    # Parche preventivo dinámico: Agrega la columna relacional card_id a la tabla loans si no existía
    try:
        cursor.execute("ALTER TABLE loans ADD COLUMN card_id INTEGER")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Parche preventivo dinámico: Agrega la columna status a la tabla loans para soportar borrado suave
    try:
        cursor.execute("ALTER TABLE loans ADD COLUMN status TEXT DEFAULT 'active'")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    
    # 4. Crear tabla de Transferencias/Abonos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_method_id INTEGER NOT NULL,
            destination_method_id INTEGER,
            destination_loan_id INTEGER,
            amount REAL NOT NULL CHECK(amount > 0),
            date DATE NOT NULL,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_method_id) REFERENCES payment_methods (id),
            FOREIGN KEY (destination_method_id) REFERENCES payment_methods (id),
            FOREIGN KEY (destination_loan_id) REFERENCES loans (id)
        )
    """)
    
    conn.commit()
    conn.close()

def _ensure_template_columns() -> None:
    """Garantiza que existan las columnas type y category_id en custom_templates sin romper datos existentes."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE custom_templates ADD COLUMN type TEXT DEFAULT 'expense'")
        cursor.execute("ALTER TABLE custom_templates ADD COLUMN category_id INTEGER")
        conn.commit()
    except sqlite3.OperationalError:
        pass # Las columnas ya existen
    finally:
        conn.close()

def _ensure_recurrence_columns() -> None:
    """Garantiza la existencia y migración de columnas para el Mapeo de Eslabones Encadenados."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE transactions ADD COLUMN recurrence_type TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE transactions ADD COLUMN is_recurrence_active INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE transactions ADD COLUMN last_applied_date DATE")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE transactions ADD COLUMN recurrence_chain_id TEXT")
    except sqlite3.OperationalError:
        pass
    
    conn.commit()
    conn.close()

def init_database() -> None:
    """
    Inicializa la base de datos creando las tablas necesarias.
    Se ejecuta automáticamente al importar el módulo.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Tabla de Métodos de Pago
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('cash', 'card', 'bank_account')),
            is_default BOOLEAN NOT NULL DEFAULT 0,
            icon TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # PARCHE DE SEGURIDAD PREVENTIVO: Garantiza la existencia de columnas críticas antes de insertar datos por defecto
    cursor.execute("PRAGMA table_info(payment_methods)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "credit_limit" not in columns:
        cursor.execute("ALTER TABLE payment_methods ADD COLUMN credit_limit REAL DEFAULT 0.0")
    if "cutoff_day" not in columns:
        cursor.execute("ALTER TABLE payment_methods ADD COLUMN cutoff_day INTEGER DEFAULT 1")
    if "payment_due_day" not in columns:
        cursor.execute("ALTER TABLE payment_methods ADD COLUMN payment_due_day INTEGER DEFAULT 28")
    if "status" not in columns:
        cursor.execute("ALTER TABLE payment_methods ADD COLUMN status TEXT DEFAULT 'active'")
    if "order_index" not in columns:
        cursor.execute("ALTER TABLE payment_methods ADD COLUMN order_index INTEGER DEFAULT 0")
    
    # 2. Tabla de categorías
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
            category_group TEXT NOT NULL,
            is_recurring BOOLEAN NOT NULL DEFAULT 0,
            icon TEXT,
            color TEXT,
            is_favorite BOOLEAN NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 3. Tabla de transacciones
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            payment_method_id INTEGER NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            description TEXT,
            type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
            date DATE NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE,
            FOREIGN KEY (payment_method_id) REFERENCES payment_methods (id) ON DELETE RESTRICT
        )
    """)

    # 4. Tabla de Ajustes (Configuración)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT
        )
    """)

    # 5. Tabla de Plantillas Personalizadas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            icon TEXT NOT NULL,
            default_amount REAL NOT NULL,
            color TEXT NOT NULL,
            type TEXT DEFAULT 'expense',
            category_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE
        )
    """)
    
    # Índices para optimizar consultas
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_payment ON transactions(payment_method_id)")
    
    conn.commit()
    
    # Insertar datos por defecto si la base de datos está vacía
    _insert_default_payment_methods(cursor)
    _insert_default_categories(cursor)
    
    conn.commit()
    conn.close() 

    # Módulos seguros de migración e inyección (Cada uno maneja su propia conexión interna)
    _ensure_recurrence_columns()
    _ensure_custom_column()
    _ensure_status_column()
    _ensure_debt_tables_and_columns()
    _ensure_template_columns()

def _insert_default_payment_methods(cursor: sqlite3.Cursor) -> None:
    """Inserta los métodos de pago básicos (Efectivo y Tarjeta) con sus parámetros de corte de fábrica."""
    cursor.execute("SELECT COUNT(*) as count FROM payment_methods")
    if cursor.fetchone()[0] > 0:
        return
    
    cursor.execute("""
        INSERT INTO payment_methods (name, type, is_default, icon, credit_limit, cutoff_day, payment_due_day, status)
        VALUES ('Efectivo', 'cash', 1, '💵', 0, 1, 1, 'active')
    """)
    cursor.execute("""
        INSERT INTO payment_methods (name, type, is_default, icon, credit_limit, cutoff_day, payment_due_day, status)
        VALUES ('Tarjeta', 'card', 0, '💳', 0, 1, 28, 'active')
    """)

def _insert_default_categories(cursor: sqlite3.Cursor) -> None:
    """Inserta categorías por defecto en la base de datos con la estructura de grupos."""
    cursor.execute("SELECT COUNT(*) as count FROM categories")
    if cursor.fetchone()[0] > 0:
        return
    
    expense_categories = [
        ("Renta", "expense", "Gastos Fijos", 1, "🏠", "#9B59B6"),
        ("Crédito hipotecario", "expense", "Gastos Fijos", 1, "🏠", "#2980B9"),
        ("Agua", "expense", "Gastos Fijos", 1, "💧", "#3498DB"),
        ("Luz", "expense", "Gastos Fijos", 1, "⚡", "#F39C12"),
        ("Gas", "expense", "Gastos Fijos", 1, "🔥", "#E74C3C"),
        ("Internet", "expense", "Gastos Fijos", 1, "📶", "#2ECC71"),
        ("Teléfono", "expense", "Gastos Fijos", 1, "📱", "#9B59B6"),
        ("Pago de tarjetas", "expense", "Gastos Fijos", 1, "💳", "#C0392B"),
        ("Préstamo personal", "expense", "Gastos Fijos", 1, "🏦", "#8E44AD"),
        ("Netflix", "expense", "Gastos Fijos", 1, "🎬", "#E50914"),
        ("Spotify", "expense", "Gastos Fijos", 1, "🎵", "#1DB954"),
        ("Amazon Prime", "expense", "Gastos Fijos", 1, "📦", "#FF9900"),
        ("Disney+", "expense", "Gastos Fijos", 1, "🏰", "#113CCF"),
        ("HBO Max", "expense", "Gastos Fijos", 1, "📺", "#8B5CF6"),
        ("Youtube Premium", "expense", "Gastos Fijos", 1, "▶️", "#FF0000"),
        ("Otras suscripciones", "expense", "Gastos Fijos", 1, "📱", "#9B59B6"),
        ("Gimnasio", "expense", "Gastos Fijos", 1, "💪", "#E74C3C"),
        
        ("Despensa", "expense", "Gastos Operativos", 0, "🛒", "#E74C3C"),
        ("Comida", "expense", "Gastos Operativos", 0, "🍔", "#FF6B6B"),
        ("Transporte público", "expense", "Gastos Operativos", 0, "🚌", "#4ECDC4"),
        ("Gasolina", "expense", "Gastos Operativos", 0, "⛽", "#E74C3C"),
        ("Salud", "expense", "Gastos Operativos", 0, "🏥", "#2ECC71"),
        ("Medicamentos", "expense", "Gastos Operativos", 0, "💊", "#27AE60"),
        ("Doctor", "expense", "Gastos Operativos", 0, "👨‍⚕️", "#1ABC9C"),
        ("Mascotas", "expense", "Gastos Operativos", 0, "🐕", "#F39C12"),
        ("Comida mascotas", "expense", "Gastos Operativos", 0, "🦴", "#95A5A6"),
        
        ("Restaurantes", "expense", "Gastos Hormiga", 0, "🍽️", "#F39C12"),
        ("Delivery", "expense", "Gastos Hormiga", 0, "🛵", "#E67E22"),
        ("Uber/Taxi", "expense", "Gastos Hormiga", 0, "🚕", "#F39C12"),
        ("Estacionamiento", "expense", "Gastos Hormiga", 0, "🅿️", "#95A5A6"),
        ("Antojos", "expense", "Gastos Hormiga", 0, "🍫", "#FF9800"),
        ("Café", "expense", "Gastos Hormiga", 0, "☕", "#6D4C41"),
        ("Snacks", "expense", "Gastos Hormiga", 0, "🍿", "#FF5722"),
        
        ("Mantenimiento", "expense", "Gastos Periódicos", 0, "🔧", "#95A5A6"),
        ("Reparaciones", "expense", "Gastos Periódicos", 0, "🛠️", "#7F8C8D"),
        ("Mantenimiento auto", "expense", "Gastos Periódicos", 0, "🔧", "#7F8C8D"),
        ("Educación", "expense", "Gastos Periódicos", 0, "📚", "#3498DB"),
        ("Libros", "expense", "Gastos Periódicos", 0, "📖", "#2ECC71"),
        ("Cursos", "expense", "Gastos Periódicos", 0, "🎓", "#9B59B6"),
        ("Ropa", "expense", "Gastos Periódicos", 0, "👕", "#E91E63"),
        ("Calzado", "expense", "Gastos Periódicos", 0, "👟", "#9C27B0"),
        ("Cuidado personal", "expense", "Gastos Periódicos", 0, "💅", "#FF5722"),
        ("Peluquería", "expense", "Gastos Periódicos", 0, "💇", "#795548"),
        ("Veterinario", "expense", "Gastos Periódicos", 0, "🏥", "#E74C3C"),
        
        ("Regalos", "expense", "Otros Gastos", 0, "🎁", "#E91E63"),
        ("Donaciones", "expense", "Otros Gastos", 0, "❤️", "#F44336"),
        ("Otros gastos", "expense", "Otros Gastos", 0, "📦", "#95A5A6"),
    ]
    
    income_categories = [
        ("Saldo Inicial", "income", "Sistema", 0, "🏁", "#226F81"),
        ("Salario", "income", "Ingresos Fijos", 1, "💰", "#27AE60"),
        
        ("Freelance", "income", "Ingresos Variables", 0, "💼", "#2980B9"),
        ("Trabajo extra", "income", "Ingresos Variables", 0, "⏰", "#16A085"),
        ("Negocio propio", "income", "Ingresos Variables", 0, "🏪", "#8E44AD"),
        ("Ventas", "income", "Ingresos Variables", 0, "💵", "#27AE60"),
        
        ("Renta de propiedad", "income", "Ingresos Pasivos", 1, "🏠", "#9B59B6"),
        ("Inversiones", "income", "Ingresos Pasivos", 1, "📈", "#2980B9"),
        ("Dividendos", "income", "Ingresos Pasivos", 0, "📊", "#3498DB"),
        ("Intereses", "income", "Ingresos Pasivos", 1, "💹", "#1ABC9C"),
        
        ("Bono", "income", "Ingresos Extraordinarios", 0, "🎉", "#2ECC71"),
        ("Cobro de deuda", "income", "Ingresos Extraordinarios", 0, "💳", "#E74C3C"),
        ("Préstamo recibido", "income", "Ingresos Extraordinarios", 0, "🏦", "#8E44AD"),
        ("Herencia", "income", "Ingresos Extraordinarios", 0, "🏛️", "#F39C12"),
        ("Venta de cosas", "income", "Ingresos Extraordinarios", 0, "🛍️", "#2ECC71"),
        ("Reembolso", "income", "Ingresos Extraordinarios", 0, "🔄", "#3498DB"),
        ("Otros ingresos", "income", "Ingresos Extraordinarios", 0, "✨", "#16A085"),
    ]
    
    for name, type_, category_group, is_recurring, icon, color in expense_categories + income_categories:
        cursor.execute(
            "INSERT INTO categories (name, type, category_group, is_recurring, icon, color) VALUES (?, ?, ?, ?, ?, ?)",
            (name, type_, category_group, is_recurring, icon, color)
        )

def get_expense_categories() -> list[dict]:
    """Obtiene todas las categorías de gastos."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, category_group, icon, is_recurring, color
        FROM categories
        WHERE type = 'expense'
        ORDER BY category_group, name
    """)
    results = cursor.fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "category_group": row["category_group"],
            "icon": row["icon"] or "📦",
            "is_recurring": bool(row["is_recurring"]) if "is_recurring" in row.keys() else False,
            "color": row["color"] or "#95A5A6"
        }
        for row in results
    ]

def get_expense_categories_grouped() -> dict[str, list[dict]]:
    """Obtiene las categorías de gastos agrupadas por grupo."""
    categories = get_expense_categories()
    grouped = {}
    for cat in categories:
        group = cat["category_group"]
        if group not in grouped:
            grouped[group] = []
        grouped[group].append(cat)
    return grouped

def get_payment_methods() -> list[dict]:
    """Obtiene todos los métodos de pago registrados que no estén archivados."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, type, is_default, icon, credit_limit, cutoff_day, payment_due_day, status
        FROM payment_methods
        WHERE status IS NULL OR status != 'archived'
        ORDER BY order_index ASC, id ASC
    """)
    results = cursor.fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "type": row["type"],
            "is_default": bool(row["is_default"]),
            "icon": row["icon"] or "💳",
            "credit_limit": float(row["credit_limit"] or 0),
            "cutoff_day": int(row["cutoff_day"] or 1),
            "payment_due_day": int(row["payment_due_day"] or 1),
            "status": row["status"] or "active"
        }
        for row in results
    ]

def reorder_payment_method(method_id, direction):
    """Lógica de intercambio de posiciones en la base de datos."""
    conn = get_connection() 
    cursor = conn.cursor()
    cursor.execute("SELECT id, order_index FROM payment_methods WHERE type != 'cash' AND (status IS NULL OR status != 'archived') ORDER BY order_index ASC")
    methods = cursor.fetchall() 
    
    idx = -1
    for i, m in enumerate(methods):
        if m["id"] == method_id:
            idx = i
            break
            
    if idx == -1: 
        conn.close()
        return

    target_idx = idx - 1 if direction == "up" else idx + 1
    if 0 <= target_idx < len(methods):
        current_id = methods[idx]["id"]
        current_order = methods[idx]["order_index"]
        neighbor_id = methods[target_idx]["id"]
        neighbor_order = methods[target_idx]["order_index"]
        
        if current_order == neighbor_order:
            current_order, neighbor_order = idx, target_idx

        cursor.execute("UPDATE payment_methods SET order_index = ? WHERE id = ?", (neighbor_order, current_id))
        cursor.execute("UPDATE payment_methods SET order_index = ? WHERE id = ?", (current_order, neighbor_id))
        conn.commit()
    conn.close()

def get_default_payment_method() -> dict | None:
    """Obtiene el método de pago marcado como predeterminado."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, type, is_default, icon
        FROM payment_methods
        WHERE is_default = 1 AND (status IS NULL OR status != 'archived')
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row["id"],
            "name": row["name"],
            "type": row["type"],
            "is_default": bool(row["is_default"]),
            "icon": row["icon"] or "💳"
        }
    return None

def get_payment_methods_for_dropdown() -> list[ft.dropdown.Option]:
    """Obtiene los métodos de pago formateados para un Dropdown (excluye congelados y archivados)."""
    methods = get_payment_methods()
    active_methods = [m for m in methods if m.get("status", "active") == "active"]
    return [ft.dropdown.Option(key=str(m["id"]), text=f"{m['icon']} {m['name']}") for m in active_methods]

def save_transaction(
    category_id: int,
    payment_method_id: int,
    amount: float,
    description: str,
    type: str,
    date: str,
    recurrence_type: str = None,         
    is_recurrence_active: bool = False   
) -> None:
    """Guarda una nueva transacción. Si es recurrent, genera un recurrence_chain_id único de inicio (Puntero Vivo = 1)."""
    conn = get_connection()
    cursor = conn.cursor()
    chain_id = str(uuid.uuid4()) if is_recurrence_active else None
    active_flag = 1 if is_recurrence_active else 0
    try:
        cursor.execute("""
            INSERT INTO transactions (
                category_id, payment_method_id, amount, description, type, date,
                recurrence_type, is_recurrence_active, recurrence_chain_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            category_id, payment_method_id, amount, description, type, date,
            recurrence_type, active_flag, chain_id
        ))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error al guardar la transacción: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_transaction_by_id(transaction_id: int) -> dict:
    """Obtiene todos los datos de una transacción específica por su ID."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    query = "SELECT t.*, c.name as category_name, p.name as payment_method_name FROM transactions t JOIN categories c ON t.category_id = c.id JOIN payment_methods p ON t.payment_method_id = p.id WHERE t.id = ?"
    cursor.execute(query, (transaction_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_transaction(transaction_id: int, data: dict) -> None:
    """Actualiza una transacción existente aisladamente para evitar descuadres en cascada."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        update_fields = []
        values = []
        
        if "amount" in data:
            update_fields.append("amount = ?")
            values.append(data["amount"])
        if "description" in data:
            update_fields.append("description = ?")
            values.append(data["description"])
        if "category_id" in data:
            update_fields.append("category_id = ?")
            values.append(data["category_id"])
        if "date" in data:
            update_fields.append("date = ?")
            values.append(data["date"])
        if "payment_method_id" in data:
            update_fields.append("payment_method_id = ?")
            values.append(data["payment_method_id"])
        if "type" in data:
            update_fields.append("type = ?")
            values.append(data["type"])
        
        if not update_fields:
            return
            
        values.append(transaction_id) 
        query = f"UPDATE transactions SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, values)
        conn.commit()
    except Exception as e:
        print(f"Error al actualizar la transacción: {e}")
        conn.rollback()
        raise e 
    finally:
        conn.close()

def delete_transaction(transaction_id: int) -> None:
    """Elimina una transacción de la base de datos por su ID."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error al eliminar la transacción: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_categories_by_group(group_name: str, category_type: str = 'expense') -> list[dict]:
    """Obtiene categorías por grupo y tipo (expense o income)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, icon, color, is_custom, is_favorite
        FROM categories
        WHERE type = ? AND LOWER(category_group) = LOWER(?)
        ORDER BY name
    """, (category_type, group_name))
    results = cursor.fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "icon": row["icon"] or "📦",
            "color": row["color"] or "#95A5A6",
            "is_custom": bool(dict(row).get("is_custom", 0)),
            "is_favorite": bool(dict(row).get("is_favorite", 0))
        }
        for row in results
    ]

def get_current_month_dates() -> tuple[str, str]:
    """Obtiene las fechas de inicio y fin del mes actual."""
    now = datetime.now()
    start_date = f"{now.year}-{now.month:02d}-01"
    if now.month == 12:
        end_date = f"{now.year + 1}-01-01"
    else:
        end_date = f"{now.year}-{now.month + 1:02d}-01"
    return start_date, end_date

def get_total_income_current_month() -> float:
    """Obtiene el total de ingresos del mes actual filtrando amortizaciones internas."""
    start_date, end_date = get_current_month_dates()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM transactions
        WHERE type = 'income'
        AND date >= ? AND date < ?
        AND is_recurrence_active != 1
        AND category_id != (SELECT id FROM categories WHERE name = 'Pago de tarjetas' LIMIT 1)
    """, (start_date, end_date))
    result = cursor.fetchone()["total"]
    conn.close()
    return float(result)

def get_total_expense_current_month() -> float:
    """Obtiene el total de gastos del mes actual ignorando punteros futuros (is_recurrence_active = 1)."""
    start_date, end_date = get_current_month_dates()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM transactions
        WHERE type = 'expense'
        AND date >= ? AND date < ?
        AND is_recurrence_active != 1
    """, (start_date, end_date))
    result = cursor.fetchone()["total"]
    conn.close()
    return float(result)

def get_total_balance() -> float:
    """Obtiene el saldo total (liquidez) blindado contra duplicados de abonos a tarjetas de crédito."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'income' AND is_recurrence_active != 1 AND category_id != (SELECT id FROM categories WHERE name = 'Pago de tarjetas' LIMIT 1)) -
            (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'expense' AND is_recurrence_active != 1) -
            (SELECT COALESCE(SUM(amount), 0) FROM transfers WHERE destination_loan_id IS NOT NULL) as total_balance
    """)
    row = cursor.fetchone()
    conn.close()
    return float(row["total_balance"] or 0.0)

def get_historical_balance(up_to_date: str = None, payment_method_id: int = None) -> float:
    """Calcula el saldo histórico con rigor absoluto ignorando punteros futuros e ingresos de amortización interna."""
    conn = get_connection()
    cursor = conn.cursor()
    
    if payment_method_id is None:
        if up_to_date is None:
            cursor.execute("""
                SELECT
                    (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'income' AND is_recurrence_active != 1 AND category_id != (SELECT id FROM categories WHERE name = 'Pago de tarjetas' LIMIT 1)) -
                    (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'expense' AND is_recurrence_active != 1) -
                    (SELECT COALESCE(SUM(amount), 0) FROM transfers WHERE destination_loan_id IS NOT NULL) as balance
            """)
        else:
            cursor.execute("""
                SELECT
                    (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'income' AND date < ? AND is_recurrence_active != 1 AND category_id != (SELECT id FROM categories WHERE name = 'Pago de tarjetas' LIMIT 1)) -
                    (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'expense' AND date < ? AND is_recurrence_active != 1) -
                    (SELECT COALESCE(SUM(amount), 0) FROM transfers WHERE destination_loan_id IS NOT NULL AND date < ?) as balance
            """, (up_to_date, up_to_date, up_to_date))
    else:
        if up_to_date is None:
            cursor.execute("""
                SELECT
                    (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE payment_method_id = ? AND type = 'income' AND is_recurrence_active != 1 AND category_id != (SELECT id FROM categories WHERE name = 'Pago de tarjetas' LIMIT 1)) -
                    (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE payment_method_id = ? AND type = 'expense' AND is_recurrence_active != 1) +
                    (SELECT COALESCE(SUM(amount), 0) FROM transfers WHERE destination_method_id = ?) -
                    (SELECT COALESCE(SUM(amount), 0) FROM transfers WHERE source_method_id = ?) as balance
            """, (payment_method_id, payment_method_id, payment_method_id, payment_method_id))
        else:
            cursor.execute("""
                SELECT
                    (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE payment_method_id = ? AND type = 'income' AND date < ? AND is_recurrence_active != 1 AND category_id != (SELECT id FROM categories WHERE name = 'Pago de tarjetas' LIMIT 1)) -
                    (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE payment_method_id = ? AND type = 'expense' AND date < ? AND is_recurrence_active != 1) +
                    (SELECT COALESCE(SUM(amount), 0) FROM transfers WHERE destination_method_id = ? AND date < ?) -
                    (SELECT COALESCE(SUM(amount), 0) FROM transfers WHERE source_method_id = ? AND date < ?) as balance
            """, (payment_method_id, up_to_date, payment_method_id, up_to_date, payment_method_id, up_to_date, payment_method_id, up_to_date))
            
    row = cursor.fetchone()
    conn.close()
    return float(row["balance"] or 0.0)

def get_balance_by_payment_method() -> list[dict]:
    """Obtiene los saldos de los métodos de pago activos o congelados desglosando y descontando el remanente de compras a meses de la tarjeta enlazada."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            pm.id, pm.name, pm.type, pm.icon,
            pm.credit_limit, pm.cutoff_day, pm.payment_due_day, pm.status,
            (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE payment_method_id = pm.id AND type = 'income' AND is_recurrence_active != 1 AND category_id != (SELECT id FROM categories WHERE name = 'Pago de tarjetas' LIMIT 1)) as total_income,
            (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE payment_method_id = pm.id AND type = 'expense' AND is_recurrence_active != 1) as total_expense,
            (SELECT COALESCE(SUM(amount), 0) FROM transfers WHERE destination_method_id = pm.id) as transfers_in,
            (SELECT COALESCE(SUM(amount), 0) FROM transfers WHERE source_method_id = pm.id) as transfers_out
        FROM payment_methods pm
        WHERE pm.status IS NULL OR pm.status != 'archived'
        ORDER BY pm.is_default DESC, pm.name
    """)
    results = cursor.fetchall()
    conn.close()
    
    loans_with_progress = get_all_loans_with_progress()
    methods_list = []
    
    for row in results:
        m_id = row["id"]
        m_type = row["type"]
        base_balance = float(row["total_income"]) - float(row["total_expense"]) + float(row["transfers_in"]) - float(row["transfers_out"])
        
        if m_type == "card":
            # Restamos el saldo remanente de las compras a mensualidades para afectar el crédito disponible total
            linked_debt = sum(l["remaining"] for l in loans_with_progress if l["card_id"] == m_id)
            base_balance -= linked_debt
            
        methods_list.append({
            "id": m_id,
            "name": row["name"],
            "type": m_type,
            "icon": row["icon"] or "💳",
            "credit_limit": float(row["credit_limit"] or 0),
            "cutoff_day": row["cutoff_day"],
            "payment_due_day": row["payment_due_day"],
            "status": row["status"] or "active",
            "balance": base_balance
        })
    return methods_list

def add_payment_method(name: str, type_: str, icon: str, credit_limit: float = 0, cutoff: int = 1, due: int = 1) -> int:
    """Agrega un nuevo método de pago."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO payment_methods (name, type, icon, credit_limit, cutoff_day, payment_due_day, status)
        VALUES (?, ?, ?, ?, ?, ?, 'active')
    """, (name, type_, icon, credit_limit, cutoff, due))
    method_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return method_id

def get_expenses_by_category_group() -> list[dict]:
    """Obtiene la suma de gastos agrupados por grupo de categoría del mes visible ignorando punteros futuros."""
    start_date, end_date = get_current_month_dates()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            c.category_group,
            COALESCE(SUM(t.amount), 0) as total,
            c.color
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.type = 'expense'
        AND t.date >= ? AND t.date < ?
        AND t.is_recurrence_active != 1
        GROUP BY c.category_group
        ORDER BY total DESC
    """, (start_date, end_date))
    results = cursor.fetchall()
    conn.close()
    return [
        {
            "category_group": row["category_group"],
            "total": float(row["total"]),
            "color": row["color"] or "#95A5A6"
        }
        for row in results
    ]

def get_income_vs_expense_current_month() -> dict:
    """Obtiene los totales de ingresos vs gastos del mes actual."""
    return {
        "income": get_total_income_current_month(),
        "expense": get_total_expense_current_month()
    }

def get_filtered_transactions(start_date: str, end_date: str, payment_method_id: int = None, is_recurrence_view: bool = False) -> list[dict]:
    """Obtiene movimientos filtrados. Soporta de forma nativa el aislamiento de Eslabones."""
    try:
        process_recurring_transactions()
    except Exception as ex:
        print(f"[Autosanción] Error ejecutando encadenamiento de eslabones: {ex}")

    conn = get_connection()
    cursor = conn.cursor()
    
    if is_recurrence_view:
        where_clause = "WHERE t.is_recurrence_active IN (1, 2)"
        params = []
    else:
        where_clause = "WHERE t.date >= ? AND t.date < ? AND t.is_recurrence_active != 1"
        params = [start_date, end_date]
    
    query = f"""
        SELECT
            t.id, t.amount, t.description, t.type, t.date,
            t.recurrence_type, t.is_recurrence_active, t.last_applied_date,
            c.name as category_name, c.icon as category_icon, c.color as category_color,
            pm.name as payment_method_name, pm.icon as payment_method_icon, t.payment_method_id, t.category_id
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        JOIN payment_methods pm ON t.payment_method_id = pm.id
        {where_clause}
    """
    
    if payment_method_id is not None:
        query += " AND t.payment_method_id = ?"
        params.append(payment_method_id)
        
    query += " ORDER BY t.date DESC, t.id DESC"
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": row["id"],
            "amount": float(row["amount"]),
            "description": row["description"] or "",
            "type": row["type"],
            "date": row["date"],
            "recurrence_type": row["recurrence_type"],
            "is_recurrence_active": int(row["is_recurrence_active"]),
            "last_applied_date": row["last_applied_date"],
            "category_name": row["category_name"],
            "category_id": row["category_id"],
            "payment_method_id": row["payment_method_id"],
            "category_icon": row["category_icon"] or "📦",
            "category_color": row["category_color"] or "#95A5A6",
            "payment_method_name": row["payment_method_name"],
            "payment_method_icon": row["payment_method_icon"] or "💳"
        }
        for row in results
    ]

def get_sum_income(start_date: str, end_date: str, payment_method_id: int = None) -> float:
    """Obtiene la suma de ingresos en un periodo ignorando punteros futuros (is_recurrence_active = 1)."""
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type = 'income' AND date >= ? AND date < ? AND is_recurrence_active != 1 AND category_id != (SELECT id FROM categories WHERE name = 'Pago de tarjetas' LIMIT 1)"
    params = [start_date, end_date]
    
    if payment_method_id is not None:
        query += " AND payment_method_id = ?"
        params.append(payment_method_id)
        
    cursor.execute(query, params)
    result = cursor.fetchone()["total"]
    conn.close()
    return float(result)

def get_sum_expenses(start_date: str, end_date: str, payment_method_id: int = None) -> float:
    """Obtiene la suma de gastos en un periodo ignorando punteros futuros (is_recurrence_active = 1)."""
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type = 'expense' AND date >= ? AND date < ? AND is_recurrence_active != 1"
    params = [start_date, end_date]
    
    if payment_method_id is not None:
        query += " AND payment_method_id = ?"
        params.append(payment_method_id)
        
    cursor.execute(query, params)
    result = cursor.fetchone()["total"]
    conn.close()
    return float(result)

def get_balance(start_date: str, end_date: str) -> float:
    """Obtiene el saldo neto de un periodo."""
    income = get_sum_income(start_date, end_date)
    expense = get_sum_expenses(start_date, end_date)
    return income - expense

def get_daily_trend(start_date: str, end_date: str, payment_method_id: int = None, search_query: str = None) -> list[dict]:
    """
    Obtiene la tendencia diaria de transacciones calculando en paralelo los totales,
    los flujos recurrentes y una serie de tiempo exclusiva para el término buscado.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    match_str = f"%{search_query}%" if search_query else ""
    
    query = """
        SELECT
            t.date,
            SUM(CASE WHEN t.type = 'income' AND t.is_recurrence_active != 1 AND t.category_id != (SELECT id FROM categories WHERE name = 'Pago de tarjetas' LIMIT 1) THEN t.amount ELSE 0 END) as daily_income,
            SUM(CASE WHEN t.type = 'expense' AND t.is_recurrence_active != 1 THEN t.amount ELSE 0 END) as daily_expense,
            SUM(CASE WHEN t.type = 'income' AND t.is_recurrence_active = 2 THEN t.amount ELSE 0 END) as rec_income,
            SUM(CASE WHEN t.type = 'expense' AND t.is_recurrence_active = 2 THEN t.amount ELSE 0 END) as rec_expense,
            SUM(CASE WHEN t.type = 'income' AND t.is_recurrence_active != 1 AND (t.description LIKE ? OR c.name LIKE ?) THEN t.amount ELSE 0 END) as search_income,
            SUM(CASE WHEN t.type = 'expense' AND t.is_recurrence_active != 1 AND (t.description LIKE ? OR c.name LIKE ?) THEN t.amount ELSE 0 END) as search_expense
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.date >= ? AND t.date < ?
    """
    params = [match_str, match_str, match_str, match_str, start_date, end_date]
    
    if payment_method_id is not None:
        query += " AND t.payment_method_id = ?"
        params.append(payment_method_id)
        
    query += " GROUP BY t.date ORDER BY t.date ASC"
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    
    return [
        {
            "date": row["date"],
            "income": float(row["daily_income"]),
            "expense": float(row["daily_expense"]),
            "rec_income": float(row["rec_income"]),
            "rec_expense": float(row["rec_expense"]),
            "search_income": float(row["search_income"]),
            "search_expense": float(row["search_expense"])
        }
        for row in results
    ]

def get_monthly_trend(start_date: str, end_date: str, payment_method_id: int = None, search_query: str = None) -> list[dict]:
    """
    Obtiene la tendencia mensual de transacciones segmentando de forma síncrona los flujos
    globales, fijos y la serie histórica específica del criterio de búsqueda.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    match_str = f"%{search_query}%" if search_query else ""
    
    query = """
        SELECT
            strftime('%Y-%m', t.date) as month,
            SUM(CASE WHEN t.type = 'income' AND t.is_recurrence_active != 1 AND t.category_id != (SELECT id FROM categories WHERE name = 'Pago de tarjetas' LIMIT 1) THEN t.amount ELSE 0 END) as monthly_income,
            SUM(CASE WHEN t.type = 'expense' AND t.is_recurrence_active != 1 THEN t.amount ELSE 0 END) as monthly_expense,
            SUM(CASE WHEN t.type = 'income' AND t.is_recurrence_active = 2 THEN t.amount ELSE 0 END) as rec_income,
            SUM(CASE WHEN t.type = 'expense' AND t.is_recurrence_active = 2 THEN t.amount ELSE 0 END) as rec_expense,
            SUM(CASE WHEN t.type = 'income' AND t.is_recurrence_active != 1 AND (t.description LIKE ? OR c.name LIKE ?) THEN t.amount ELSE 0 END) as search_income,
            SUM(CASE WHEN t.type = 'expense' AND t.is_recurrence_active != 1 AND (t.description LIKE ? OR c.name LIKE ?) THEN t.amount ELSE 0 END) as search_expense
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.date >= ? AND t.date < ?
    """
    params = [match_str, match_str, match_str, match_str, start_date, end_date]
    
    if payment_method_id is not None:
        query += " AND t.payment_method_id = ?"
        params.append(payment_method_id)
        
    query += " GROUP BY month ORDER BY month ASC"
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    
    return [
        {
            "month": row["month"],
            "income": float(row["monthly_income"]),
            "expense": float(row["monthly_expense"]),
            "rec_income": float(row["rec_income"]),
            "rec_expense": float(row["rec_expense"]),
            "search_income": float(row["search_income"]),
            "search_expense": float(row["search_expense"])
        }
        for row in results
    ]

def get_last_month_dates() -> tuple[str, str]:
    """Obtiene las fechas de inicio y fin del mes pasado."""
    now = datetime.now()
    first_day_this_month = datetime(now.year, now.month, 1)
    last_day_last_month = first_day_this_month - timedelta(days=1)
    start_date = f"{last_day_last_month.year}-{last_day_last_month.month:02d}-01"
    end_date = f"{first_day_this_month.year}-{first_day_this_month.month:02d}-01"
    return start_date, end_date

def get_total_income_last_month() -> float:
    """Obtiene el total de ingresos del mes pasado ignorando punteros futuros."""
    start_date, end_date = get_last_month_dates()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM transactions
        WHERE type = 'income'
        AND date >= ? AND date < ?
        AND is_recurrence_active != 1
        AND category_id != (SELECT id FROM categories WHERE name = 'Pago de tarjetas' LIMIT 1)
    """, (start_date, end_date))
    result = cursor.fetchone()["total"]
    conn.close()
    return float(result)

def get_total_expense_last_month() -> float:
    """Obtiene el total de gastos del mes pasado ignorando punteros futuros."""
    start_date, end_date = get_last_month_dates()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM transactions
        WHERE type = 'expense'
        AND date >= ? AND date < ?
        AND is_recurrence_active != 1
    """, (start_date, end_date))
    result = cursor.fetchone()["total"]
    conn.close()
    return float(result)

def get_expenses_by_category_time_series() -> list[dict]:
    """Obtiene los gastos agrupados por categoría y día del mes actual ignorando punteros futuros."""
    start_date, end_date = get_current_month_dates()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            date,
            c.category_group as category,
            SUM(t.amount) as total
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.type = 'expense'
        AND t.date >= ? AND t.date < ?
        AND t.is_recurrence_active != 1
        GROUP BY date, c.category_group
        ORDER BY date ASC
    """, (start_date, end_date))
    results = cursor.fetchall()
    conn.close()
    return [
        {
            "date": row["date"],
            "category": row["category"],
            "total": float(row["total"])
        }
        for row in results
    ]

def save_setting(key: str, value: str) -> None:
    """Guarda o actualiza una configuración global."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO app_settings (setting_key, setting_value)
            VALUES (?, ?)
        """, (key, value))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error al guardar la configuración: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_setting(key: str, default: str = None) -> str | None:
    """Obtiene el valor de una configuración global."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM app_settings WHERE setting_key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row["setting_value"]
    return default

def get_initial_balance_category_id() -> int | None:
    """Obtiene el ID de la categoría 'Saldo Inicial'."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM categories WHERE name = 'Saldo Inicial' AND type = 'income' LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return row["id"]
    return None

def set_initial_balance(amount: float) -> None:
    """Establece o actualiza el saldo inicial de la aplicación."""
    if amount <= 0:
        return
        
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO categories (name, icon, color, type, category_group, is_recurring)
            VALUES ('Saldo Inicial', '🏁', '#226F81', 'income', 'Sistema', 0)
        """)
        conn.commit()

        cursor.execute("SELECT id FROM categories WHERE name = 'Saldo Inicial'")
        cat_result = cursor.fetchone()
        if not cat_result:
            return
        category_id = cat_result["id"]
        
        cursor.execute("SELECT id FROM payment_methods WHERE is_default = 1 LIMIT 1")
        pm_result = cursor.fetchone()
        payment_method_id = pm_result["id"] if pm_result else 1
        
        cursor.execute("DELETE FROM transactions WHERE category_id = ? AND description = 'Ajuste inicial de cuenta'", (category_id,))
        
        cursor.execute("""
            INSERT INTO transactions (category_id, payment_method_id, amount, description, type, date)
            VALUES (?, ?, ?, 'Ajuste inicial de cuenta', 'income', '1900-01-01')
        """, (category_id, payment_method_id, amount))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error al establecer el saldo inicial: {e}")
        conn.rollback()
    finally:
        conn.close()
        
def get_initial_balance() -> float:
    """Obtiene el monto del saldo inicial registrado."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE c.name = 'Saldo Inicial' AND c.type = 'income'
          AND t.description = 'Ajuste inicial de cuenta'
    """)
    row = cursor.fetchone()
    conn.close()
    return float(row["total"])

def hard_reset_database() -> None:
    """Elimina todos los datos del usuario volviendo el esquema al estado de fábrica con parámetros de corte iniciales."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM transactions;")
        cursor.execute("DELETE FROM transfers;")
        cursor.execute("DELETE FROM loans;")
        cursor.execute("DELETE FROM custom_templates;")
        cursor.execute("DELETE FROM categories WHERE is_custom = 1;")
        try:
            cursor.execute("UPDATE categories SET is_favorite = 0;")
        except sqlite3.OperationalError:
            pass
            
        cursor.execute("DELETE FROM payment_methods;")
        try:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='payment_methods';")
        except sqlite3.OperationalError:
            pass
        
        cursor.execute("""
            INSERT INTO payment_methods (name, type, is_default, icon, credit_limit, cutoff_day, payment_due_day, status)
            VALUES ('Efectivo', 'cash', 1, '💵', 0, 1, 1, 'active')
        """)
        cursor.execute("""
            INSERT INTO payment_methods (name, type, is_default, icon, credit_limit, cutoff_day, payment_due_day, status)
            VALUES ('Tarjeta', 'card', 0, '💳', 10000, 1, 28, 'active')
        """)

        try:
            cursor.execute("UPDATE app_settings SET setting_value = '0' WHERE setting_key = 'initial_balance';")
            cursor.execute("UPDATE app_settings SET setting_value = '0' WHERE setting_key = 'security_enabled';")
            cursor.execute("UPDATE app_settings SET setting_value = '' WHERE setting_key = 'app_pin_hash';")
            cursor.execute("UPDATE app_settings SET setting_value = '' WHERE setting_key = 'totp_secret';")
        except sqlite3.Error:
            pass
            
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error crítico al hacer el Hard Reset: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_templates(type_: str = None) -> list[dict]:
    """Obtiene las plantillas rápidas personalizadas."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if type_:
        cursor.execute("""
            SELECT id, name, icon, default_amount, color, type, category_id
            FROM custom_templates
            WHERE type = ?
            ORDER BY created_at DESC
        """, (type_,))
    else:
        cursor.execute("""
            SELECT id, name, icon, default_amount, color, type, category_id
            FROM custom_templates
            ORDER BY created_at DESC
        """)
    results = cursor.fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "icon": row["icon"],
            "default_amount": float(row["default_amount"]),
            "color": row["color"],
            "type": row["type"] if "type" in row.keys() else "expense",
            "category_id": row["category_id"] if "category_id" in row.keys() else None
        }
        for row in results
    ]

def add_template(data: dict) -> int:
    """Crea una nueva plantilla rápida."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO custom_templates (name, icon, default_amount, color, type, category_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data["name"], 
            data["icon"], 
            data["default_amount"], 
            data["color"], 
            data.get("type", "expense"), 
            data.get("category_id")
        ))
        template_id = cursor.lastrowid
        conn.commit()
        return template_id
    except sqlite3.Error as e:
        print(f"Error al agregar plantilla: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()

def delete_template(template_id: int) -> None:
    """Elimina una plantilla rápida."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM custom_templates WHERE id = ?", (template_id,))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error al eliminar plantilla: {e}")
        conn.rollback()
    finally:
        conn.close()

def add_category(name: str, icon: str, color: str, type_: str, category_group: str) -> None:
    """Crea una nueva categoría de usuario."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO categories (name, icon, color, type, category_group, is_custom, is_recurring)
            VALUES (?, ?, ?, ?, ?, 1, 0)
        """, (name, icon, color, type_, category_group))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error al agregar categoría: {e}")
        conn.rollback()
    finally:
        conn.close()

def update_category(cat_id: int, name: str, icon: str, color: str) -> None:
    """Actualiza los datos de una categoría personalizada."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE categories 
            SET name = ?, icon = ?, color = ?
            WHERE id = ? AND is_custom = 1
        """, (name, icon, color, cat_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error al actualizar categoría: {e}")
        conn.rollback()
    finally:
        conn.close()

def delete_category(cat_id: int) -> None:
    """Elimina una categoría personalizada."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM categories WHERE id = ? AND is_custom = 1", (cat_id,))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error al eliminar categoría: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_loans() -> list[dict]:
    """Obtiene la lista de préstamos registrados."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, total_amount, interest_rate, term_months, term_unit, start_date, icon, color
        FROM loans
        ORDER BY start_date DESC
    """)
    results = cursor.fetchall()
    conn.close()
    return [dict(row) for row in results]

def add_loan(name: str, total_amount: float, interest_rate: float, term_months: int, term_unit: str, start_date: str, icon: str, color: str, card_id: int = None) -> int:
    """Registra un nuevo préstamo tradicional o una compra a mensualidades vinculada a una tarjeta de crédito."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO loans (name, total_amount, interest_rate, term_months, term_unit, start_date, icon, color, card_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, total_amount, interest_rate, term_months, term_unit, start_date, icon, color, card_id))
        loan_id = cursor.lastrowid
        conn.commit()
        return loan_id
    except sqlite3.Error as e:
        print(f"Error al agregar préstamo o compra a crédito: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()

def update_loan(loan_id: int, name: str, total_amount: float, interest_rate: float, term_months: int, term_unit: str, start_date: str) -> None:
    """Actualiza la configuración de un préstamo."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE loans 
            SET name = ?, total_amount = ?, interest_rate = ?, term_months = ?, term_unit = ?, start_date = ?
            WHERE id = ?
        """, (name, total_amount, interest_rate, term_months, term_unit, start_date, loan_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error al actualizar préstamo: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()

def delete_loan(loan_id: int) -> None:
    """Elimina un préstamo o compra a meses aplicando borrado suave inteligente si cuenta con abonos vinculados."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Comprobar si existen abonos/pagos realizados en la tabla de transferencias
        cursor.execute("SELECT COUNT(*) as count FROM transfers WHERE destination_loan_id = ?", (loan_id,))
        has_payments = cursor.fetchone()["count"] > 0
        
        if has_payments:
            # Borrado suave (Mantiene la integridad de los saldos e históricos)
            cursor.execute("UPDATE loans SET status = 'deleted' WHERE id = ?", (loan_id,))
        else:
            cursor.execute("UPDATE transfers SET destination_loan_id = NULL WHERE destination_loan_id = ?", (loan_id,))
            cursor.execute("DELETE FROM loans WHERE id = ?", (loan_id,))
            
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error al eliminar préstamo o compra: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()

def add_transfer(source_id: int, amount: float, date: str, description: str, dest_method_id: int = None, dest_loan_id: int = None) -> None:
    """Registra una transferencia o abono manteniendo la trazabilidad del origen."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Obtenemos nombre del origen para la trazabilidad
        cursor.execute("SELECT name, icon FROM payment_methods WHERE id = ?", (source_id,))
        source_data = cursor.fetchone()
        source_name = source_data["name"] if source_data else "Origen"
        
        # 1. Registro maestro
        cursor.execute("""
            INSERT INTO transfers (source_method_id, destination_method_id, destination_loan_id, amount, date, description)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (source_id, dest_method_id, dest_loan_id, amount, date, description))
        
        # 2. Inyección en transacciones para tarjetas (Impacto visual en historial)
        if dest_method_id is not None:
            cursor.execute("SELECT type FROM payment_methods WHERE id = ?", (dest_method_id,))
            method_row = cursor.fetchone()
            if method_row and method_row["type"] == "card":
                # Usamos un import local para romper la dependencia circular con core.translations
                from core.translations import t
                full_desc = f"{t('deudas_pay_from', default='Pago desde')}: {source_name}"
                
                # Buscamos la categoría 'Pago de tarjetas' de tipo 'expense' o creamos un fallback
                cursor.execute("SELECT id FROM categories WHERE name = 'Pago de tarjetas' LIMIT 1")
                cat_row = cursor.fetchone()
                category_id = cat_row["id"] if cat_row else 8
                
                cursor.execute("""
                    INSERT INTO transactions (category_id, payment_method_id, amount, description, type, date)
                    VALUES (?, ?, ?, ?, 'income', ?)
                """, (category_id, dest_method_id, amount, full_desc, date))
                
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error al registrar abono/transferencia: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()

def delete_payment_method(method_id: int):
    """Elimina una cuenta bancaria o tarjeta permanentemente (Borrado forzado físico)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM payment_methods WHERE id = ?", (method_id,))
    conn.commit()
    conn.close()

def update_payment_method(method_id: int, name: str, type_: str, icon: str, credit_limit: float = 0, cutoff: int = 1, due: int = 1):
    """Actualiza los datos de un método de pago."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE payment_methods 
        SET name = ?, type = ?, icon = ?, credit_limit = ?, cutoff_day = ?, payment_due_day = ?
        WHERE id = ?
    """, (name, type_, icon, credit_limit, cutoff, due, method_id))
    conn.commit()
    conn.close()

def freeze_payment_method(method_id: int) -> None:
    """Conmuta el estado de un método de pago entre activo y congelado (frozen)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM payment_methods WHERE id = ?", (method_id,))
    row = cursor.fetchone()
    if row:
        current_status = row["status"] or "active"
        new_status = "active" if current_status == "frozen" else "frozen"
        cursor.execute("UPDATE payment_methods SET status = ? WHERE id = ?", (new_status, method_id))
        conn.commit()
    conn.close()

def archive_payment_method(method_id: int, new_name: str) -> None:
    """Archiva de forma lógica una cuenta renombrándola cronológicamente para liberar el constraint UNIQUE."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE payment_methods SET status = 'archived', name = ? WHERE id = ?", (new_name, method_id))
    conn.commit()
    conn.close()

def transfer_all_to_cash(method_id: int) -> None:
    """Calcula matemáticamente el saldo real remanente y lo evacúa con una transferencia líquida a efectivo."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE payment_method_id = ? AND type = 'income' AND is_recurrence_active != 1 AND category_id != (SELECT id FROM categories WHERE name = 'Pago de tarjetas' LIMIT 1)) as total_income,
            (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE payment_method_id = ? AND type = 'expense' AND is_recurrence_active != 1) as total_expense,
            (SELECT COALESCE(SUM(amount), 0) FROM transfers WHERE destination_method_id = ?) as transfers_in,
            (SELECT COALESCE(SUM(amount), 0) FROM transfers WHERE source_method_id = ?) as transfers_out
    """, (method_id, method_id, method_id, method_id))
    row = cursor.fetchone()
    balance = float(row["total_income"]) - float(row["total_expense"]) + float(row["transfers_in"]) - float(row["transfers_out"])
    
    if balance > 0.01:
        cursor.execute("SELECT id FROM payment_methods WHERE type = 'cash' LIMIT 1")
        cash_row = cursor.fetchone()
        cash_id = cash_row["id"] if cash_row else 1
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        cursor.execute("""
            INSERT INTO transfers (source_method_id, destination_method_id, amount, date, description)
            VALUES (?, ?, ?, ?, 'Evacuación de fondos automática por cierre de cuenta')
        """, (method_id, cash_id, balance, today_str))
        conn.commit()
    conn.close()
    
def get_all_loans_with_progress() -> list[dict]:
    """Obtiene los préstamos vigentes aplicando correctamente la tasa de interés e incluyendo su progreso temporal según las fechas de pago expiradas."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            l.id, l.name, l.total_amount, l.interest_rate, l.icon, l.color,
            l.start_date, l.term_months, l.term_unit, l.card_id, l.status,
            COALESCE((SELECT SUM(amount) FROM transfers WHERE destination_loan_id = l.id), 0) as total_paid
        FROM loans l
        WHERE l.status IS NULL OR l.status != 'deleted'
        ORDER BY l.start_date DESC
    """)
    results = cursor.fetchall()
    conn.close()
    
    from datetime import datetime, date
    from dateutil.relativedelta import relativedelta
    
    loans_data = []
    for row in results:
        base_amount = float(row["total_amount"])
        interest_rate = float(row["interest_rate"] or 0)
        card_id = row["card_id"]
        
        total_with_interest = base_amount + (base_amount * (interest_rate / 100))
        
        if card_id is not None:
            try:
                start_dt = datetime.strptime(row["start_date"][:10], "%Y-%m-%d").date()
                today_dt = datetime.now().date()
                
                # Consultar los parámetros de corte y pago de la tarjeta vinculada
                conn_card = get_connection()
                cursor_card = conn_card.cursor()
                cursor_card.execute("SELECT cutoff_day, payment_due_day FROM payment_methods WHERE id = ?", (card_id,))
                c_row = cursor_card.fetchone()
                conn_card.close()
                
                cutoff_day = int(c_row["cutoff_day"]) if c_row and c_row["cutoff_day"] else 1
                payment_due_day = int(c_row["payment_due_day"]) if  c_row and c_row["payment_due_day"] else 26
                
                if start_dt.day <= cutoff_day:
                    first_cutoff = date(start_dt.year, start_dt.month, cutoff_day)
                else:
                    nm = start_dt + relativedelta(months=1)
                    first_cutoff = date(nm.year, nm.month, cutoff_day)
                
                billed_months = 0
                for i in range(1, int(row["term_months"]) + 1):
                    inst_cutoff = first_cutoff + relativedelta(months=i-1)
                    inst_due = date(inst_cutoff.year, inst_cutoff.month, payment_due_day)
                    if inst_due <= today_dt:
                        billed_months += 1
                        
                total_paid = billed_months * (total_with_interest / int(row["term_months"]))
            except:
                total_paid = float(row["total_paid"])
        else:
            total_paid = float(row["total_paid"])
        
        remaining = max(0.0, total_with_interest - total_paid)
        percentage = (total_paid / total_with_interest) * 100 if total_with_interest > 0 else 0
        
        loans_data.append({
            "id": row["id"],
            "name": row["name"],
            "total_amount": base_amount,
            "total_paid": total_paid,
            "remaining": remaining,
            "progress_percentage": percentage,
            "interest_rate": interest_rate,
            "icon": row["icon"],
            "color": row["color"],
            "start_date": row["start_date"],
            "term_months": row["term_months"],
            "term_unit": row["term_unit"],
            "card_id": card_id,
            "status": row["status"] or "active"
        })
    return loans_data

def get_loan_payments(loan_id: int) -> list[dict]:
    """Obtiene los abonos vinculados a un préstamo."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.id, t.amount, t.date, pm.name as method_name, pm.icon as method_icon, pm.type as method_type
        FROM transfers t
        JOIN payment_methods pm ON t.source_method_id = pm.id
        WHERE t.destination_loan_id = ?
        ORDER BY t.date DESC
    """, (loan_id,))
    results = cursor.fetchall()
    conn.close()
    return [dict(row) for row in results]

def get_card_transactions(card_id: int, start_date: str, end_date: str) -> list[dict]:
    """Obtiene los movimientos (tanto consumos, abonos recibidos como compras diferidas virtuales) de tarjetas de crédito."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Obtener transacciones reales registradas en la tabla
    cursor.execute("""
        SELECT t.id, t.amount, t.description, t.date, t.type,
               c.name as category_name, c.icon as category_icon,
               pm.name as source_name, pm.icon as source_icon
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN payment_methods pm ON pm.id = (
            SELECT source_method_id FROM transfers 
            WHERE destination_method_id = t.payment_method_id AND date = t.date AND amount = t.amount LIMIT 1
        )
        WHERE t.payment_method_id = ?
        AND t.date >= ? AND t.date < ?
        AND t.is_recurrence_active != 1
        ORDER BY t.date DESC, t.id DESC
    """, (card_id, start_date, end_date))
    
    results = [dict(row) for row in cursor.fetchall()]
    
    # 2. Obtener compras a crédito vinculadas a esta tarjeta para inyectar filas virtuales
    cursor.execute("""
        SELECT id, name, total_amount, interest_rate, term_months, start_date
        FROM loans
        WHERE card_id = ? AND (status IS NULL OR status != 'deleted')
    """, (card_id,))
    card_loans = cursor.fetchall()
    conn.close()
    
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    
    for l in card_loans:
        l_id = l["id"]
        l_name = l["name"]
        l_total = float(l["total_amount"])
        l_interest = float(l["interest_rate"] or 0)
        l_months = int(l["term_months"] or 1)
        
        try:
            l_start_date = datetime.strptime(l["start_date"][:10], "%Y-%m-%d").date()
        except:
            continue
            
        # A. Inyectar la Compra Padre (Gasto Original con opacidad)
        if start_dt <= l_start_date < end_dt:
            results.append({
                "id": f"virtual_parent_{l_id}",
                "amount": l_total,
                "description": l_name,
                "date": l["start_date"],
                "type": "expense",
                "category_name": "Compra a Crédito",
                "category_icon": "🔄",
                "source_name": None,
                "source_icon": None,
                "is_credit_purchase_parent": True,
                "is_credit_purchase_installment": False
            })
            
        # B. Inyectar las Mensualidades individuales aplicables
        total_with_interest = l_total + (l_total * (l_interest / 100))
        monthly_amount = total_with_interest / l_months
        
        for i in range(1, l_months + 1):
            inst_date = l_start_date + relativedelta(months=i-1)
            if start_dt <= inst_date < end_dt:
                results.append({
                    "id": f"virtual_inst_{l_id}_{i}",
                    "amount": monthly_amount,
                    "description": f"{l_name} ({i}/{l_months})",
                    "date": inst_date.strftime("%Y-%m-%d"),
                    "type": "expense",
                    "category_name": "Mensualidad",
                    "category_icon": "📅",
                    "source_name": None,
                    "source_icon": None,
                    "is_credit_purchase_parent": False,
                    "is_credit_purchase_installment": True
                })
                
    results.sort(key=lambda x: (x["date"], str(x["id"])), reverse=True)
    return results

def get_expenses_by_category_summary(start_date: str, end_date: str, payment_method_id: int = None) -> list[dict]:
    """Suma y agrupa los gastos de categorías filtrando los punteros futuros (is_recurrence_active = 1)."""
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT c.name as category, c.color, SUM(t.amount) as total
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.type = 'expense' AND t.date >= ? AND t.date < ?
          AND t.is_recurrence_active != 1
    """
    max_params = [start_date, end_date]
    if payment_method_id is not None:
        query += " AND t.payment_method_id = ?"
        max_params.append(payment_method_id)
        
    query += " GROUP BY c.name, c.color ORDER BY total DESC"
    cursor.execute(query, max_params)
    results = cursor.fetchall()
    conn.close()
    return [{"category": r["category"], "color": r["color"] or "#95A5A6", "total": float(r["total"])} for r in results]

def get_income_by_category_summary(start_date: str, end_date: str, payment_method_id: int = None) -> list[dict]:
    """Suma y agrupa los ingresos de categorías filtrando los punteros futuros (is_recurrence_active = 1)."""
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT c.name as category, c.color, SUM(t.amount) as total
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.type = 'income' AND t.date >= ? AND t.date < ?
          AND t.is_recurrence_active != 1
    """
    max_params = [start_date, end_date]
    if payment_method_id is not None:
        query += " AND t.payment_method_id = ?"
        max_params.append(payment_method_id)
        
    query += " GROUP BY c.name, c.color ORDER BY total DESC"
    cursor.execute(query, max_params)
    results = cursor.fetchall()
    conn.close()
    return [{"category": r["category"], "color": r["color"] or "#27AE60", "total": float(r["total"])} for r in results]

def toggle_category_favorite(category_id: int, is_favorite: bool) -> None:
    """Cambia el estado favorito de una categoría."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE categories SET is_favorite = ? WHERE id = ?", (1 if is_favorite else 0, category_id))
    conn.commit()
    conn.close()

def get_favorite_categories(category_type: str) -> list:
    """Retorna las categorías marcadas como favoritas de un tipo específico."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categories WHERE type = ? AND is_favorite = 1", (category_type,))
    columns = [column[0] for column in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return results

def backup_database(destination_path: str) -> None:
    """Copia el archivo de la base de datos actual a una ruta de destino."""
    shutil.copy2(DB_PATH, destination_path)

def restore_database(source_path: str) -> None:
    """Reemplaza la base de datos actual con un archivo de respaldo con rollback de seguridad y reaplica las migraciones."""
    temp_backup = DB_PATH + ".bak"
    try:
        if os.path.exists(DB_PATH):
            shutil.copy2(DB_PATH, temp_backup)
        shutil.copy2(source_path, DB_PATH)
        if os.path.exists(temp_backup):
            os.remove(temp_backup)
            
        init_database()
        
    except Exception as e:
        if os.path.exists(temp_backup):
            shutil.copy2(temp_backup, DB_PATH)
            os.remove(temp_backup)
        raise e

def get_active_recurrences(transaction_type: str = None) -> list[dict]:
    """Obtiene exclusivamente el eslabón activo futuro (is_recurrence_active = 1) para las tarjetas de la UI."""
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT 
            t.id, t.amount, t.description, t.type, t.date,
            t.recurrence_type, t.is_recurrence_active, t.last_applied_date,
            c.name as category_name, c.icon as category_icon, c.color as category_color, 
            t.payment_method_id, t.category_id,
            pm.name as payment_method_name, pm.icon as payment_method_icon
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        JOIN payment_methods pm ON t.payment_method_id = pm.id
        WHERE t.is_recurrence_active = 1
    """
    params = []
    if transaction_type:
        query += " AND t.type = ?"
        params.append(transaction_type)
        
    query += " ORDER BY t.date DESC"
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "amount": float(row["amount"]),
            "description": row["description"] or "",
            "type": row["type"],
            "date": row["date"],
            "recurrence_type": row["recurrence_type"] or "mes",
            "is_recurrence_active": int(row["is_recurrence_active"]),
            "last_applied_date": row["last_applied_date"] or row["date"],
            "category_name": row["category_name"],
            "category_id": row["category_id"],
            "payment_method_id": row["payment_method_id"],
            "category_icon": row["category_icon"] or "📦",
            "category_color": row["category_color"] or "#95A5A6",
            "payment_method_name": row["payment_method_name"],
            "payment_method_icon": row["payment_method_icon"] or "💳"
        }
        for row in results
    ]

def disable_recurrence(transaction_id: int) -> None:
    """Apaga permanentemente la continuidad de la cadena apagando el puntero activo (is_recurrence_active = 0)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE transactions SET is_recurrence_active = 0 WHERE id = ?", (transaction_id,))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error al desactivar la recurrencia: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()

def update_recurrence_settings(transaction_id: int, recurrence_type: str, amount: float, description: str) -> None:
    """Actualiza los parámetros de la plantilla del puntero futuro activo."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE transactions
            SET recurrence_type = ?, amount = ?, description = ?
            WHERE id = ?
        """, (recurrence_type, amount, description, transaction_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error al actualizar parámetros de recurrencia: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()

def process_recurring_transactions() -> None:
    """
    Motor Idempotente de Eslabones Encadenados (Chained State Machine).
    Si un puntero vivo (is_recurrence_active = 1) expira por llegar a la fecha de hoy,
    se transforma en registro histórico puro (is_recurrence_active = 2) y dispara en
    cadena el nacimiento del siguiente puntero proyectado hacia el futuro.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    today = datetime.now().date()
    
    while True:
        cursor.execute("""
            SELECT id, category_id, payment_method_id, amount, description, type, date, 
                   recurrence_type, recurrence_chain_id, last_applied_date
            FROM transactions 
            WHERE is_recurrence_active = 1 AND date <= ?
        """, (today_str,))
        
        expired_pointers = cursor.fetchall()
        if not expired_pointers:
            break
            
        for tx in expired_pointers:
            tx_id = tx["id"]
            r_type = str(tx["recurrence_type"]).lower().strip()
            r_type = r_type.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
            
            try:
                current_date = datetime.strptime(str(tx["date"]).strip()[:10], "%Y-%m-%d").date()
            except Exception as e:
                print(f"[Motor Error] Imposible parsear fecha del eslabón: {e}")
                continue
                
            if "semana" in r_type or "weekly" in r_type or "semanal" in r_type:
                next_date = current_date + timedelta(weeks=1)
            elif "bimensual" in r_type or "bimonthly" in r_type:
                total_months = current_date.month - 1 + 2
                y = current_date.year + (total_months // 12)
                m = (total_months % 12) + 1
                try:
                    next_date = current_date.replace(year=y, month=m)
                except ValueError:
                    if m == 12:
                        next_date = datetime(y + 1, 1, 1).date() - timedelta(days=1)
                    else:
                        next_date = datetime(y, m + 1, 1).date() - timedelta(days=1)
            elif "trimestral" in r_type or "quarterly" in r_type:
                total_months = current_date.month - 1 + 3
                y = current_date.year + (total_months // 12)
                m = (total_months % 12) + 1
                try:
                    next_date = current_date.replace(year=y, month=m)
                except ValueError:
                    if m == 12:
                        next_date = datetime(y + 1, 1, 1).date() - timedelta(days=1)
                    else:
                        next_date = datetime(y, m + 1, 1).date() - timedelta(days=1)
            elif "semestral" in r_type or "semiannual" in r_type:
                total_months = current_date.month - 1 + 6
                y = current_date.year + (total_months // 12)
                m = (total_months % 12) + 1
                try:
                    next_date = current_date.replace(year=y, month=m)
                except ValueError:
                    if m == 12:
                        next_date = datetime(y + 1, 1, 1).date() - timedelta(days=1)
                    else:
                        next_date = datetime(y, m + 1, 1).date() - timedelta(days=1)
            elif "mes" in r_type or "monthly" in r_type or "mensual" in r_type:
                y = current_date.year + (current_date.month // 12) if current_date.month == 12 else current_date.year
                m = 1 if current_date.month == 12 else current_date.month + 1
                try:
                    next_date = current_date.replace(year=y, month=m)
                except ValueError:
                    if m == 12:
                        next_date = datetime(y + 1, 1, 1).date() - timedelta(days=1)
                    else:
                        next_date = datetime(y, m + 1, 1).date() - timedelta(days=1)
            elif "dia" in r_type or "daily" in r_type or "diario" in r_type:
                next_date = current_date + timedelta(days=1)
            elif "quince" in r_type or "biweekly" in r_type or "quincenal" in r_type:
                if current_date.day <= 15:
                    if current_date.month == 12:
                        target = datetime(current_date.year + 1, 1, 1).date() - timedelta(days=1)
                    else:
                        target = datetime(current_date.year, current_date.month + 1, 1).date() - timedelta(days=1)
                else:
                    nm = current_date.month + 1 if current_date.month < 12 else 1
                    ny = current_date.year if current_date.month < 12 else current_date.year + 1
                    target = datetime(ny, nm, 15).date()
                
                if get_setting("adjust_biweekly_weekend", "0") == "1":
                    wd = target.weekday()
                    if wd == 5: next_date = target - timedelta(days=1)
                    elif wd == 6: next_date = target - timedelta(days=2)
                    else: next_date = target
                else:
                    next_date = target
            elif "generica" in r_type or "yearly" in r_type or "anual" in r_type:
                try:
                    next_date = current_date.replace(year=current_date.year + 1)
                except ValueError:
                    next_date = current_date.replace(year=current_date.year + 1, day=28)
            else:
                next_date = current_date + timedelta(days=30)

            chain_id = tx["recurrence_chain_id"]
            if not chain_id:
                import uuid
                chain_id = str(uuid.uuid4())

            cursor.execute("""
                UPDATE transactions 
                SET is_recurrence_active = 2, recurrence_chain_id = ?, last_applied_date = ?
                WHERE id = ?
            """, (chain_id, today_str, tx_id))

            cursor.execute("""
                INSERT INTO transactions (
                    category_id, payment_method_id, amount, description, type, date,
                    recurrence_type, is_recurrence_active, recurrence_chain_id, last_applied_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, (
                tx["category_id"], tx["payment_method_id"], tx["amount"], tx["description"],
                tx["type"], next_date.strftime("%Y-%m-%d"), tx["recurrence_type"], chain_id, tx["last_applied_date"]
            ))
            
    conn.commit()
    conn.close()