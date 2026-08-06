from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError


class InvoiceNotFoundError(NotFoundError):
    def __init__(self, invoice_id: int):
        super().__init__(f"Invoice with id {invoice_id} was not found.")


class PaymentNotFoundError(NotFoundError):
    def __init__(self, payment_id: int):
        super().__init__(f"Payment with id {payment_id} was not found.")


class InvoiceStateError(BusinessRuleError):
    pass


class InvoiceConflictError(ConflictError):
    pass
