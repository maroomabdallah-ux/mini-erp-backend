# Mini ERP Backend

Backend service built with FastAPI, SQLAlchemy 2.0, PostgreSQL, Alembic, JWT authentication, and role-based access control (RBAC).

The currently completed scope includes project setup, users, authentication, roles, permissions, refresh-token revocation, audit logging, categories, and products.

## 1. Run the Project

From the project root directory, start PostgreSQL and the API:

```bash
docker compose up -d postgres api


cd /Users/apple/miniERPsystem
source .venv/bin/activate
cd backend
uvicorn app.main:app --reload
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

Permissions implemented in Phase 1:

| Code | Purpose |
|---|---|
| `users.manage` | List, create, update, deactivate users, and reset passwords |
| `roles.manage` | List and create roles, and assign permissions |
| `audit.read` | Read audit logs |

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

## 20. Important HTTP Status Codes

| Status | Meaning |
|---|---|
| `401` | Missing, invalid, or expired token; or invalid login credentials |
| `403` | Missing permission or deactivated account |
| `404` | Requested user or role does not exist |
| `409` | Username, email, or role name already exists |
| `422` | Validation or business-rule failure |

Standard error envelope:

```json
{
  "detail": "Error description",
  "code": "ERROR_CODE",
  "field_errors": {}
}
```

## 21. Recommended Test Flow

Test the complete feature in this order:

```text
POST /auth/login
GET /auth/me
GET /roles
POST /roles
PUT /roles/{role_id}/permissions
POST /users
PUT /users/{user_id}
GET /users/{user_id}
GET /audit-logs
POST /auth/refresh
POST /auth/logout
```

## 22. Quality Checks

Run tests:

```bash
docker compose run --rm api pytest
```

Run Ruff:

```bash
docker compose run --rm api ruff check app tests
```

Run mypy on the implemented modules:

```bash
docker compose run --rm api mypy app/core app/db app/features/users app/features/audit app/main.py app/routers.py app/seed.py
```

Every database schema change must be delivered through an Alembic migration. Apply migrations to a fresh database before considering a feature complete.
