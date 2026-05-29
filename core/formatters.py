"""
Módulo de formateo de valores monetarios.

Centraliza toda la gramática de los números para el sistema de finanzas.
"""

from database.connection import get_setting


def format_currency(amount: float) -> str:
    """
    Formatea un monto según la configuración de moneda del usuario.
    
    Args:
        amount (float): El monto a formatear.
        
    Returns:
        str: El monto formateado según la moneda configurada.
    """
    currency = get_setting("currency", "MXN")
    
    if currency == "EUR":
        formatted_us = f"${amount:,.2f}"
        number_part = formatted_us.replace("$", "")
        parts = number_part.split(".")
        if len(parts) == 2:
            integer_part = parts[0].replace(",", ".")
            decimal_part = parts[1]
            return f"{integer_part},{decimal_part} €"
        return f"{number_part} €"
    else:
        return f"${amount:,.2f}"