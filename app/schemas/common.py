"""Reusable Pydantic types and validation helpers."""

from decimal import Decimal
from typing import Annotated

from pydantic import Field
from pydantic_core import core_schema


def _period_validator(value: str) -> str:
    """Validate a contribution period in YYYY-MM format (ADR-004)."""
    import re

    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
        raise ValueError("period must be a valid calendar month in YYYY-MM format")
    return value


class Period(str):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            _period_validator,
            core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )


# Monetary values use Decimal and never float (AGENTS financial rules).
Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)]
# Signed ledger balance (debit - credit): negative for credit-side accounts.
SignedMoney = Annotated[Decimal, Field(max_digits=18, decimal_places=2)]

# Share units are stored with 4 decimal places (ADR-005).
Quantity = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]