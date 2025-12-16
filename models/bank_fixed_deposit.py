# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class BankFixedDeposit(models.Model):
    _name = 'bank.fixed.deposit'
    _description = 'Fixed Deposit / Savings Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'opening_date desc, id desc'
    _rec_name = 'fd_number'

    # FD Information
    fd_number = fields.Char(string='FD Number', required=True, 
                           copy=False, readonly=True, 
                           default=lambda self: 'New')
    opening_date = fields.Date(string='Opening Date', required=True, 
                              default=fields.Date.today, tracking=True)
    
    # Customer & Account
    customer_id = fields.Many2one('bank.customer', string='Customer', 
                                 required=True, ondelete='restrict', tracking=True)
    source_account_id = fields.Many2one('bank.account', string='Source Account', 
                                       required=True, ondelete='restrict', tracking=True)
    
    # FD Type
    fd_type = fields.Selection([
        ('fixed_deposit', 'Fixed Deposit'),
        ('recurring_deposit', 'Recurring Deposit'),
        ('savings_plan', 'Savings Plan'),
    ], string='Type', required=True, default='fixed_deposit', tracking=True)
    
    # Amount
    principal_amount = fields.Monetary(string='Principal Amount', 
                                      currency_field='currency_id', 
                                      required=True, tracking=True)
    interest_earned = fields.Monetary(string='Interest Earned', 
                                     currency_field='currency_id', 
                                     compute='_compute_interest_earned', store=True)
    maturity_amount = fields.Monetary(string='Maturity Amount', 
                                     currency_field='currency_id', 
                                     compute='_compute_maturity_amount', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 required=True, 
                                 default=lambda self: self.env.company.currency_id)
    
    # Interest
    interest_rate = fields.Float(string='Interest Rate (% p.a.)', required=True, 
                                digits=(5, 2), tracking=True)
    interest_payout = fields.Selection([
        ('maturity', 'On Maturity'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ], string='Interest Payout', default='maturity', required=True)
    
    # Tenure
    tenure_months = fields.Integer(string='Tenure (Months)', required=True, tracking=True)
    maturity_date = fields.Date(string='Maturity Date', compute='_compute_maturity_date', 
                               store=True, tracking=True)
    
    # Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('matured', 'Matured'),
        ('closed', 'Closed'),
        ('premature_closed', 'Premature Closed'),
    ], string='Status', default='draft', tracking=True)
    
    # Closure
    closure_date = fields.Date(string='Closure Date')
    closure_amount = fields.Monetary(string='Closure Amount', currency_field='currency_id')
    premature_penalty = fields.Float(string='Premature Closure Penalty (%)', 
                                    default=1.0, digits=(5, 2))
    
    # Auto Renewal
    auto_renew = fields.Boolean(string='Auto Renew', default=False)
    renewed_from_id = fields.Many2one('bank.fixed.deposit', string='Renewed From')
    renewed_to_id = fields.Many2one('bank.fixed.deposit', string='Renewed To')
    
    # Nominee
    nominee_name = fields.Char(string='Nominee Name')
    nominee_relation = fields.Char(string='Nominee Relation')
    
    _sql_constraints = [
        ('principal_amount_positive', 'CHECK(principal_amount > 0)', 'Principal amount must be positive!'),
        ('tenure_positive', 'CHECK(tenure_months > 0)', 'Tenure must be positive!'),
    ]
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('fd_number', 'New') == 'New':
                vals['fd_number'] = self.env['ir.sequence'].next_by_code('bank.fixed.deposit') or 'New'
        return super(BankFixedDeposit, self).create(vals_list)
    
    @api.depends('opening_date', 'tenure_months')
    def _compute_maturity_date(self):
        for record in self:
            if record.opening_date and record.tenure_months:
                record.maturity_date = record.opening_date + relativedelta(months=record.tenure_months)
            else:
                record.maturity_date = False
    
    @api.depends('principal_amount', 'interest_rate', 'tenure_months', 'opening_date')
    def _compute_interest_earned(self):
        """Calculate interest earned"""
        for record in self:
            if record.principal_amount and record.interest_rate and record.tenure_months:
                P = record.principal_amount
                r = record.interest_rate / 100
                t = record.tenure_months / 12  # Convert to years
                
                # Simple interest for now (can be changed to compound)
                interest = P * r * t
                record.interest_earned = round(interest, 2)
            else:
                record.interest_earned = 0.0
    
    @api.depends('principal_amount', 'interest_earned')
    def _compute_maturity_amount(self):
        for record in self:
            record.maturity_amount = record.principal_amount + record.interest_earned
    
    def action_activate(self):
        """Activate FD"""
        for record in self:
            # Check source account balance
            if record.source_account_id.available_balance < record.principal_amount:
                raise ValidationError('Insufficient balance in source account.')
            
            # Debit from source account
            txn = self.env['bank.transaction'].create({
                'account_id': record.source_account_id.id,
                'transaction_type': 'withdrawal',
                'amount': record.principal_amount,
                'description': f'FD opened - {record.fd_number}',
                'reference': record.fd_number,
                'status': 'pending',
            })
            txn.action_complete()
            
            record.status = 'active'
            record.message_post(body='Fixed Deposit activated')
            
            # Send notification
            self.env['bank.notification'].create({
                'customer_id': record.customer_id.id,
                'notification_type': 'email',
                'subject': 'FD Opened',
                'message': f'Your FD of {record.principal_amount} has been opened. Maturity date: {record.maturity_date}',
            })
    
    def action_mature(self):
        """Mature FD"""
        for record in self:
            if record.status != 'active':
                raise ValidationError('Only active FDs can be matured.')
            
            record.status = 'matured'
            record.message_post(body=f'FD matured. Maturity amount: {record.maturity_amount}')
            
            # Send notification
            self.env['bank.notification'].create({
                'customer_id': record.customer_id.id,
                'notification_type': 'sms',
                'subject': 'FD Matured',
                'message': f'Your FD {record.fd_number} has matured. Amount: {record.maturity_amount}',
            })
            
            # Auto-renew if enabled
            if record.auto_renew:
                record.action_renew()
    
    def action_renew(self):
        """Renew FD"""
        self.ensure_one()
        
        if self.status != 'matured':
            raise ValidationError('Only matured FDs can be renewed.')
        
        # Create new FD
        new_fd = self.create({
            'customer_id': self.customer_id.id,
            'source_account_id': self.source_account_id.id,
            'fd_type': self.fd_type,
            'principal_amount': self.maturity_amount,
            'interest_rate': self.interest_rate,
            'tenure_months': self.tenure_months,
            'interest_payout': self.interest_payout,
            'auto_renew': self.auto_renew,
            'renewed_from_id': self.id,
        })
        
        self.renewed_to_id = new_fd.id
        new_fd.action_activate()
        
        self.message_post(body=f'FD renewed to {new_fd.fd_number}')
        
        return new_fd
    
    def action_close(self):
        """Close FD and credit to account"""
        for record in self:
            if record.status not in ['active', 'matured']:
                raise ValidationError('Cannot close FD in current status.')
            
            # Calculate closure amount
            if record.status == 'matured':
                closure_amount = record.maturity_amount
            else:
                # Premature closure - apply penalty
                penalty_amount = record.interest_earned * (record.premature_penalty / 100)
                closure_amount = record.principal_amount + record.interest_earned - penalty_amount
                record.status = 'premature_closed'
            
            record.closure_amount = closure_amount
            record.closure_date = fields.Date.today()
            
            # Credit to source account
            txn = self.env['bank.transaction'].create({
                'account_id': record.source_account_id.id,
                'transaction_type': 'deposit',
                'amount': closure_amount,
                'description': f'FD closure - {record.fd_number}',
                'reference': record.fd_number,
                'status': 'pending',
            })
            txn.action_complete()
            
            if record.status != 'premature_closed':
                record.status = 'closed'
            
            record.message_post(body=f'FD closed. Amount credited: {closure_amount}')
    
    @api.model
    def cron_check_maturity(self):
        """Cron job to check and mature FDs"""
        today = fields.Date.today()
        matured_fds = self.search([
            ('status', '=', 'active'),
            ('maturity_date', '<=', today)
        ])
        
        for fd in matured_fds:
            fd.action_mature()
