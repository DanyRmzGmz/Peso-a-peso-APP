"""
Repositorio de datos para el tracker de finanzas personales.
Contiene todas las operaciones CRUD y consultas especiales.
"""
from datetime import datetime, date
from typing import List, Optional, Tuple
from database.connection import get_connection
from database.models import Category, Transaction, MonthlySummary


# ============================================
# OPERACIONES DE CATEGORÍAS
# ============================================

def create_category(name: str, type_: str, icon: str = None, color: str = None) -> int:
    """
    Crea una nueva categoría en la base de datos.
    
    Args:
        name: Nombre de la categoría.
        type_: Tipo de categoría ('income' o 'expense').
        icon: Emoji o ícono (opcional).
        color: Color en formato hex (opcional).
    
    Returns:
        int: ID de la categoría creada.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO categories (name, type, icon, color) VALUES (?, ?, ?, ?)",
        (name, type_, icon, color)
    )
    
    category_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return category_id


def get_all_categories(type_: str = None) -> List[Category]:
    """
    Obtiene todas las categorías, opcionalmente filtradas por tipo.
    
    Args:
        type_: Tipo de categoría a filtrar ('income' o 'expense').
    
    Returns:
        List[Category]: Lista de categorías.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if type_:
        cursor.execute(
            "SELECT * FROM categories WHERE type = ? ORDER BY name",
            (type_,)
        )
    else:
        cursor.execute("SELECT * FROM categories ORDER BY type, name")
    
    rows = cursor.fetchall()
    conn.close()
    
    return [Category.from_row(row) for row in rows]


def get_category_by_id(category_id: int) -> Optional[Category]:
    """
    Obtiene una categoría por su ID.
    
    Args:
        category_id: ID de la categoría.
    
    Returns:
        Category o None si no existe.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
    row = cursor.fetchone()
    conn.close()
    
    return Category.from_row(row) if row else None


def delete_category(category_id: int) -> bool:
    """
    Elimina una categoría por su ID.
    
    Args:
        category_id: ID de la categoría a eliminar.
    
    Returns:
        bool: True si se eliminó, False si no existía.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return deleted


# ============================================
# OPERACIONES DE TRANSACCIONES
# ============================================

def create_transaction(
    category_id: int,
    amount: float,
    type_: str,
    description: str = "",
    transaction_date: date = None
) -> int:
    """
    Crea una nueva transacción en la base de datos.
    
    Args:
        category_id: ID de la categoría.
        amount: Monto de la transacción.
        type_: Tipo de transacción ('income' o 'expense').
        description: Descripción opcional.
        transaction_date: Fecha de la transacción (default: hoy).
    
    Returns:
        int: ID de la transacción creada.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if transaction_date is None:
        transaction_date = date.today()
    
    cursor.execute(
        """INSERT INTO transactions 
           (category_id, amount, description, type, date) 
           VALUES (?, ?, ?, ?, ?)""",
        (category_id, amount, description, type_, transaction_date.isoformat())
    )
    
    transaction_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return transaction_id


def get_all_transactions(
    type_: str = None,
    limit: int = None,
    offset: int = 0
) -> List[Transaction]:
    """
    Obtiene todas las transacciones, opcionalmente filtradas y paginadas.
    
    Args:
        type_: Tipo de transacción a filtrar ('income' o 'expense').
        limit: Límite de resultados.
        offset: Offset para paginación.
    
    Returns:
        List[Transaction]: Lista de transacciones.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if type_:
        query = "SELECT * FROM transactions WHERE type = ? ORDER BY date DESC, id DESC"
        params = (type_,)
    else:
        query = "SELECT * FROM transactions ORDER BY date DESC, id DESC"
        params = ()
    
    if limit:
        query += " LIMIT ? OFFSET ?"
        params = params + (limit, offset)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [Transaction.from_row(row) for row in rows]


def get_transaction_by_id(transaction_id: int) -> Optional[Transaction]:
    """
    Obtiene una transacción por su ID.
    
    Args:
        transaction_id: ID de la transacción.
    
    Returns:
        Transaction o None si no existe.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,))
    row = cursor.fetchone()
    conn.close()
    
    return Transaction.from_row(row) if row else None


def update_transaction(
    transaction_id: int,
    category_id: int = None,
    amount: float = None,
    description: str = None,
    type_: str = None,
    transaction_date: date = None
) -> bool:
    """
    Actualiza una transacción existente.
    
    Args:
        transaction_id: ID de la transacción a actualizar.
        category_id: Nuevo ID de categoría (opcional).
        amount: Nuevo monto (opcional).
        description: Nueva descripción (opcional).
        type_: Nuevo tipo (opcional).
        transaction_date: Nueva fecha (opcional).
    
    Returns:
        bool: True si se actualizó, False si no existía.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Construir query dinámicamente
    updates = []
    params = []
    
    if category_id is not None:
        updates.append("category_id = ?")
        params.append(category_id)
    if amount is not None:
        updates.append("amount = ?")
        params.append(amount)
    if description is not None:
        updates.append("description = ?")
        params.append(description)
    if type_ is not None:
        updates.append("type = ?")
        params.append(type_)
    if transaction_date is not None:
        updates.append("date = ?")
        params.append(transaction_date.isoformat())
    
    if not updates:
        return False
    
    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    
    params.append(transaction_id)
    
    query = f"UPDATE transactions SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, params)
    
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return updated


