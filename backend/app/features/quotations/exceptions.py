from app.core.exceptions import BusinessRuleError, NotFoundError


class QuotationNotFoundError(NotFoundError):
    def __init__(self, quotation_id: int):
        super().__init__(f"Quotation with id {quotation_id} was not found.")


class QuotationStateError(BusinessRuleError):
    pass


class QuotationEntityError(BusinessRuleError):
    pass
