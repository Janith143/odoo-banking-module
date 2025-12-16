# -*- coding: utf-8 -*-
{
    'name': 'Odoo Bank',
    'version': '19.0.1.0.0',
    'category': 'Banking',
    'summary': 'Comprehensive Banking Management System',
    'description': """
        Odoo Banking Application
        =========================
        Complete banking solution with:
        * Customer Management (KYC)
        * Account Creation & Management
        * Transaction History & Statements
        * Money Transfer (Internal & External)
        * Loan Management
        * Fixed Deposits / Savings Plans
        * Notifications (SMS / Email / Push)
        * Security: Authentication, Encryption
        * Admin Dashboards: Audit Logs, Reporting
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'web',
        'account',
    ],
    'data': [
        # Security
        'security/bank_security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/bank_data.xml',
        'data/email_templates.xml',
        
        # Views
        'views/bank_customer_views.xml',
        'views/bank_account_views.xml',
        'views/bank_transaction_views.xml',
        'views/bank_transfer_views.xml',
        'views/bank_loan_views.xml',
        'views/bank_fixed_deposit_views.xml',
        'views/bank_dashboard_views.xml',
        'views/bank_menus.xml',
        
        # Reports
        'reports/bank_reports.xml',
        'reports/account_statement_template.xml',
        'reports/transaction_receipt_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odoo_bank/static/src/components/**/*.js',
            'odoo_bank/static/src/components/**/*.xml',
            'odoo_bank/static/src/css/bank_dashboard.css',
        ],
    },
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
