from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError


class SalesOrderNotFoundError(NotFoundError):
    def __init__(self, order_id: int):
        super().__init__(f"Sales order with id {order_id} was not found.")


class SalesOrderStateError(BusinessRuleError):
    pass


class SalesOrderConversionError(ConflictError):
    pass


class SalesOrderStockError(ConflictError):
    pass