def delete_transaction(transaction_id: int) -> bool:
    """
    Elimina una transacción por su ID.
    
    Args:
        transaction_id: ID de la transacción a eliminar.
    
    Returns:
        bool: True si se eliminó, False si no existía.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return deleted


# ============================================
# CONSULTAS ESPECIALES
# ============================================

def get_transactions_by_month(
    year: int,
    month: int,
    type_: str = None
) -> List[Transaction]:
    """
    Obtiene las transacciones de un mes específico.
    
    Args:
        year: Año (ej: 2024).
        month: Mes (1-12).
        type_: Filtrar por tipo ('income' o 'expense').
    
    Returns:
        List[Transaction]: Lista de transacciones del mes.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Calcular rango de fechas del mes
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
    
    if type_:
        cursor.execute(
            """SELECT * FROM transactions 
               WHERE date >= ? AND date < ? AND type = ?
               ORDER BY date DESC, id DESC""",
            (start_date, end_date, type_)
        )
    else:
        cursor.execute(
            """SELECT * FROM transactions 
               WHERE date >= ? AND date < ?
               ORDER BY date DESC, id DESC""",
            (start_date, end_date)
        )
    
    rows = cursor.fetchall()
    conn.close()
    
    return [Transaction.from_row(row) for row in rows]


def get_monthly_summary(year: int, month: int) -> MonthlySummary:
    """
    Obtiene el resumen mensual de ingresos y gastos.
    
    Args:
        year: Año (ej: 2024).
        month: Mes (1-12).
    
    Returns:
        MonthlySummary: Resumen del mes.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Calcular rango de fechas del mes
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
    
    # Obtener total de ingresos
    cursor.execute(
        """SELECT COALESCE(SUM(amount), 0) as total 
           FROM transactions 
           WHERE type = 'income' AND date >= ? AND date < ?""",
        (start_date, end_date)
    )
    total_income = cursor.fetchone()[0] or 0.0
    
    # Obtener total de gastos
    cursor.execute(
        """SELECT COALESCE(SUM(amount), 0) as total 
           FROM transactions 
           WHERE type = 'expense' AND date >= ? AND date < ?""",
        (start_date, end_date)
    )
    total_expense = cursor.fetchone()[0] or 0.0
    
    # Obtener conteo de transacciones
    cursor.execute(
        """SELECT COUNT(*) as count 
           FROM transactions 
           WHERE date >= ? AND date < ?""",
        (start_date, end_date)
    )
    transaction_count = cursor.fetchone()[0] or 0
    
    conn.close()
    
    return MonthlySummary(
        year=year,
        month=month,
        total_income=total_income,
        total_expense=total_expense,
        transaction_count=transaction_count
    )


def get_balance() -> float:
    """
    Calcula el balance total (ingresos - gastos).
    
    Returns:
        float: Balance total.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Total de ingresos
    cursor.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type = 'income'"
    )
    total_income = cursor.fetchone()[0] or 0.0
    
    # Total de gastos
    cursor.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type = 'expense'"
    )
    total_expense = cursor.fetchone()[0] or 0.0
    
    conn.close()
    
    return total_income - total_expense


def get_category_totals(year: int = None, month: int = None, type_: str = None) -> List[Tuple[Category, float]]:
    """
    Obtiene el total por categoría, opcionalmente filtrado por período.
    
    Args:
        year: Año (opcional).
        month: Mes (opcional, requiere year).
        type_: Filtrar por tipo.
    
    Returns:
        List[Tuple[Category, float]]: Lista de tuplas (categoría, total).
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Construir condición de fecha
    date_condition = ""
    params = []
    
    if year and month:
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"
        date_condition = "AND t.date >= ? AND t.date < ?"
        params = [start_date, end_date]
    
    # Construir condición de tipo
    type_condition = ""
    if type_:
        type_condition = "AND t.type = ?"
        params.append(type_)
    
    query = f"""
        SELECT c.*, COALESCE(SUM(t.amount), 0) as total
        FROM categories c
        LEFT JOIN transactions t ON c.id = t.category_id {date_condition} {type_condition}
        GROUP BY c.id
        ORDER BY c.type, c.name
    """
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [(Category.from_row(row), row["total"]) for row in rows]