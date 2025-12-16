# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class BankTransaction(models.Model):
    _name = 'bank.transaction'
    _description = 'Bank Transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'transaction_date desc, id desc'
    _rec_name = 'transaction_number'

    # Transaction Information
    transaction_number = fields.Char(string='Transaction Number', required=True, 
                                    copy=False, readonly=True, 
                                    default=lambda self: 'New')
    transaction_date = fields.Datetime(string='Transaction Date', required=True, 
                                      default=fields.Datetime.now, tracking=True)
    
    # Account
    account_id = fields.Many2one('bank.account', string='Account', 
                                required=True, ondelete='restrict', tracking=True)
    customer_id = fields.Many2one(related='account_id.customer_id', 
                                 string='Customer', readonly=True, store=True)
    
    # Transaction Details
    transaction_type = fields.Selection([
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('transfer_in', 'Transfer In'),
        ('transfer_out', 'Transfer Out'),
        ('interest', 'Interest Credit'),
        ('fee', 'Fee/Charge'),
        ('loan_disbursement', 'Loan Disbursement'),
        ('loan_repayment', 'Loan Repayment'),
    ], string='Transaction Type', required=True, tracking=True)
    
    amount = fields.Monetary(string='Amount', currency_field='currency_id', 
                            required=True, tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 required=True, 
                                 default=lambda self: self.env.company.currency_id)
    
    # Balance
    balance_before = fields.Monetary(string='Balance Before', 
                                    currency_field='currency_id', readonly=True)
    balance_after = fields.Monetary(string='Balance After', 
                                   currency_field='currency_id', readonly=True)
    
    # Description
    description = fields.Text(string='Description')
    reference = fields.Char(string='Reference')
    
    # Related Records
    transfer_id = fields.Many2one('bank.transfer', string='Related Transfer')
    loan_id = fields.Many2one('bank.loan', string='Related Loan')
    
    # Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    # Reconciliation
    is_reconciled = fields.Boolean(string='Reconciled', default=False)
    reconciliation_date = fields.Date(string='Reconciliation Date')
    
    _sql_constraints = [
        ('amount_positive', 'CHECK(amount > 0)', 'Amount must be positive!'),
    ]
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('transaction_number', 'New') == 'New':
                vals['transaction_number'] = self.env['ir.sequence'].next_by_code('bank.transaction') or 'New'
            
            # Get account and store balance before
            if vals.get('account_id'):
                account = self.env['bank.account'].browse(vals.get('account_id'))
                vals['balance_before'] = account.balance
        
        results = super(BankTransaction, self).create(vals_list)
        
        # Auto-complete if not draft
        for result in results:
            if result.status != 'draft':
                result.action_complete()
        
        return results
    
    def action_complete(self):
        """Complete transaction and update account balance"""
        for record in self:
            if record.status == 'completed':
                continue
            
            # Update account balance
            if record.transaction_type in ['deposit', 'transfer_in', 'interest', 'loan_disbursement']:
                record.account_id.update_balance(record.amount, 'credit')
            elif record.transaction_type in ['withdrawal', 'transfer_out', 'fee', 'loan_repayment']:
                record.account_id.update_balance(record.amount, 'debit')
            
            # Update balance after
            record.balance_after = record.account_id.balance
            record.status = 'completed'
            
            # Send notification for significant transactions
            if record.amount >= 10000:
                self.env['bank.notification'].create({
                    'customer_id': record.customer_id.id,
                    'notification_type': 'sms',
                    'subject': 'Transaction Alert',
                    'message': f'{record.transaction_type}: {record.amount} on account {record.account_id.account_number}',
                })
    
    def action_cancel(self):
        """Cancel transaction"""
        for record in self:
            if record.status == 'completed':
                raise ValidationError('Cannot cancel completed transaction. Please create a reversal.')
            record.status = 'cancelled'
    
    def action_reverse(self):
        """Create reversal transaction"""
        self.ensure_one()
        if self.status != 'completed':
            raise ValidationError('Can only reverse completed transactions.')
        
        # Determine reversal type
        reversal_type_map = {
            'deposit': 'withdrawal',
            'withdrawal': 'deposit',
            'transfer_in': 'transfer_out',
            'transfer_out': 'transfer_in',
            'interest': 'fee',
            'fee': 'deposit',
        }
        
        reversal = self.create({
            'account_id': self.account_id.id,
            'transaction_type': reversal_type_map.get(self.transaction_type, 'fee'),
            'amount': self.amount,
            'description': f'Reversal of {self.transaction_number}',
            'reference': self.transaction_number,
            'status': 'pending',
        })
        
        reversal.action_complete()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bank.transaction',
            'res_id': reversal.id,
            'view_mode': 'form',
            'target': 'current',
        }
