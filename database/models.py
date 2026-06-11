"""
Modelos de datos para el tracker de finanzas personales.
"""
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional


@dataclass
class Category:
    """
    Modelo de categoría para clasificar transacciones.
    
    Attributes:
        id: Identificador único de la categoría.
        name: Nombre de la categoría.
        type: Tipo de categoría ('income' o 'expense').
        icon: Emoji o ícono representativo.
        color: Color en formato hexadecimal.
        created_at: Fecha de creación del registro.
    """
    id: Optional[int] = None
    name: str = ""
    type: str = "expense"  # 'income' o 'expense'
    icon: Optional[str] = None
    color: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Valida que el tipo sea válido."""
        if self.type not in ("income", "expense"):
            raise ValueError("El tipo debe ser 'income' o 'expense'")
    
    def to_dict(self) -> dict:
        """Convierte el modelo a un diccionario."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "icon": self.icon,
            "color": self.color,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    @classmethod
    def from_row(cls, row) -> "Category":
        """Crea una instancia desde una fila de la base de datos."""
        return cls(
            id=row["id"],
            name=row["name"],
            type=row["type"],
            icon=row["icon"],
            color=row["color"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )
    
    def is_income(self) -> bool:
        """Retorna True si es una categoría de ingresos."""
        return self.type == "income"
    
    def is_expense(self) -> bool:
        """Retorna True si es una categoría de gastos."""
        return self.type == "expense"


@dataclass
class Transaction:
    """
    Modelo de transacción (ingreso o gasto).
    
    Attributes:
        id: Identificador único de la transacción.
        category_id: ID de la categoría asociada.
        amount: Monto de la transacción (siempre positivo).
        description: Descripción opcional de la transacción.
        type: Tipo de transacción ('income' o 'expense').
        date: Fecha de la transacción.
        created_at: Fecha de creación del registro.
        updated_at: Fecha de última modificación.
    """
    id: Optional[int] = None
    category_id: int = 0
    amount: float = 0.0
    description: str = ""
    type: str = "expense"  # 'income' o 'expense'
    date: date = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Valida los datos después de inicializar."""
        if self.type not in ("income", "expense"):
            raise ValueError("El tipo debe ser 'income' o 'expense'")
        if self.amount <= 0:
            raise ValueError("El monto debe ser mayor a 0")
        if self.date is None:
            self.date = date.today()
    
    def to_dict(self) -> dict:
        """Convierte el modelo a un diccionario."""
        return {
            "id": self.id,
            "category_id": self.category_id,
            "amount": self.amount,
            "description": self.description,
            "type": self.type,
            "date": self.date.isoformat() if self.date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_row(cls, row) -> "Transaction":
        """Crea una instancia desde una fila de la base de datos."""
        return cls(
            id=row["id"],
            category_id=row["category_id"],
            amount=row["amount"],
            description=row["description"],
            type=row["type"],
            date=datetime.strptime(row["date"], "%Y-%m-%d").date() if row["date"] else None,
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
        )
    
    def is_income(self) -> bool:
        """Retorna True si es un ingreso."""
        return self.type == "income"
    
    def is_expense(self) -> bool:
        """Retorna True si es un gasto."""
        return self.type == "expense"
    
    def signed_amount(self) -> float:
        """Retorna el monto con signo (+ para ingresos, - para gastos)."""
        return self.amount if self.is_income() else -self.amount


@dataclass
class MonthlySummary:
    """
    Modelo para almacenar el resumen mensual de finanzas.
    
    Attributes:
        year: Año del resumen.
        month: Mes del resumen (1-12).
        total_income: Total de ingresos en el mes.
        total_expense: Total de gastos en el mes.
        balance: Balance del mes (ingresos - gastos).
        transaction_count: Número de transacciones en el mes.
    """
    year: int
    month: int
    total_income: float = 0.0
    total_expense: float = 0.0
    balance: float = 0.0
    transaction_count: int = 0
    
    def __post_init__(self):
        """Calcula el balance automáticamente."""
        self.balance = self.total_income - self.total_expense
    
    def to_dict(self) -> dict:
        """Convierte el modelo a un diccionario."""
        return {
            "year": self.year,
            "month": self.month,
            "total_income": self.total_income,
            "total_expense": self.total_expense,
            "balance": self.balance,
            "transaction_count": self.transaction_count,
        }
    
    @property
    def month_name(self) -> str:
        """Retorna el nombre del mes."""
        months = [
            "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
        ]
        return months[self.month - 1] if 1 <= self.month <= 12 else "Desconocido"
    
    def formatted_summary(self) -> str:
        """Retorna un resumen formateado en string."""
        return (
            f"{self.month_name} {self.year}\n"
            f"Ingresos: ${self.total_income:,.2f}\n"
            f"Gastos: ${self.total_expense:,.2f}\n"
            f"Balance: ${self.balance:,.2f}"
        )