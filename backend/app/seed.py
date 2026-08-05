"""Idempotent development seed data for RBAC and implemented master data."""

from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.features.inventory.models import StockLevel, StockMovement
from app.features.products.models import Category, Product
from app.features.users.model import Permission, Role, User
from app.features.warehouses.models import Warehouse

PERMISSIONS = {
    "users.manage": "Create, update, deactivate and reset users",
    "roles.manage": "Create roles and assign permissions",
    "audit.read": "Read audit logs",
    "products.read": "View products",
    "products.manage": "Create, update and deactivate products",
    "warehouses.read": "View warehouses",
    "warehouses.manage": "Create and update warehouses",
    "suppliers.read": "View suppliers",
    "suppliers.manage": "Create, update and deactivate suppliers",
    "customers.read": "View customers",
    "customers.manage": "Create, update and deactivate customers",
    "inventory.read": "View stock levels and movements",
    "inventory.adjust": "Record manual stock adjustments",
    "inventory.transfer": "Create and process warehouse transfers",
    "inventory.count": "Create and enter physical stock counts",
    "inventory.count.approve": "Approve physical stock counts",
    "inventory.low_stock.read": "View low-stock alerts",
    "purchase_orders.read": "View purchase orders",
    "purchase_orders.create": "Create purchase orders",
    "purchase_orders.update": "Edit draft purchase orders",
    "purchase_orders.approve": "Approve purchase orders",
    "purchase_orders.cancel": "Cancel purchase orders",
    "goods_receipts.read": "View goods receipts",
    "goods_receipts.create": "Receive goods against purchase orders",
    "quotations.read": "View quotations",
    "quotations.manage": "Create, update and convert quotations",
    "sales_orders.read": "View sales orders",
    "sales_orders.create": "Create sales orders",
    "sales_orders.update": "Edit draft sales orders",
    "sales_orders.confirm": "Confirm sales orders",
    "sales_orders.deliver": "Deliver sales orders and deduct stock",
    "invoices.read": "View invoices",
    "invoices.create": "Generate invoices",
    "invoices.cancel": "Cancel invoices with reversing entries",
    "accounts.read": "View chart of accounts",
    "accounts.manage": "Manage chart of accounts",
    "payments.read": "View customer and supplier payments",
    "payments.create": "Record customer and supplier payments",
    "journal_entries.read": "View journal entries",
    "customer_statements.read": "View customer statements",
    "supplier_statements.read": "View supplier statements",
    "reports.profit.read": "View profit reports",
    "reports.top_products.read": "View top-products reports",
    "reports.inventory_valuation.read": "View inventory valuation",
    "reports.receivables.read": "View receivables aging",
    "reports.monthly_sales.read": "View monthly sales reports",
}

ROLE_NAMES = [
    "admin",
    "purchasing_officer",
    "sales_officer",
    "warehouse_keeper",
    "accountant",
    "manager",
]

ROLE_PERMISSIONS = {
    "purchasing_officer": {
        "products.read",
        "products.manage",
        "warehouses.read",
        "suppliers.read",
        "suppliers.manage",
        "purchase_orders.read",
        "purchase_orders.create",
        "purchase_orders.update",
        "purchase_orders.cancel",
        "goods_receipts.read",
    },
    "sales_officer": {
        "products.read",
        "warehouses.read",
        "customers.read",
        "customers.manage",
        "inventory.read",
        "quotations.read",
        "quotations.manage",
        "sales_orders.read",
        "sales_orders.create",
        "sales_orders.update",
        "sales_orders.confirm",
        "invoices.read",
        "invoices.create",
    },
    "warehouse_keeper": {
        "products.read",
        "warehouses.read",
        "inventory.read",
        "inventory.adjust",
        "inventory.transfer",
        "inventory.count",
        "inventory.low_stock.read",
        "purchase_orders.read",
        "goods_receipts.read",
        "goods_receipts.create",
        "sales_orders.read",
        "sales_orders.deliver",
    },
    "accountant": {
        "products.read",
        "warehouses.read",
        "customers.read",
        "accounts.read",
        "accounts.manage",
        "payments.read",
        "payments.create",
        "invoices.read",
        "invoices.cancel",
        "purchase_orders.read",
        "journal_entries.read",
        "customer_statements.read",
        "supplier_statements.read",
        "reports.profit.read",
        "reports.receivables.read",
        "reports.inventory_valuation.read",
    },
    "manager": {
        "products.read",
        "warehouses.read",
        "customers.read",
        "quotations.read",
        "purchase_orders.read",
        "purchase_orders.approve",
        "sales_orders.read",
        "invoices.read",
        "inventory.read",
        "inventory.low_stock.read",
        "inventory.count.approve",
        "reports.profit.read",
        "reports.top_products.read",
        "reports.inventory_valuation.read",
        "reports.receivables.read",
        "reports.monthly_sales.read",
    },
}

DEMO_USERS = {
    "purchasing": ("Purchasing", "Officer", "purchasing_officer"),
    "sales": ("Sales", "Officer", "sales_officer"),
    "warehouse": ("Warehouse", "Keeper", "warehouse_keeper"),
    "accountant": ("Finance", "Accountant", "accountant"),
    "manager": ("Operations", "Manager", "manager"),
}

