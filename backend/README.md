# Mini ERP Backend

Backend service built with FastAPI, SQLAlchemy 2.0, PostgreSQL, Alembic, JWT authentication, and role-based access control (RBAC).

The completed scope includes authentication, users, roles, permissions, audit logging, products and categories, suppliers, warehouses, inventory operations, physical counts, purchase orders, goods receipts, customers, and sales quotations.

## 1. Run the Project

From the project root directory, start PostgreSQL and the API:

```bash
docker compose up -d postgres api
```

Apply all database migrations:

```bash
docker compose run --rm api alembic upgrade head
```

Load the development seed data:

```bash
docker compose run --rm api python -m app.seed
```

Check the service status:

```bash
docker compose ps
```

Stop the project:

```bash
docker compose down

cd /Users/apple/miniERPsystem
source .venv/bin/activate
cd backend
uvicorn app.main:app --reload
```

## 2. Important URLs

Swagger UI:

```text
http://localhost:8000/docs
```

Health check:

```text
http://localhost:8000/health
```

## 3. Development Admin Account

```text
Username: admin
Password: Passw0rd!
Email: admin@example.com
```

These credentials are for local development only. Change the password in any shared or production-like environment.

## 4. Login

Endpoint:

```text
POST /auth/login
```

Request body:

```json
{
  "login": "admin",
  "password": "Passw0rd!"
}
```

The `login` field accepts either a username or an email address.

