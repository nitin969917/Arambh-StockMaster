# StockMaster - Inventory Management System (IMS)

A comprehensive, modular Inventory Management System designed to digitize and streamline all stock-related operations within a business. StockMaster replaces manual registers, Excel sheets, and scattered tracking methods with a centralized, real-time, easy-to-use web application.

## 📹 Project Video

Watch our project demonstration video: **[Click here to watch the StockMaster IMS Demo Video](https://drive.google.com/file/d/1wYxK3ENx13HbuzlcAS4f7BusgdjBSWBD/view?usp=sharing)**

---

## 🚀 Features

### 🔐 Authentication & User Management
- **Sign Up / Login**: Secure user authentication with custom validation
- **OTP-based Password Reset**: Email-based password reset with OTP verification
- **Role-Based Access Control**: Two user roles with distinct permissions
  - **Inventory Manager**: Full system access, can create receipts and deliveries
  - **Warehouse Staff**: Operational access, can perform transfers and validate deliveries

### 📊 Dashboard
- **Real-time KPIs**: Track receipts, deliveries, and internal transfers
- **Low Stock Alerts**: Automatic alerts when products fall below threshold
- **Operational Overview**: Monitor pending operations, late deliveries, and waiting statuses
- **Warehouse-Specific Data**: Warehouse staff see only their assigned warehouse data

### 📦 Product Management
- **Product CRUD**: Create, read, update products with SKU, category, and unit of measure
- **Low Stock Threshold**: Set alert levels for automatic low stock warnings
- **Product Categories**: Organize products with default and custom categories
- **Active/Inactive Status**: Enable or disable products as needed

### 🏭 Warehouse & Location Management
- **Multi-Warehouse Support**: Create and manage multiple warehouses
- **Location Management**: Define multiple storage locations within each warehouse
- **Warehouse Staff Assignment**: Automatically create warehouse staff accounts when creating warehouses
- **Warehouse Isolation**: Strict data isolation - warehouse staff can only access their assigned warehouse

### 📋 Stock Operations

#### 1. Receipts (Incoming Stock)
- Receive goods from external vendors
- Auto-populate quantities from product initial stock
- Automatic stock update on validation
- Quantity field locked (readonly) during receipt

#### 2. Delivery Orders (Outgoing Stock)
- Ship goods to external customers
- Stock availability checking
- Status workflow: Draft → Waiting → Ready → Done
- Print-friendly delivery notes

#### 3. Internal Transfers
- Move stock between locations within the same warehouse
- Warehouse staff can only transfer within their assigned warehouse
- Auto-validation for past/current scheduled dates
- Real-time stock updates

### 📈 Stock Tracking
- **Stock List**: View available stock per product and location
- **Move History**: Complete ledger of all stock movements
- **Warehouse Filtering**: Filter stock by warehouse and location
- **Search Functionality**: Search by SKU, product name, or reference

### ⚙️ Settings
- **Warehouse Management**: Create and manage warehouses with staff accounts
- **Location Management**: Add locations to warehouses
- **User-Friendly Interface**: Modern, card-based settings page

### 🔒 Security & Data Isolation
- **User-Based Filtering**: Users can only see data they created or related to their warehouse
- **Warehouse Isolation**: Warehouse staff cannot access other warehouses' data
- **Role-Based Permissions**: Different access levels for different user roles
- **Form-Level Validation**: Prevents unauthorized warehouse access at form level

---

## 🛠️ Technology Stack

- **Backend**: Django 5.2.8
- **Database**: SQLite (development) / PostgreSQL (production ready)
- **Frontend**: Bootstrap 5
- **Authentication**: Django Session-based Authentication
- **Email**: SMTP (Gmail) for OTP-based password reset

---

## 📦 Installation

### Prerequisites
- Python 3.8+
- pip (Python package manager)
- Virtual environment (recommended)

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/nitin969917/Arambh-StockMaster.git
   cd Aarambh_StockMaster
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run migrations**
   ```bash
   python manage.py migrate
   ```

5. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

6. **Seed default categories (optional)**
   ```bash
   python manage.py migrate  # Categories are auto-created via migration
   ```

7. **Run the development server**
   ```bash
   python manage.py runserver
   ```

8. **Access the application**
   - Main Application: http://127.0.0.1:8000/
   - Django Admin: http://127.0.0.1:8000/admin/

---

---

## 📖 Usage Guide

### For Inventory Managers

1. **Create Warehouses**
   - Navigate to Settings → Add Warehouse
   - Fill in warehouse details and create warehouse staff account
   - Staff account is automatically created with warehouse assignment

2. **Add Products**
   - Go to Products → New Product
   - Set low stock alert threshold for automatic alerts
   - Stock is created when products are received via Receipt

3. **Create Receipts**
   - Operations → + Receipt
   - Select destination location
   - Add products (quantities auto-populated from initial stock)
   - Stock is automatically updated on save

4. **Create Deliveries**
   - Operations → + Delivery
   - Select source location
   - Add products and quantities
   - Status updates automatically based on stock availability

### For Warehouse Staff

1. **View Stock**
   - Stock tab shows only your warehouse's stock
   - Filter by location and SKU

2. **Internal Transfers**
   - Operations → + Transfer
   - Select source and destination locations (only within your warehouse)
   - System prevents transfers from/to other warehouses

3. **Validate Deliveries**
   - View deliveries from your warehouse
   - Click "Validate" to process and update stock

4. **Move History**
   - View complete history of stock movements in your warehouse

---

## 🗂️ Project Structure

```
Aarambh_StockMaster/
├── accounts/              # User authentication and management
│   ├── models.py         # Custom User model with roles
│   ├── views.py          # Login, signup, password reset
│   ├── forms.py          # Authentication forms
│   └── admin.py          # Django admin configuration
├── inventory/            # Core inventory management
│   ├── models.py         # Product, Warehouse, Location, Stock models
│   ├── views.py          # Dashboard, operations, stock views
│   ├── forms.py          # Product, warehouse, document forms
│   ├── decorators.py     # Role-based access control
│   └── admin.py          # Django admin configuration
├── templates/            # HTML templates
│   ├── base.html         # Base template with navigation
│   ├── accounts/         # Authentication templates
│   └── inventory/        # Inventory management templates
├── stockmaster/          # Django project settings
│   ├── settings.py       # Project configuration
│   ├── urls.py           # Main URL routing
│   └── wsgi.py           # WSGI configuration
└── db.sqlite3            # SQLite database (development)
```

---

## 🔑 Key Features Explained

### Warehouse Isolation
Warehouse staff users are assigned to a specific warehouse during creation. The system enforces strict data isolation:
- Stock lists show only their warehouse's stock
- Operations show only operations involving their warehouse
- Forms prevent selecting locations from other warehouses
- Transfers are restricted to within the same warehouse

### Low Stock Alerts
Products have a `low_stock_alert` field that sets the threshold. When stock at any warehouse falls below this threshold, it appears on the dashboard with visual indicators.

### Automatic Stock Updates
- **Receipts**: Stock increases automatically at destination location
- **Deliveries**: Stock decreases automatically at source location
- **Internal Transfers**: Stock decreases at source, increases at destination
- All movements are logged in the move history ledger

---

