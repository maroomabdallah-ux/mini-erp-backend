from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError


class AccountNotFoundError(NotFoundError):
    pass


class AccountingRuleError(BusinessRuleError):
    pass


class AccountingConflictError(ConflictError):
    pass