Example response:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "user": {}
}
```

## 5. Authorize Swagger UI

After calling `POST /auth/login`:

1. Copy only the value of `access_token`.
2. Click **Authorize** at the top of Swagger UI.
3. Paste the token into the **Value** field.
4. Click **Authorize**.

Do not add the word `Bearer`; Swagger adds it automatically.

## 6. Current User

Endpoint:

```text
GET /auth/me
```

This endpoint returns:

- The authenticated user's profile.
- The roles assigned to the user.
- The user's effective permissions.
- The account status.

The frontend can call this endpoint after a page reload to restore the current session and decide which pages and actions to display.

## 7. Refresh and Logout

Request a new access token:

```text
POST /auth/refresh
```

Request body:

```json
{
  "refresh_token": "REFRESH_TOKEN_HERE"
}
```

Revoke a refresh token and log out:

```text
POST /auth/logout
```

Request body:

```json
{
  "refresh_token": "REFRESH_TOKEN_HERE"
}
```

## 8. List and Get Users

List users with pagination:

```text
GET /users?page=1&size=20
```

Get one user:

```text
GET /users/{user_id}
```

Example:

```text
GET /users/5
```

These operations require:

```text
users.manage
```

## 9. Create a User

Endpoint:

```text
POST /users
```

Request body:

```json
{
  "username": "test_user",
  "first_name": "Test",
  "last_name": "User",
  "email": "test@example.com",
  "password": "Test1234",
  "role_ids": []
}
```

Password requirements:

- At least 8 characters.
- At least one uppercase letter.
- At least one lowercase letter.
- At least one number.

## 10. Update a User

Endpoint:

```text
PUT /users/{user_id}
```

Example for user 5:

```text
PUT /users/5
```

Update only the first name:

```json
{
  "first_name": "Ahmad"
}
```

Update several fields:

```json
{
  "username": "ahmad_ali",
  "first_name": "Ahmad",
  "last_name": "Ali",
  "email": "ahmad@example.com"
}
```

Assign a role to the user:

```json
{
  "role_ids": [4]
}
```

The values in `role_ids` are role database IDs, not role names. Call `GET /roles` to find the correct IDs in the current database.

Sending `role_ids` replaces the user's entire existing role list.

## 11. Deactivate a User and Reset a Password

Soft-deactivate a user:

```text
POST /users/{user_id}/deactivate
```

Reset a user's password:

```text
POST /users/{user_id}/reset-password
```

Request body:

```json
{
  "new_password": "NewPass123"
}
```

A deactivated user cannot log in. Login returns:

```text
403 Forbidden
```

## 12. Roles and Permissions

A role represents a job function, for example:

```text
admin
sales_officer
accountant
warehouse_keeper
```

A permission represents an allowed operation, for example:

```text
users.manage
roles.manage
audit.read
```

The relationship is:

```text
User -> Role -> Permissions
```

## 13. List and Get Roles

List all roles without permission details:

```text
GET /roles
```

Example response:

```json
[
  {
    "id": 2,
    "name": "admin",
    "description": "Admin",
    "is_active": true
  }
]
```

Get one role with its permissions:

```text
GET /roles/{role_id}
```

Example:

```text
GET /roles/2
```

## 14. Create a Role

Endpoint:

```text
POST /roles
```

Request body:

```json
{
  "name": "inventory_supervisor",
  "description": "Manages inventory operations"
}
```

A new role starts without permissions. Assign its permissions in a separate request.

This operation requires:

```text
roles.manage
```

## 15. Replace a Role's Permissions

Endpoint:

```text
PUT /roles/{role_id}/permissions
```

Example for role 2:

```text
PUT /roles/2/permissions
```

Assign permissions with IDs 1, 2, and 3:

```json
{
  "permission_ids": [1, 2, 3]
}
```

Remove every permission from the role:

```json
{
  "permission_ids": []
}
```

This endpoint replaces the role's complete permission list; it does not append to the old list.

Do not assume role or permission IDs are the same in every database. Read the current data before sending IDs.

## 16. Current Permissions

Permissions used by the currently implemented modules:

| Code                       | Purpose                                                        |
| -------------------------- | -------------------------------------------------------------- |
| `users.manage`             | List, create, update, deactivate users, and reset passwords    |
| `roles.manage`             | List and create roles, and assign permissions                  |
| `audit.read`               | Read audit logs                                                |
| `products.read`            | View products and categories                                   |
| `products.manage`          | Create, update, deactivate, and import products and categories |
| `warehouses.read`          | View warehouses                                                |
| `warehouses.manage`        | Create, update, and deactivate warehouses                      |
| `inventory.read`           | View stock levels and movement history                         |
| `inventory.adjust`         | Record manual stock adjustments                                |
| `inventory.transfer`       | Transfer stock between warehouses                              |
| `inventory.count`          | Record physical stock counts                                   |
| `inventory.count.approve`  | Approve physical counts and apply variances                    |
| `inventory.low_stock.read` | View low-stock alerts                                          |

New permissions should be added when their corresponding features and protected endpoints are implemented.

## 17. Seeded Roles

```text
admin
purchasing_officer
sales_officer
warehouse_keeper
accountant
manager
```

The seed assigns the SRS permission matrix to all six built-in roles. Permissions for future modules are ready before those modules are implemented.

## 18. Audit Logs

List audit records:

```text
GET /audit-logs
```

Filtering examples:

```text
GET /audit-logs?user_id=2
GET /audit-logs?action=update
GET /audit-logs?table_name=users
GET /audit-logs?page=1&size=20
```

An audit record can contain:

- The user who performed the action.
- The action type.
- The affected table and record.
- Old and new values.
- The source IP address.
- The action timestamp.

Reading audit logs requires:

```text
audit.read
```

## 19. Categories and Products

Category endpoints:

```text
GET    /categories
POST   /categories
PUT    /categories/{category_id}
DELETE /categories/{category_id}
```

Product endpoints:

```text
GET    /products?page=1&size=20&search=&category_id=&is_active=
GET    /products/{product_id}
POST   /products
PUT    /products/{product_id}
DELETE /products/{product_id}
POST   /products/import
```

Reading requires `products.read`; writing requires `products.manage`.

Example product body:

```json
{
  "sku": "SKU-1001",
  "name": "Sample Product",
  "barcode": "6251234567890",
  "category_id": 1,
  "cost_price": "12.50",
  "sale_price": "19.99",
  "min_stock_level": "5.00"
}
```

CSV imports use `multipart/form-data` with a `file` field and support these headers:

```text
sku,name,barcode,category_id,cost_price,sale_price,min_stock_level
```

The import response contains the number of created rows and field-level errors for every rejected row.

## 20. Warehouses

Warehouse endpoints:

```text
GET    /warehouses?page=1&size=20&search=&is_active=
GET    /warehouses/{warehouse_id}
POST   /warehouses
PUT    /warehouses/{warehouse_id}
DELETE /warehouses/{warehouse_id}
```

Reading requires `warehouses.read`; writing requires `warehouses.manage`.

Example warehouse body:

```json
{
  "code": "WH-AMM-MAIN",
  "name": "Amman Main Warehouse",
  "address": "Sahab Industrial Area, Amman"
}
```

Warehouse codes are normalized to uppercase and must be unique. Deletion is implemented as soft deactivation, and a warehouse holding stock cannot be deactivated.

## 21. Suppliers

Supplier endpoints:

```text
GET    /suppliers?page=1&size=20&search=&is_active=
GET    /suppliers/{supplier_id}
POST   /suppliers
PUT    /suppliers/{supplier_id}
DELETE /suppliers/{supplier_id}
```

Reading requires `suppliers.read`; writing requires `suppliers.manage`.

Example supplier body:

```json
{
  "name": "Jordan Office Solutions",
  "email": "purchasing@jos.example",
  "phone": "+962 6 555 0100",
  "credit_terms": "Net 30"
}
```

Supplier email addresses are validated and normalized to lowercase. Search covers name, email, phone, and credit terms. Deletion is implemented as soft deactivation, and all create, update, and deactivate operations are written to the audit log.

## 22. Customers

Customer endpoints:

```text
GET    /customers?page=1&size=20&search=&is_active=&city=
GET    /customers/cities
GET    /customers/{customer_id}
POST   /customers
PUT    /customers/{customer_id}
DELETE /customers/{customer_id}
```

Customer records receive an automatic `CUS-00001`-style code and store the customer name, contact person, email, phone, address, city, tax number, and approved credit limit. Search covers identity and contact fields, deletion is a soft deactivation, and every write is audited.

Sales officers manage customers. Managers and accountants have read access, while administrators retain full access.

## 23. Sales Quotations

Quotation endpoints:

```text
GET  /quotations?page=1&size=20&search=&status=&customer_id=
GET  /quotations/{quotation_id}
POST /quotations
PUT  /quotations/{quotation_id}
POST /quotations/{quotation_id}/send
POST /quotations/{quotation_id}/accept
POST /quotations/{quotation_id}/reject
POST /quotations/{quotation_id}/expire
```

Sales officers build draft quotations from active customers and products. The backend calculates subtotal, quotation-level discount, tax, and final total. Sent quotations can be recorded as accepted, rejected with a reason, or expired. Only drafts can be edited, every state transition is audited, and quantities are whole units.

Accepted quotations can be converted once into a Sales Order. Quotations never reserve or deduct stock.

### Sales Orders and Delivery

```text
GET  /sales-orders?page=1&size=20&search=&status=&customer_id=
GET  /sales-orders/{sales_order_id}
GET  /sales-orders/{sales_order_id}/availability
POST /quotations/{quotation_id}/convert
POST /sales-orders/{sales_order_id}/confirm
POST /sales-orders/{sales_order_id}/cancel
POST /sales-orders/{sales_order_id}/deliver
```

Conversion freezes the accepted quotation's customer, product lines, prices, discount, tax, and totals in a draft Sales Order. Confirmation marks the order ready for fulfillment without changing inventory. Delivery requires one active warehouse with enough stock for every line; it then deducts all quantities atomically, creates an `SDN-...` delivery record, records immutable outbound stock movements, and prevents repeat delivery. Every transition is permission-controlled and audited.

### Invoices and Customer Payments

```text
GET  /invoices?page=1&size=20&search=&status=&customer_id=&overdue=
GET  /invoices/eligible-orders
GET  /invoices/{invoice_id}
POST /invoices
POST /invoices/{invoice_id}/issue
POST /invoices/{invoice_id}/cancel
POST /invoices/{invoice_id}/payments
POST /payments/{payment_id}/reverse
```

Only delivered Sales Orders can be invoiced, and each order can produce exactly one invoice. The invoice freezes the customer, products, quantities, prices, discount, tax, and totals. Issued invoices accept partial or full payments; the backend calculates paid amount, remaining balance, and status, rejects overpayments, and keeps reversed payments as immutable financial history. Sales Officers generate and issue invoices, Accountants post or reverse payments and cancel unpaid invoices, Managers have read access, and Administrators have full access.

## 24. Inventory Levels and Movements

Inventory endpoints:

```text
GET  /inventory/stock?product_id=&warehouse_id=&search=&page=&size=
GET  /inventory/movements?product_id=&warehouse_id=&movement_type=&date_from=&date_to=
POST /inventory/adjustments
POST /inventory/transfers
GET  /inventory/counts?status=&page=&size=
POST /inventory/counts
POST /inventory/counts/{count_id}/approve
GET  /inventory/low-stock
```

Manual adjustment body:

```json
{
  "product_id": 1,
  "warehouse_id": 1,
  "quantity_change": 5,
  "reason": "Physical count correction"
}
```

Positive changes add stock and negative changes remove stock. Every change locks the affected inventory row, updates the current level, records an immutable movement, and writes an audit entry in one database transaction. Any operation that would create negative stock is rejected with `409 Conflict`.

Transfer body:

```json
{
  "product_id": 1,
  "source_warehouse_id": 1,
  "destination_warehouse_id": 2,
  "quantity": 6,
  "reason": "Replenish secondary location"
}
```

A transfer validates two different active warehouses and sufficient source stock, locks the affected inventory rows, and updates both quantities atomically. It records linked `out` and `in` movements under one generated `TRF-...` reference and writes one audit entry.

Physical counts use a two-step workflow: `inventory.count` records the system snapshot and actual counted quantity as pending; `inventory.count.approve` validates that stock has not changed, applies the variance, records a linked movement, and approves the count. Stale counts are rejected instead of overwriting newer inventory activity.

Reading stock and movements requires `inventory.read`; manual adjustments require `inventory.adjust`; transfers require `inventory.transfer`; physical-count entry requires `inventory.count`; approval requires `inventory.count.approve`; low-stock alerts require `inventory.low_stock.read`.

All inventory quantities and minimum-stock thresholds are whole units. Fractional quantities are rejected with `422 Unprocessable Entity`; prices and monetary values retain two decimal places.

## 25. Purchase Orders and Goods Receipts

Purchase workflow endpoints:

```text
GET  /purchase-orders?page=1&size=20&search=&status=&supplier_id=&created_by=
GET  /purchase-orders/{purchase_order_id}
POST /purchase-orders
PUT  /purchase-orders/{purchase_order_id}
POST /purchase-orders/{purchase_order_id}/submit
POST /purchase-orders/{purchase_order_id}/approve
POST /purchase-orders/{purchase_order_id}/reject
POST /purchase-orders/{purchase_order_id}/cancel
POST /purchase-orders/{purchase_order_id}/receive
GET  /goods-receipts?page=1&size=20
GET  /goods-receipts/{receipt_id}
```

Create a draft purchase order with an active supplier and at least one active product:

```json
{
  "supplier_id": 1,
  "notes": "Monthly replenishment",
  "items": [
    { "product_id": 1, "quantity": 10, "unit_cost": "4.50" },
    { "product_id": 2, "quantity": 5, "unit_cost": "12.00" }
  ]
}
```

Quantities are whole positive units, monetary values use two decimal places, and each product may appear only once per order. The server calculates every line total and the order total.

The controlled workflow is:

```text
draft -> pending_approval -> approved -> received
                          -> rejected
