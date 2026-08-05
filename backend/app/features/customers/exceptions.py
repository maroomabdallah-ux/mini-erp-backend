from app.core.exceptions import BusinessRuleError, NotFoundError


class CustomerNotFoundError(NotFoundError):
    def __init__(self, customer_id: int):
        super().__init__(f"Customer with id {customer_id} was not found.")


class CustomerDeactivationError(BusinessRuleError):
    pass
