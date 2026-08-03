from fastapi import APIRouter

from app.features.audit.router import router as audit_router
from app.features.products.router import router as products_router
from app.features.users.auth_router import router as auth_router
from app.features.users.roles_router import router as roles_router
from app.features.users.router import router as users_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(audit_router)
api_router.include_router(products_router)
