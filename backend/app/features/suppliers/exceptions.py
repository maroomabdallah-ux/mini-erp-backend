from app.core.exceptions import BusinessRuleError, NotFoundError


class SupplierNotFoundError(NotFoundError):
    def __init__(self, supplier_id: int):
        super().__init__(f"Supplier with id {supplier_id} was not found.")


class SupplierDeactivationError(BusinessRuleError):
    pass
