# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import random
import string


class BankAccount(models.Model):
    _name = 'bank.account'
    _description = 'Bank Account'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'account_number'

    # Account Information
    account_number = fields.Char(string='Account Number', required=True, 
                                 copy=False, readonly=True, 
                                 default=lambda self: 'New')
    account_name = fields.Char(string='Account Name', required=True, tracking=True)
    account_type = fields.Selection([
        ('savings', 'Savings Account'),
        ('current', 'Current Account'),
        ('fixed_deposit', 'Fixed Deposit'),
        ('loan', 'Loan Account')
    ], string='Account Type', required=True, default='savings', tracking=True)
    
    # Customer
    customer_id = fields.Many2one('bank.customer', string='Customer', 
                                 required=True, ondelete='restrict', tracking=True)
    customer_email = fields.Char(related='customer_id.email', string='Customer Email', readonly=True)
    customer_phone = fields.Char(related='customer_id.phone', string='Customer Phone', readonly=True)
    
    # Balance
    balance = fields.Monetary(string='Balance', currency_field='currency_id', 
                             readonly=True, tracking=True)
    available_balance = fields.Monetary(string='Available Balance', 
                                       currency_field='currency_id', 
                                       compute='_compute_available_balance', store=True)
    hold_amount = fields.Monetary(string='Hold Amount', currency_field='currency_id', 
                                 default=0.0)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 required=True, 
                                 default=lambda self: self.env.company.currency_id)
    
    # Account Details
    opening_date = fields.Date(string='Opening Date', required=True, 
                              default=fields.Date.today, tracking=True)
    closing_date = fields.Date(string='Closing Date')
    branch = fields.Char(string='Branch')
    
    # Interest
    interest_rate = fields.Float(string='Interest Rate (%)', digits=(5, 2))
    last_interest_date = fields.Date(string='Last Interest Calculated')
    
    # Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('frozen', 'Frozen'),
        ('closed', 'Closed')
    ], string='Status', default='draft', tracking=True)
    
    # Relations
    transaction_ids = fields.One2many('bank.transaction', 'account_id', string='Transactions')
    transaction_count = fields.Integer(string='Transaction Count', compute='_compute_transaction_count')
    color = fields.Integer(string='Color Index')
    
    # Security
    pin_hash = fields.Char(string='PIN Hash', groups='base.group_system')
    
    # Limits
    daily_withdrawal_limit = fields.Monetary(string='Daily Withdrawal Limit', 
                                            currency_field='currency_id', 
                                            default=50000.0)
    daily_transfer_limit = fields.Monetary(string='Daily Transfer Limit', 
                                          currency_field='currency_id', 
                                          default=100000.0)
    
    active = fields.Boolean(string='Active', default=True)
    
    _sql_constraints = [
        ('account_number_unique', 'unique(account_number)', 'Account number must be unique!'),
    ]
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('account_number', 'New') == 'New':
                # Generate unique account number
                vals['account_number'] = self._generate_account_number()
        results = super(BankAccount, self).create(vals_list)
        # Log account creation
        for result in results:
            self.env['bank.audit.log'].create({
                'action': 'create',
                'model_name': 'bank.account',
                'record_id': result.id,
                'description': f'Account created: {result.account_number}',
                'user_id': self.env.user.id,
            })
        return results
    
    def _generate_account_number(self):
        """Generate unique 12-digit account number"""
        while True:
            account_number = ''.join(random.choices(string.digits, k=12))
            if not self.search([('account_number', '=', account_number)]):
                return account_number
    
    @api.depends('balance', 'hold_amount')
    def _compute_available_balance(self):
        for record in self:
            record.available_balance = record.balance - record.hold_amount
    
    @api.depends('transaction_ids')
    def _compute_transaction_count(self):
        for record in self:
            record.transaction_count = len(record.transaction_ids)
    
    def action_activate(self):
        """Activate account"""
        for record in self:
            if record.customer_id.kyc_status != 'approved':
                raise ValidationError('Customer KYC must be approved before activating account.')
            record.status = 'active'
            record.message_post(body='Account activated')
            # Send notification
            self.env['bank.notification'].create({
                'customer_id': record.customer_id.id,
                'notification_type': 'email',
                'subject': 'Account Activated',
                'message': f'Your account {record.account_number} has been activated.',
            })
    
    def action_freeze(self):
        """Freeze account"""
        for record in self:
            record.status = 'frozen'
            record.message_post(body='Account frozen')
    
    def action_close(self):
        """Close account"""
        for record in self:
            if record.balance != 0:
                raise ValidationError('Cannot close account with non-zero balance.')
            record.status = 'closed'
            record.closing_date = fields.Date.today()
            record.message_post(body='Account closed')
    
    def action_view_transactions(self):
        """View account transactions"""
        return {
            'name': 'Account Transactions',
            'type': 'ir.actions.act_window',
            'res_model': 'bank.transaction',
            'view_mode': 'list,form',
            'domain': [('account_id', '=', self.id)],
            'context': {'default_account_id': self.id}
        }
    
    def update_balance(self, amount, transaction_type):
        """Update account balance"""
        self.ensure_one()
        if transaction_type in ['deposit', 'credit', 'interest']:
            self.balance += amount
        elif transaction_type in ['withdrawal', 'debit', 'fee']:
            if self.available_balance < amount:
                raise ValidationError('Insufficient balance.')
            self.balance -= amount
        
        # Log balance update
        self.env['bank.audit.log'].create({
            'action': 'update',
            'model_name': 'bank.account',
            'record_id': self.id,
            'description': f'Balance updated: {transaction_type} {amount}. New balance: {self.balance}',
            'user_id': self.env.user.id,
        })
