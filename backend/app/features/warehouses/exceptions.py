from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError


class WarehouseNotFoundError(NotFoundError):
    def __init__(self, warehouse_id: int):
        super().__init__(f"Warehouse with id {warehouse_id} was not found.")


class DuplicateWarehouseCodeError(ConflictError):
    def __init__(self, code: str):
        super().__init__(f"A warehouse with code '{code}' already exists.")


class WarehouseDeactivationError(BusinessRuleError):
    pass