draft / pending_approval / approved -> cancelled
```

Purchasing officers create, edit, submit, and cancel orders. Managers approve or reject pending orders, and the creator cannot approve their own order. Warehouse keepers receive approved orders into one active warehouse. Receiving creates a unique `GRN-...` goods receipt, adds all ordered quantities to stock, records an `in` movement for every item, and marks the order as received in one transaction. An order cannot be received twice.

Reject and cancel requests require a body such as:

```json
{ "reason": "Budget is not approved" }
```

Receiving requires:

```json
{ "warehouse_id": 1, "notes": "Delivery verified" }
```

## 26. Important HTTP Status Codes

| Status | Meaning                                                          |
| ------ | ---------------------------------------------------------------- |
| `401`  | Missing, invalid, or expired token; or invalid login credentials |
| `403`  | Missing permission or deactivated account                        |
| `404`  | Requested user or role does not exist                            |
| `409`  | Username, email, or role name already exists                     |
| `422`  | Validation or business-rule failure                              |

Standard error envelope:

```json
{
  "detail": "Error description",
  "code": "ERROR_CODE",
  "field_errors": {}
}
```

## 27. Recommended Test Flow

Test the complete feature in this order:

```text
POST /auth/login
GET /auth/me
PUT /auth/me
POST /auth/change-password
GET /roles
POST /roles
PUT /roles/{role_id}/permissions
POST /users
PUT /users/{user_id}
GET /users/{user_id}
GET /audit-logs
GET /warehouses
POST /warehouses
GET /inventory/stock
POST /inventory/adjustments
POST /inventory/transfers
GET /inventory/counts
POST /inventory/counts
POST /inventory/counts/{count_id}/approve
GET /inventory/movements
GET /inventory/low-stock
POST /purchase-orders
PUT /purchase-orders/{purchase_order_id}
POST /purchase-orders/{purchase_order_id}/submit
POST /purchase-orders/{purchase_order_id}/approve
POST /purchase-orders/{purchase_order_id}/receive
GET /goods-receipts
POST /auth/refresh
POST /auth/logout
```

## 28. Quality Checks

Run tests:

```bash
docker compose run --rm api pytest
```

Run Ruff:

```bash
docker compose run --rm api ruff check app tests
```

Run mypy:

```bash
docker compose run --rm api mypy app
```

Check for migration drift:

```bash
docker compose run --rm api alembic check
```

Every database schema change must be delivered through an Alembic migration. Apply migrations to a fresh database before considering a feature complete.

## 29. Sales, Billing, and Accounting

The backend implements direct and quotation-based sales orders, warehouse and credit checks at confirmation, delivery stock deduction, immutable issued invoices, linked credit notes, customer and supplier payments, balanced journals, account statements, and source-document timelines.

Accounting provides `/accounting/dashboard`, `/accounts`, `/journal-entries`, `/supplier-payments`, `/supplier-outstanding`, customer/supplier statement endpoints, and `/invoices/{id}/accounting-timeline`. Operational events post journals automatically; manual journals are validated for debit/credit equality. System account codes, types, hierarchy, and active state are protected.

Current Alembic head: `r2q1p0o9n8m7`.
