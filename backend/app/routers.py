from fastapi import APIRouter

from app.features.accounting.router import router as accounting_router
from app.features.audit.router import router as audit_router
from app.features.billing.router import router as billing_router
from app.features.customers.router import router as customers_router
from app.features.inventory.router import router as inventory_router
from app.features.products.router import router as products_router
from app.features.purchases.router import router as purchases_router
from app.features.quotations.router import router as quotations_router
from app.features.reports.router import router as reports_router
from app.features.sales.router import router as sales_router
from app.features.suppliers.router import router as suppliers_router
from app.features.users.auth_router import router as auth_router
from app.features.users.roles_router import router as roles_router
from app.features.users.router import router as users_router
from app.features.warehouses.router import router as warehouses_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(audit_router)
api_router.include_router(accounting_router)
api_router.include_router(billing_router)
api_router.include_router(customers_router)
api_router.include_router(products_router)
api_router.include_router(purchases_router)
api_router.include_router(quotations_router)
api_router.include_router(reports_router)
api_router.include_router(sales_router)
api_router.include_router(suppliers_router)
api_router.include_router(warehouses_router)
api_router.include_router(inventory_router)
