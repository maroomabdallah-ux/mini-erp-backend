from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError


class ProductNotFoundError(NotFoundError):
    def __init__(self, product_id: int):
        super().__init__(f"Product with id {product_id} was not found.")


class CategoryNotFoundError(NotFoundError):
    def __init__(self, category_id: int):
        super().__init__(f"Category with id {category_id} was not found.")


class DuplicateSkuError(ConflictError):
    def __init__(self, sku: str):
        super().__init__(f"A product with SKU '{sku}' already exists.")


class DuplicateBarcodeError(ConflictError):
    def __init__(self, barcode: str):
        super().__init__(f"A product with barcode '{barcode}' already exists.")


class DuplicateCategoryError(ConflictError):
    def __init__(self, name: str):
        super().__init__(f"A category named '{name}' already exists.")


class CategoryCycleError(BusinessRuleError):
    def __init__(self):
        super().__init__("A category cannot be its own parent or descendant.")


class DeactivationError(BusinessRuleError):
    pass
