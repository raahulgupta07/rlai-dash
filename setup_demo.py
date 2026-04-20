"""
Demo Data Setup
===============

Creates 2 demo projects with sample data for testing:
1. Sales Agent — orders, customers, products
2. Finance Agent — invoices, expenses, revenue

Usage: python setup_demo.py
"""

import csv
import io
import random
import requests
from datetime import datetime, timedelta

BASE = "http://localhost:8001"

DEMO_USER = "demo"
DEMO_PASS = "demo1234"

# --- Register demo user ---
print(f"Registering user '{DEMO_USER}'...")
r = requests.post(f"{BASE}/api/auth/register", json={"username": DEMO_USER, "password": DEMO_PASS})
if r.status_code == 409:
    print(f"User '{DEMO_USER}' already exists, skipping registration")
elif r.status_code != 200:
    print(f"Registration failed: {r.text}")
    exit(1)
else:
    print(f"Registered user: {DEMO_USER}")

# --- Login as demo user ---
print(f"Logging in as {DEMO_USER}...")
r = requests.post(f"{BASE}/api/auth/login", json={"username": DEMO_USER, "password": DEMO_PASS})
if r.status_code != 200:
    print(f"Login failed: {r.text}")
    exit(1)
token = r.json()["token"]
headers = {"Authorization": f"Bearer {token}"}
print(f"Logged in. Token: {token[:20]}...")


