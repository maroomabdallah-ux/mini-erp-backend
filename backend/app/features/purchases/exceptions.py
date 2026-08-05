from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError


class PurchaseOrderNotFoundError(NotFoundError):
    def __init__(self, purchase_order_id: int):
        super().__init__(f"Purchase order with id {purchase_order_id} was not found.")


class PurchaseOrderStateError(BusinessRuleError):
    pass


class PurchaseOrderEntityError(BusinessRuleError):
    pass


class PurchaseOrderConflictError(ConflictError):
    pass


class GoodsReceiptNotFoundError(NotFoundError):
    def __init__(self, receipt_id: int):
        super().__init__(f"Goods receipt with id {receipt_id} was not found.")