DEMO_PASSWORD = "Passw0rd!"

# Intentionally below their minimum levels so development environments include
# realistic Low Stock alerts.
DEMO_LOW_STOCK = {
    "PEN-PIL-G2-07-BLK": (Decimal("8.00"), Decimal("10.00")),
    "PAP-DP-A4-80G": (Decimal("12.00"), Decimal("14.00")),
    "CHR-ERG-MESH-BLK": (Decimal("1.00"), Decimal("2.00")),
}

CATEGORY_DATA = [
    ("Electronics", None),
    ("Computers & Laptops", "Electronics"),
    ("Mobile Accessories", "Electronics"),
    ("Office Supplies", None),
    ("Paper & Notebooks", "Office Supplies"),
    ("Writing Tools", "Office Supplies"),
    ("Office Furniture", None),
]

PRODUCT_DATA = [
    {
        "sku": "LAP-LEN-E14-G5",
        "name": "Lenovo ThinkPad E14 Gen 5 Laptop",
        "barcode": "0196804123456",
        "category": "Computers & Laptops",
        "cost_price": "525.00",
        "sale_price": "649.00",
        "min_stock_level": "3.00",
    },
    {
        "sku": "LAP-HP-250-G10",
        "name": "HP 250 G10 Business Laptop",
        "barcode": "0197498123451",
        "category": "Computers & Laptops",
        "cost_price": "415.00",
        "sale_price": "499.00",
        "min_stock_level": "4.00",
    },
    {
        "sku": "MON-DELL-P2422H",
        "name": "Dell P2422H 24-inch Monitor",
        "barcode": "0884116398123",
        "category": "Computers & Laptops",
        "cost_price": "118.00",
        "sale_price": "149.00",
        "min_stock_level": "5.00",
    },
    {
        "sku": "MOU-LOG-MX3S",
        "name": "Logitech MX Master 3S Mouse",
        "barcode": "5099206103726",
        "category": "Mobile Accessories",
        "cost_price": "62.00",
        "sale_price": "79.90",
        "min_stock_level": "8.00",
    },
    {
        "sku": "HUB-ANK-555-8IN1",
        "name": "Anker 555 USB-C Hub 8-in-1",
        "barcode": "0194644090123",
        "category": "Mobile Accessories",
        "cost_price": "49.00",
        "sale_price": "64.50",
        "min_stock_level": "6.00",
    },
    {
        "sku": "CHR-SAM-25W-USBC",
        "name": "Samsung 25W USB-C Wall Charger",
        "barcode": "8806090973334",
        "category": "Mobile Accessories",
        "cost_price": "12.50",
        "sale_price": "18.00",
        "min_stock_level": "15.00",
    },
    {
        "sku": "PAP-DP-A4-80G",
        "name": "Double A A4 Copy Paper 80gsm",
        "barcode": "8858741710128",
        "category": "Paper & Notebooks",
        "cost_price": "3.10",
        "sale_price": "4.25",
        "min_stock_level": "40.00",
    },
    {
        "sku": "NTB-MOL-A5-BLK",
        "name": "Moleskine Classic A5 Notebook",
        "barcode": "8058647629484",
        "category": "Paper & Notebooks",
        "cost_price": "10.50",
        "sale_price": "14.95",
        "min_stock_level": "12.00",
    },
    {
        "sku": "PEN-PIL-G2-07-BLK",
        "name": "Pilot G2 0.7 Black Gel Pen",
        "barcode": "4902505163166",
        "category": "Writing Tools",
        "cost_price": "0.85",
        "sale_price": "1.35",
        "min_stock_level": "50.00",
    },
    {
        "sku": "MRK-STB-BOSS-4PK",
        "name": "Stabilo Boss Highlighter Set of 4",
        "barcode": "4006381215715",
        "category": "Writing Tools",
        "cost_price": "3.40",
        "sale_price": "4.75",
        "min_stock_level": "20.00",
    },
    {
        "sku": "CHR-ERG-MESH-BLK",
        "name": "Ergonomic Mesh Office Chair",
        "barcode": "6251001234501",
        "category": "Office Furniture",
        "cost_price": "78.00",
        "sale_price": "109.00",
        "min_stock_level": "5.00",
    },
    {
        "sku": "DSK-STD-140-WAL",
        "name": "Walnut Office Desk 140cm",
        "barcode": "6251001234518",
        "category": "Office Furniture",
        "cost_price": "95.00",
        "sale_price": "135.00",
        "min_stock_level": "3.00",
    },
]

WAREHOUSE_DATA = [
    {
        "code": "WH-AMM-MAIN",
        "name": "Amman Main Warehouse",
        "address": "Sahab Industrial Area, Amman",
    },
    {
        "code": "WH-IRB-NORTH",
        "name": "Irbid North Warehouse",
        "address": "Al-Hassan Industrial Estate, Irbid",
    },
]