def make_csv(headers_list, rows):
    """Build CSV bytes from headers + rows."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers_list)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode()


# ==========================================================================
# PROJECT 1: SALES
# ==========================================================================
print("\n--- Creating Sales Project ---")

r = requests.post(f"{BASE}/api/projects", headers=headers, params={
    "name": "Sales Demo",
    "agent_name": "Sales Agent",
    "agent_role": "Sales data analyst specializing in orders, customers, and product performance",
    "agent_personality": "sharp and results-oriented"
})
if r.status_code == 409:
    print("Sales project already exists, skipping creation")
    sales_slug = f"proj_{DEMO_USER}_sales_demo"
else:
    sales_slug = r.json()["slug"]
    print(f"Created: {sales_slug}")

# --- Customers ---
print("Uploading customers...")
regions = ["North", "South", "East", "West"]
segments = ["Enterprise", "SMB", "Startup", "Government"]
customers = []
for i in range(1, 201):
    customers.append([
        i,
        f"Customer_{i:03d}",
        f"customer{i}@example.com",
        random.choice(regions),
        random.choice(segments),
        (datetime(2023, 1, 1) + timedelta(days=random.randint(0, 700))).strftime("%Y-%m-%d"),
        random.choice(["active", "active", "active", "churned", "paused"]),
    ])
csv_data = make_csv(["customer_id", "name", "email", "region", "segment", "signup_date", "status"], customers)
r = requests.post(f"{BASE}/api/upload", headers=headers,
    params={"table_name": "customers", "project": sales_slug},
    files={"file": ("customers.csv", csv_data, "text/csv")})
print(f"  customers: {r.status_code}")

# --- Products ---
print("Uploading products...")
categories = ["Electronics", "Software", "Services", "Hardware", "Consulting"]
products = []
for i in range(1, 51):
    cat = random.choice(categories)
    price = round(random.uniform(50, 5000), 2)
    products.append([i, f"{cat} Product {i}", cat, price, random.choice(["active", "discontinued"])])
csv_data = make_csv(["product_id", "product_name", "category", "unit_price", "status"], products)
r = requests.post(f"{BASE}/api/upload", headers=headers,
    params={"table_name": "products", "project": sales_slug},
    files={"file": ("products.csv", csv_data, "text/csv")})
print(f"  products: {r.status_code}")

# --- Orders ---
print("Uploading orders...")
orders = []
for i in range(1, 1001):
    cust_id = random.randint(1, 200)
    prod_id = random.randint(1, 50)
    qty = random.randint(1, 20)
    price = products[prod_id - 1][3]
    total = round(qty * price, 2)
    order_date = (datetime(2024, 1, 1) + timedelta(days=random.randint(0, 450))).strftime("%Y-%m-%d")
    status = random.choice(["completed", "completed", "completed", "pending", "cancelled", "refunded"])
    orders.append([i, cust_id, prod_id, qty, price, total, order_date, status])
csv_data = make_csv(["order_id", "customer_id", "product_id", "quantity", "unit_price", "total_amount", "order_date", "status"], orders)
r = requests.post(f"{BASE}/api/upload", headers=headers,
    params={"table_name": "orders", "project": sales_slug},
    files={"file": ("orders.csv", csv_data, "text/csv")})
print(f"  orders: {r.status_code}")


# ==========================================================================
# PROJECT 2: FINANCE
# ==========================================================================
print("\n--- Creating Finance Project ---")

r = requests.post(f"{BASE}/api/projects", headers=headers, params={
    "name": "Finance Demo",
    "agent_name": "Finance Agent",
    "agent_role": "Financial analyst specializing in invoices, expenses, revenue tracking, and budget analysis",
    "agent_personality": "precise and analytical"
})
if r.status_code == 409:
    print("Finance project already exists, skipping creation")
    finance_slug = f"proj_{DEMO_USER}_finance_demo"
else:
    finance_slug = r.json()["slug"]
    print(f"Created: {finance_slug}")

# --- Invoices ---
print("Uploading invoices...")
departments = ["Engineering", "Marketing", "Sales", "Operations", "HR", "Legal"]
invoices = []
for i in range(1, 501):
    amount = round(random.uniform(500, 50000), 2)
    inv_date = (datetime(2024, 1, 1) + timedelta(days=random.randint(0, 450))).strftime("%Y-%m-%d")
    due_date = (datetime.strptime(inv_date, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d")
    status = random.choice(["paid", "paid", "paid", "overdue", "pending", "cancelled"])
    invoices.append([
        f"INV-{i:04d}", f"Vendor_{random.randint(1, 50):03d}",
        amount, inv_date, due_date, status,
        random.choice(departments),
    ])
csv_data = make_csv(["invoice_id", "vendor", "amount", "invoice_date", "due_date", "status", "department"], invoices)
r = requests.post(f"{BASE}/api/upload", headers=headers,
    params={"table_name": "invoices", "project": finance_slug},
    files={"file": ("invoices.csv", csv_data, "text/csv")})
print(f"  invoices: {r.status_code}")

# --- Expenses ---
print("Uploading expenses...")
expense_cats = ["Travel", "Software", "Office Supplies", "Marketing", "Salaries", "Utilities", "Equipment"]
expenses = []
for i in range(1, 801):
    amount = round(random.uniform(50, 15000), 2)
    exp_date = (datetime(2024, 1, 1) + timedelta(days=random.randint(0, 450))).strftime("%Y-%m-%d")
    expenses.append([
        i, random.choice(expense_cats), amount, exp_date,
        random.choice(departments),
        random.choice(["approved", "approved", "pending", "rejected"]),
        f"Employee_{random.randint(1, 100):03d}",
    ])
csv_data = make_csv(["expense_id", "category", "amount", "expense_date", "department", "status", "submitted_by"], expenses)
r = requests.post(f"{BASE}/api/upload", headers=headers,
    params={"table_name": "expenses", "project": finance_slug},
    files={"file": ("expenses.csv", csv_data, "text/csv")})
print(f"  expenses: {r.status_code}")

# --- Monthly Revenue ---
print("Uploading monthly revenue...")
revenue = []
months = []
base_rev = 500000
for m in range(24):
    dt = datetime(2023, 7, 1) + timedelta(days=m * 30)
    month_str = dt.strftime("%Y-%m")
    growth = 1 + random.uniform(-0.05, 0.10)
    base_rev = round(base_rev * growth, 2)
    revenue.append([
        month_str,
        round(base_rev, 2),
        round(base_rev * random.uniform(0.6, 0.85), 2),
        round(base_rev * random.uniform(0.1, 0.25), 2),
        round(base_rev - base_rev * random.uniform(0.6, 0.85), 2),
    ])
csv_data = make_csv(["month", "total_revenue", "recurring_revenue", "new_revenue", "gross_profit"], revenue)
r = requests.post(f"{BASE}/api/upload", headers=headers,
    params={"table_name": "monthly_revenue", "project": finance_slug},
    files={"file": ("monthly_revenue.csv", csv_data, "text/csv")})
print(f"  monthly_revenue: {r.status_code}")

# --- Budget ---
print("Uploading budgets...")
budgets = []
for dept in departments:
    for q in ["Q1-2024", "Q2-2024", "Q3-2024", "Q4-2024", "Q1-2025"]:
        allocated = round(random.uniform(50000, 500000), 2)
        spent = round(allocated * random.uniform(0.5, 1.1), 2)
        budgets.append([dept, q, allocated, spent, round(allocated - spent, 2)])
csv_data = make_csv(["department", "quarter", "budget_allocated", "budget_spent", "budget_remaining"], budgets)
r = requests.post(f"{BASE}/api/upload", headers=headers,
    params={"table_name": "budgets", "project": finance_slug},
    files={"file": ("budgets.csv", csv_data, "text/csv")})
print(f"  budgets: {r.status_code}")


print("\n" + "=" * 60)
print("DEMO SETUP COMPLETE")
print("=" * 60)
print(f"\nSales Project:   {sales_slug}")
print(f"  Tables: customers (200 rows), products (50 rows), orders (1000 rows)")
print(f"\nFinance Project: {finance_slug}")
print(f"  Tables: invoices (500 rows), expenses (800 rows), monthly_revenue (24 rows), budgets (30 rows)")
print(f"\nLogin: {DEMO_USER} / {DEMO_PASS}")
print(f"URL:   http://localhost:8001")
print(f"\nTest queries:")
print(f"  Sales:   'What is the total revenue?' / 'Top 10 customers by order value'")
print(f"  Finance: 'Show monthly revenue trend' / 'Which department overspent their budget?'")
print(f"  Dash Agent: 'Compare sales and finance performance' (should route correctly)")
