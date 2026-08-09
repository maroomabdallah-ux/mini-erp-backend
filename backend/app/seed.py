"""Idempotent development seed data for RBAC and implemented business data."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.features.accounting.service import post_entry
from app.features.billing.models import Invoice, InvoiceItem, Payment
from app.features.customers.models import Customer
from app.features.inventory.models import StockLevel, StockMovement
from app.features.products.models import Category, Product
from app.features.suppliers.models import Supplier
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
    for index in range(len(PRODUCT_DATA) + 1, 51):
        sku = f"DEMO-{index:03d}"
        if db.scalar(select(Product).where(Product.sku == sku)) is not None:
            continue
        cost = Decimal(5 + index)
        db.add(
            Product(
                sku=sku,
                name=f"Demo Catalog Product {index:03d}",
                barcode=f"990000000{index:03d}",
                category_id=categories["Office Supplies"].id,
                cost_price=cost,
                sale_price=(cost * Decimal("1.35")).quantize(Decimal("0.01")),
                min_stock_level=5,
            )
        )
        created_products += 1
    return created_categories, created_products


def seed_partners(db) -> tuple[int, int]:
    suppliers = 0
    customers = 0
    for index in range(1, 11):
        email = f"supplier{index:02d}@example.com"
        if db.scalar(select(Supplier).where(Supplier.email == email)) is None:
            db.add(
                Supplier(
                    name=f"Demo Supplier {index:02d}",
                    email=email,
                    phone=f"+9626555{index:04d}",
                    credit_terms="Net 30",
                )
            )
            suppliers += 1
    for index in range(1, 21):
        code = f"CUST-{index:04d}"
        if db.scalar(select(Customer).where(Customer.code == code)) is None:
            db.add(
                Customer(
                    code=code,
                    name=f"Demo Customer {index:02d}",
                    contact_person=f"Contact {index:02d}",
                    email=f"customer{index:02d}@example.com",
                    phone=f"+9627955{index:04d}",
                    city="Amman",
                    credit_limit=Decimal("5000.00"),
                )
            )
            customers += 1
    return suppliers, customers


def seed_reporting_history(db, *, admin_id: int) -> int:
    """Create a coherent 12-month sales history for development dashboards."""
    if db.scalar(select(Invoice.id).where(Invoice.notes == "Demo reporting dataset")):
        return 0
    customers = list(
        db.scalars(
            select(Customer)
            .where(Customer.code.like("CUST-%"), Customer.is_active.is_(True))
            .order_by(Customer.id)
            .limit(8)
        ).all()
    )
    products = list(
        db.scalars(
            select(Product)
            .where(Product.is_active.is_(True))
            .order_by(Product.id)
            .limit(10)
        ).all()
    )
    if not customers or len(products) < 2:
        return 0

    month = date.today().replace(day=1)
    months: list[date] = []
    for _ in range(12):
        months.append(month)
        month = (month - timedelta(days=1)).replace(day=1)
    months.reverse()
    created = 0
    for month_index, month_start in enumerate(months):
        for sequence, day in enumerate((6, 19), start=1):
            issue_date = month_start.replace(day=day)
            if issue_date > date.today():
                issue_date = date.today()
            customer = customers[(month_index * 2 + sequence) % len(customers)]
            selected = [
                products[(month_index + sequence) % len(products)],
                products[(month_index + sequence + 3) % len(products)],
            ]
            quantities = (4 + (month_index % 5), 2 + ((month_index + sequence) % 4))
            items = []
            subtotal = Decimal("0")
            for product, quantity in zip(selected, quantities, strict=True):
                line_total = product.sale_price * quantity
                subtotal += line_total
                items.append(
                    InvoiceItem(
                        product_id=product.id,
                        quantity=quantity,
                        unit_price=product.sale_price,
                        line_total=line_total,
                    )
                )
            tax = (subtotal * Decimal("0.16")).quantize(Decimal("0.01"))
            total = subtotal + tax
            is_open = month_index >= 10 and sequence == 2
            is_partial = month_index == 11 and sequence == 1
            paid_amount = (
                (total * Decimal("0.55")).quantize(Decimal("0.01"))
                if is_partial
                else Decimal("0")
                if is_open
                else total
            )
            status = "partially_paid" if is_partial else "issued" if is_open else "paid"
            issued_at = datetime.combine(issue_date, datetime.min.time(), tzinfo=UTC)
            invoice = Invoice(
                number=f"DEMO-INV-{month_start:%Y%m}-{sequence:02d}",
                customer_id=customer.id,
                status=status,
                issue_date=issue_date,
                due_date=issue_date + timedelta(days=30),
                notes="Demo reporting dataset",
                subtotal=subtotal,
                discount_amount=Decimal("0"),
                tax_amount=tax,
                total_amount=total,
                paid_amount=paid_amount,
                created_by=admin_id,
                issued_by=admin_id,
                issued_at=issued_at,
                created_at=issued_at,
                items=items,
            )
            db.add(invoice)
            db.flush()
            post_entry(
                db,
                entry_date=issue_date,
                description=f"Demo sales invoice {invoice.number}",
                source_type="sales_invoice",
                source_id=invoice.id,
                actor_id=admin_id,
                lines=[
                    ("1200", total, Decimal("0"), customer.name),
                    ("4000", Decimal("0"), total, customer.name),
                ],
            )
            if paid_amount > 0:
                payment = Payment(
                    number=f"DEMO-PAY-{month_start:%Y%m}-{sequence:02d}",
                    invoice_id=invoice.id,
                    customer_id=customer.id,
                    amount=paid_amount,
                    payment_date=min(issue_date + timedelta(days=12), date.today()),
                    method="bank_transfer" if sequence == 1 else "cash",
                    reference=f"DEMO-REF-{month_start:%Y%m}-{sequence:02d}",
                    notes="Demo reporting dataset",
                    status="posted",
                    created_by=admin_id,
                )
                db.add(payment)
                db.flush()
                cash_code = "1100" if payment.method == "bank_transfer" else "1000"
                post_entry(
                    db,
                    entry_date=payment.payment_date,
                    description=f"Demo customer payment {payment.number}",
                    source_type="customer_payment",
                    source_id=payment.id,
                    actor_id=admin_id,
                    lines=[
                        (cash_code, paid_amount, Decimal("0"), customer.name),
                        ("1200", Decimal("0"), paid_amount, customer.name),
                    ],
                )
            created += 1
    return created


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
        created_suppliers, created_customers = seed_partners(db)
        db.flush()
        created_stock_levels = seed_inventory(db, admin_id=admin.id)
        created_invoices = seed_reporting_history(db, admin_id=admin.id)
        db.commit()
        print(
            "Seed complete. "
            f"Added {created_categories} categories, {created_products} products, "
            f"and {created_warehouses} warehouses. "
            f"Added {created_suppliers} suppliers and {created_customers} customers. "
            f"Added {created_invoices} historical invoices. "
            f"Added {created_stock_levels} stock levels. "
            "Demo logins use password Passw0rd!: admin, purchasing, sales, "
            "warehouse, accountant, manager."
        )


if __name__ == "__main__":
    seed()