def seed_catalog(db) -> tuple[int, int]:
    categories: dict[str, Category] = {}
    created_categories = 0
    for name, _ in CATEGORY_DATA:
        category = db.scalar(select(Category).where(Category.name == name))
        if category is None:
            category = Category(name=name)
            db.add(category)
            created_categories += 1
        categories[name] = category

    db.flush()
    for name, parent_name in CATEGORY_DATA:
        category = categories[name]
        expected_parent_id = categories[parent_name].id if parent_name else None
        if category.parent_id != expected_parent_id:
            category.parent_id = expected_parent_id

    created_products = 0
    for item in PRODUCT_DATA:
        product = db.scalar(select(Product).where(Product.sku == item["sku"]))
        if product is not None:
            continue
        product = Product(
            sku=item["sku"],
            name=item["name"],
            barcode=item["barcode"],
            category_id=categories[item["category"]].id,
            cost_price=Decimal(item["cost_price"]),
            sale_price=Decimal(item["sale_price"]),
            min_stock_level=Decimal(item["min_stock_level"]),
        )
        db.add(product)
        created_products += 1
    return created_categories, created_products


def seed_warehouses(db) -> int:
    created_count = 0
    for item in WAREHOUSE_DATA:
        warehouse = db.scalar(select(Warehouse).where(Warehouse.code == item["code"]))
        if warehouse is not None:
            continue
        db.add(Warehouse(**item))
        created_count += 1
    return created_count


def seed_inventory(db, *, admin_id: int) -> int:
    products = list(db.scalars(select(Product).where(Product.is_active.is_(True))).all())
    warehouses = list(db.scalars(select(Warehouse).where(Warehouse.is_active.is_(True))).all())
    created_count = 0
    for product in products:
        for warehouse in warehouses:
            existing = db.scalar(
                select(StockLevel).where(
                    StockLevel.product_id == product.id,
                    StockLevel.warehouse_id == warehouse.id,
                )
            )
            if existing is not None:
                continue
            demo_quantities = DEMO_LOW_STOCK.get(product.sku)
            warehouse_index = warehouses.index(warehouse)
            quantity = (
                demo_quantities[warehouse_index]
                if demo_quantities and warehouse_index < len(demo_quantities)
                else Decimal(
                    (sum(ord(character) for character in product.sku) + warehouse.id * 13) % 61
                )
            )
            db.add(
                StockLevel(
                    product_id=product.id,
                    warehouse_id=warehouse.id,
                    quantity=quantity,
                )
            )
            if quantity > 0:
                db.add(
                    StockMovement(
                        product_id=product.id,
                        warehouse_id=warehouse.id,
                        type="in",
                        quantity=quantity,
                        reference_type="opening_stock",
                        reason="Development seed opening stock",
                        created_by=admin_id,
                    )
                )
            created_count += 1
    return created_count


def seed() -> None:
    with SessionLocal() as db:
        permissions: list[Permission] = []
        permissions_by_code: dict[str, Permission] = {}
        for code, description in PERMISSIONS.items():
            permission = db.scalar(select(Permission).where(Permission.code == code))
            if permission is None:
                permission = Permission(code=code, description=description)
                db.add(permission)
            permissions.append(permission)
            permissions_by_code[code] = permission

        roles: dict[str, Role] = {}
        for name in ROLE_NAMES:
            role = db.scalar(select(Role).where(Role.name == name))
            if role is None:
                role = Role(name=name, description=name.replace("_", " ").title())
                db.add(role)
            roles[name] = role

        db.flush()
        roles["admin"].permissions = permissions
        for role_name, codes in ROLE_PERMISSIONS.items():
            roles[role_name].permissions = [permissions_by_code[code] for code in codes]

        admin = db.scalar(select(User).where(User.username == "admin"))
        if admin is None:
            admin = User(
                username="admin",
                first_name="System",
                last_name="Administrator",
                email="admin@example.com",
                hashed_password=hash_password("Passw0rd!"),
                roles=[roles["admin"]],
            )
            db.add(admin)
        elif admin.email != "admin@example.com":
            admin.email = "admin@example.com"

        for username, (first_name, last_name, role_name) in DEMO_USERS.items():
            user = db.scalar(select(User).where(User.username == username))
            if user is None:
                user = User(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    email=f"{username}@example.com",
                    hashed_password=hash_password(DEMO_PASSWORD),
                )
                db.add(user)
            else:
                user.first_name = first_name
                user.last_name = last_name
                user.email = f"{username}@example.com"
                user.hashed_password = hash_password(DEMO_PASSWORD)
                user.is_active = True
            user.roles = [roles[role_name]]

        created_categories, created_products = seed_catalog(db)
        created_warehouses = seed_warehouses(db)
        db.flush()
        created_stock_levels = seed_inventory(db, admin_id=admin.id)
        db.commit()
        print(
            "Seed complete. "
            f"Added {created_categories} categories, {created_products} products, "
            f"and {created_warehouses} warehouses. "
            f"Added {created_stock_levels} stock levels. "
            "Demo logins use password Passw0rd!: admin, purchasing, sales, "
            "warehouse, accountant, manager."
        )


if __name__ == "__main__":
    seed()
