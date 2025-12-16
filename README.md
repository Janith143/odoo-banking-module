# Odoo Bank Module

A comprehensive banking management system for Odoo 19.

## Features

- **Customer Management (KYC)**: Complete KYC verification workflow with document upload
- **Account Management**: Multiple account types (Savings, Current, Fixed Deposit)
- **Transaction Processing**: Deposits, withdrawals, and comprehensive transaction history
- **Money Transfers**: Internal and external transfers with approval workflow
- **Loan Management**: Loan applications, EMI calculation, and repayment tracking
- **Fixed Deposits**: FD creation with interest calculation and maturity tracking
- **Notifications**: Email, SMS, and push notifications
- **Security**: Role-based access control and audit logging
- **Reports**: Account statements, transaction receipts, and loan schedules

## Installation

1. Copy the `odoo_bank` folder to your Odoo addons directory
2. Update the addons list: `odoo-bin -c odoo.conf -u all`
3. Install the module from Apps menu

## Configuration

1. Go to Settings > Users & Companies > Groups
2. Assign users to appropriate banking groups:
   - Bank Customer
   - Bank Teller
   - Bank Manager
   - Bank Administrator

## Usage

Access the Banking menu from the main navigation to:
- Manage customers and KYC
- Create and manage accounts
- Process transactions
- Handle transfers
- Manage loans and fixed deposits
- View audit logs and reports

## Technical Details

- **Odoo Version**: 19.0
- **Python**: Backend models and business logic
- **XML**: Views and reports
- **JavaScript (OWL)**: Frontend components
- **License**: LGPL-3

## Support

For issues or questions, contact your system administrator.

## File Structure

```
odoo_bank/
├── controllers/       # Route handlers and API endpoints
├── data/             # Master data and demo data
├── models/           # Database models and business logic
├── reports/          # QWeb reports and templates
├── security/         # Access rights and security rules
├── static/           # Static assets (CSS, JS, Images)
├── views/            # XML views and user interface
├── CHANGELOG.md      # Version history
├── README.md         # Project documentation
├── __init__.py       # Python package initialization
└── __manifest__.py   # Odoo module manifest
```
