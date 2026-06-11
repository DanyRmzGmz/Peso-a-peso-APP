"""
Views module - Contains all application views.
"""

from views.categorias_view import create_categorias_view
from views.placeholder_view import get_placeholder_view

__all__ = [
    "get_gastos_view",
    "get_placeholder_view",
]