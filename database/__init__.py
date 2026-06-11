"""
Paquete database - Módulo de gestión de base de datos SQLite
"""
from database.connection import get_connection, init_database
from database.models import Category, Transaction
from database.repository import (
    # Categorías
    create_category,
    get_all_categories,
    get_category_by_id,
    delete_category,
    # Transacciones
    create_transaction,
    get_all_transactions,
    get_transaction_by_id,
    update_transaction,
    delete_transaction,
    # Consultas especiales
    get_transactions_by_month,
    get_monthly_summary,
    get_balance,
)

__all__ = [
    "get_connection",
    "init_database",
    "Category",
    "Transaction",
    "create_category",
    "get_all_categories",
    "get_category_by_id",
    "delete_category",
    "create_transaction",
    "get_all_transactions",
    "get_transaction_by_id",
    "update_transaction",
    "delete_transaction",
    "get_transactions_by_month",
    "get_monthly_summary",
    "get_balance",
]