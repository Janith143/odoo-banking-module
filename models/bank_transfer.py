# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class BankTransfer(models.Model):
    _name = 'bank.transfer'
    _description = 'Bank Transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'transfer_date desc, id desc'
    _rec_name = 'transfer_number'

    # Transfer Information
    transfer_number = fields.Char(string='Transfer Number', required=True, 
                                  copy=False, readonly=True, 
                                  default=lambda self: 'New')
    transfer_date = fields.Datetime(string='Transfer Date', required=True, 
                                   default=fields.Datetime.now, tracking=True)
    
    # Transfer Type
    transfer_type = fields.Selection([
        ('internal', 'Internal Transfer'),
        ('external', 'External Transfer'),
        ('rtgs', 'RTGS'),
        ('neft', 'NEFT'),
        ('imps', 'IMPS'),
    ], string='Transfer Type', required=True, default='internal', tracking=True)
    
    # Source Account
    from_account_id = fields.Many2one('bank.account', string='From Account', 
                                     required=True, ondelete='restrict', tracking=True)
    from_customer_id = fields.Many2one(related='from_account_id.customer_id', 
                                      string='From Customer', readonly=True)
    
    # Destination (Internal)
    to_account_id = fields.Many2one('bank.account', string='To Account', 
                                   ondelete='restrict', tracking=True)
    to_customer_id = fields.Many2one(related='to_account_id.customer_id', 
                                    string='To Customer', readonly=True)
    
    # Destination (External)
    beneficiary_name = fields.Char(string='Beneficiary Name')
    beneficiary_account = fields.Char(string='Beneficiary Account Number')
    beneficiary_bank = fields.Char(string='Beneficiary Bank')
    beneficiary_ifsc = fields.Char(string='IFSC Code')
    
    # Amount
    amount = fields.Monetary(string='Amount', currency_field='currency_id', 
                            required=True, tracking=True)
    fee = fields.Monetary(string='Transfer Fee', currency_field='currency_id', 
                         compute='_compute_fee', store=True)
    total_amount = fields.Monetary(string='Total Amount', currency_field='currency_id', 
                                  compute='_compute_total_amount', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 required=True, 
                                 default=lambda self: self.env.company.currency_id)
    
    # Description
    description = fields.Text(string='Description')
    reference = fields.Char(string='Reference')
    
    # Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    # Approval
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approved_date = fields.Datetime(string='Approved Date', readonly=True)
    rejection_reason = fields.Text(string='Rejection Reason')
    
    # Related Transactions
    debit_transaction_id = fields.Many2one('bank.transaction', string='Debit Transaction', readonly=True)
    credit_transaction_id = fields.Many2one('bank.transaction', string='Credit Transaction', readonly=True)
    
    # External Gateway (Placeholder)
    gateway_reference = fields.Char(string='Gateway Reference', readonly=True)
    gateway_status = fields.Char(string='Gateway Status', readonly=True)
    
    _sql_constraints = [
        ('amount_positive', 'CHECK(amount > 0)', 'Amount must be positive!'),
    ]
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('transfer_number', 'New') == 'New':
                vals['transfer_number'] = self.env['ir.sequence'].next_by_code('bank.transfer') or 'New'
        return super(BankTransfer, self).create(vals_list)
    
    @api.depends('transfer_type', 'amount')
    def _compute_fee(self):
        """Calculate transfer fee based on type"""
        for record in self:
            if record.transfer_type == 'internal':
                record.fee = 0.0
            elif record.transfer_type in ['rtgs', 'neft']:
                record.fee = 25.0 if record.amount < 200000 else 50.0
            elif record.transfer_type == 'imps':
                record.fee = 5.0
            else:
                record.fee = 10.0
    
    @api.depends('amount', 'fee')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = record.amount + record.fee
    
    @api.constrains('from_account_id', 'to_account_id')
    def _check_accounts(self):
        for record in self:
            if record.transfer_type == 'internal':
                if not record.to_account_id:
                    raise ValidationError('Destination account is required for internal transfers.')
                if record.from_account_id == record.to_account_id:
                    raise ValidationError('Source and destination accounts cannot be the same.')
    
    def action_submit(self):
        """Submit transfer for approval"""
        for record in self:
            # Validate
            if record.from_account_id.status != 'active':
                raise ValidationError('Source account is not active.')
            
            if record.from_account_id.available_balance < record.total_amount:
                raise ValidationError('Insufficient balance in source account.')
            
            # Check daily limit
            today_transfers = self.search([
                ('from_account_id', '=', record.from_account_id.id),
                ('transfer_date', '>=', fields.Date.today()),
                ('status', '=', 'completed')
            ])
            total_today = sum(today_transfers.mapped('amount'))
            
            if total_today + record.amount > record.from_account_id.daily_transfer_limit:
                raise ValidationError('Daily transfer limit exceeded.')
            
            # Auto-approve small amounts, otherwise pending
            if record.amount < 100000:
                record.action_approve()
            else:
                record.status = 'pending'
                record.message_post(body='Transfer submitted for approval')
    
    def action_approve(self):
        """Approve transfer"""
        for record in self:
            record.write({
                'status': 'approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now()
            })
            record.message_post(body='Transfer approved')
            # Process immediately
            record.action_process()
    
    def action_reject(self):
        """Reject transfer"""
        for record in self:
            record.status = 'cancelled'
            record.message_post(body=f'Transfer rejected: {record.rejection_reason}')
    
    def action_process(self):
        """Process the transfer"""
        for record in self:
            if record.status != 'approved':
                raise ValidationError('Only approved transfers can be processed.')
            
            record.status = 'processing'
            
            try:
                # Create debit transaction
                debit_txn = self.env['bank.transaction'].create({
                    'account_id': record.from_account_id.id,
                    'transaction_type': 'transfer_out',
                    'amount': record.total_amount,
                    'description': f'Transfer to {record.beneficiary_name or record.to_account_id.account_number}',
                    'reference': record.transfer_number,
                    'transfer_id': record.id,
                    'status': 'pending',
                })
                debit_txn.action_complete()
                record.debit_transaction_id = debit_txn.id
                
                # For internal transfers, create credit transaction
                if record.transfer_type == 'internal' and record.to_account_id:
                    credit_txn = self.env['bank.transaction'].create({
                        'account_id': record.to_account_id.id,
                        'transaction_type': 'transfer_in',
                        'amount': record.amount,
                        'description': f'Transfer from {record.from_account_id.account_number}',
                        'reference': record.transfer_number,
                        'transfer_id': record.id,
                        'status': 'pending',
                    })
                    credit_txn.action_complete()
                    record.credit_transaction_id = credit_txn.id
                
                # For external transfers, simulate gateway call
                elif record.transfer_type in ['external', 'rtgs', 'neft', 'imps']:
                    # Placeholder for external gateway integration
                    record.gateway_reference = f'EXT{record.id}{fields.Datetime.now().strftime("%Y%m%d%H%M%S")}'
                    record.gateway_status = 'SUCCESS'
                
                record.status = 'completed'
                record.message_post(body='Transfer completed successfully')
                
                # Send notification
                self.env['bank.notification'].create({
                    'customer_id': record.from_customer_id.id,
                    'notification_type': 'sms',
                    'subject': 'Transfer Successful',
                    'message': f'Transfer of {record.amount} completed. Ref: {record.transfer_number}',
                })
                
            except Exception as e:
                record.status = 'failed'
                record.message_post(body=f'Transfer failed: {str(e)}')
                raise
    
    def action_cancel(self):
        """Cancel transfer"""
        for record in self:
            if record.status in ['completed', 'processing']:
                raise ValidationError('Cannot cancel completed or processing transfers.')
            record.status = 'cancelled'
