from datetime import date

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import DatabaseSession, require_permission
from app.features.reports import service
from app.features.reports.schemas import (
    InventoryValuationReport,
    ManagementDashboard,
    MonthlySalesRow,
    ProfitReport,
    ReceivableAgingReport,
    StockMovementRow,
    TopProductRow,
)
from app.features.users.model import User

router = APIRouter(prefix="/reports", tags=["Reports"])


def _default_from() -> date:
    return date.today().replace(day=1)


@router.get("/dashboard", response_model=ManagementDashboard)
def dashboard(
    db: DatabaseSession,
    actor: User = Depends(require_permission("reports.profit.read")),
):
    return service.dashboard(db)


@router.get("/profit", response_model=ProfitReport)
def profit(
    db: DatabaseSession,
    date_from: date = Query(default_factory=_default_from),
    date_to: date = Query(default_factory=date.today),
    category_id: int | None = Query(None, gt=0),
    actor: User = Depends(require_permission("reports.profit.read")),
):
    return service.profit(db, date_from, date_to, category_id)


@router.get("/top-products", response_model=list[TopProductRow])
def top_products(
    db: DatabaseSession,
    date_from: date = Query(default_factory=_default_from),
    date_to: date = Query(default_factory=date.today),
    limit: int = Query(10, ge=1, le=100),
    sort_by: str = Query("revenue", pattern="^(revenue|quantity)$"),
    actor: User = Depends(require_permission("reports.top_products.read")),
):
    return service.top_products(db, date_from, date_to, limit, sort_by)


@router.get("/inventory-valuation", response_model=InventoryValuationReport)
def inventory_valuation(
    db: DatabaseSession,
    actor: User = Depends(require_permission("reports.inventory_valuation.read")),
):
    return service.inventory_valuation(db)


@router.get("/receivables-aging", response_model=ReceivableAgingReport)
def receivables_aging(
    db: DatabaseSession,
    as_of: date = Query(default_factory=date.today),
    actor: User = Depends(require_permission("reports.receivables.read")),
):
    return service.receivables_aging(db, as_of)


@router.get("/monthly-sales", response_model=list[MonthlySalesRow])
def monthly_sales(
    db: DatabaseSession,
    months: int = Query(12, ge=1, le=36),
    actor: User = Depends(require_permission("reports.monthly_sales.read")),
):
    return service.monthly_sales(db, months)


@router.get("/stock-movements", response_model=list[StockMovementRow])
def stock_movements(
    product_id: int,
    db: DatabaseSession,
    warehouse_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    actor: User = Depends(require_permission("reports.inventory_valuation.read")),
):
    return service.stock_movements(db, product_id, warehouse_id, date_from, date_to)
