from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError


class StockLevelNotFoundError(NotFoundError):
    def __init__(self, product_id: int, warehouse_id: int):
        super().__init__(
            f"No stock level exists for product {product_id} in warehouse {warehouse_id}."
        )


class InactiveInventoryEntityError(BusinessRuleError):
    pass


class InsufficientStockError(ConflictError):
    def __init__(self, available: str, requested_change: str):
        super().__init__(
            "The adjustment would create negative stock.",
            field_errors={
                "quantity_change": (
                    f"Available quantity is {available}; requested change is {requested_change}."
                )
            },
        )
