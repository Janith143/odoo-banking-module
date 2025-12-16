# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class BankLoan(models.Model):
    _name = 'bank.loan'
    _description = 'Bank Loan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'application_date desc, id desc'
    _rec_name = 'loan_number'

    # Loan Information
    loan_number = fields.Char(string='Loan Number', required=True, 
                             copy=False, readonly=True, 
                             default=lambda self: 'New')
    application_date = fields.Date(string='Application Date', required=True, 
                                  default=fields.Date.today, tracking=True)
    
    # Customer & Account
    customer_id = fields.Many2one('bank.customer', string='Customer', 
                                 required=True, ondelete='restrict', tracking=True)
    account_id = fields.Many2one('bank.account', string='Disbursement Account', 
                                required=True, ondelete='restrict', tracking=True)
    
    # Loan Type
    loan_type = fields.Selection([
        ('personal', 'Personal Loan'),
        ('home', 'Home Loan'),
        ('auto', 'Auto Loan'),
        ('education', 'Education Loan'),
        ('business', 'Business Loan'),
    ], string='Loan Type', required=True, tracking=True)
    
    # Loan Amount
    requested_amount = fields.Monetary(string='Requested Amount', 
                                      currency_field='currency_id', 
                                      required=True, tracking=True)
    approved_amount = fields.Monetary(string='Approved Amount', 
                                     currency_field='currency_id', tracking=True)
    disbursed_amount = fields.Monetary(string='Disbursed Amount', 
                                      currency_field='currency_id', readonly=True)
    outstanding_amount = fields.Monetary(string='Outstanding Amount', 
                                        currency_field='currency_id', 
                                        compute='_compute_outstanding_amount', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 required=True, 
                                 default=lambda self: self.env.company.currency_id)
    
    # Interest & Tenure
    interest_rate = fields.Float(string='Interest Rate (% p.a.)', required=True, 
                                digits=(5, 2), tracking=True)
    tenure_months = fields.Integer(string='Tenure (Months)', required=True, tracking=True)
    emi_amount = fields.Monetary(string='EMI Amount', currency_field='currency_id', 
                                compute='_compute_emi_amount', store=True)
    
    # Dates
    approval_date = fields.Date(string='Approval Date', readonly=True)
    disbursement_date = fields.Date(string='Disbursement Date', readonly=True)
    first_emi_date = fields.Date(string='First EMI Date')
    maturity_date = fields.Date(string='Maturity Date', compute='_compute_maturity_date', store=True)
    
    # Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('disbursed', 'Disbursed'),
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('defaulted', 'Defaulted'),
    ], string='Status', default='draft', tracking=True)
    
    # Approval
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    rejection_reason = fields.Text(string='Rejection Reason')
    
    # Collateral
    collateral_type = fields.Selection([
        ('none', 'No Collateral'),
        ('property', 'Property'),
        ('vehicle', 'Vehicle'),
        ('securities', 'Securities'),
        ('fd', 'Fixed Deposit'),
    ], string='Collateral Type', default='none')
    collateral_value = fields.Monetary(string='Collateral Value', currency_field='currency_id')
    collateral_description = fields.Text(string='Collateral Description')
    
    # Repayment
    total_paid = fields.Monetary(string='Total Paid', currency_field='currency_id', 
                                compute='_compute_total_paid', store=True)
    emi_paid_count = fields.Integer(string='EMIs Paid', compute='_compute_emi_stats', store=True)
    emi_pending_count = fields.Integer(string='EMIs Pending', compute='_compute_emi_stats', store=True)
    
    # Relations
    transaction_ids = fields.One2many('bank.transaction', 'loan_id', string='Transactions')
    
    _sql_constraints = [
        ('requested_amount_positive', 'CHECK(requested_amount > 0)', 'Requested amount must be positive!'),
        ('tenure_positive', 'CHECK(tenure_months > 0)', 'Tenure must be positive!'),
    ]
    
    @api.model
    def create(self, vals):
        if vals.get('loan_number', 'New') == 'New':
            vals['loan_number'] = self.env['ir.sequence'].next_by_code('bank.loan') or 'New'
        return super(BankLoan, self).create(vals)
    
    @api.depends('approved_amount', 'interest_rate', 'tenure_months')
    def _compute_emi_amount(self):
        """Calculate EMI using reducing balance method"""
        for record in self:
            if record.approved_amount and record.interest_rate and record.tenure_months:
                P = record.approved_amount
                r = record.interest_rate / (12 * 100)  # Monthly interest rate
                n = record.tenure_months
                
                if r > 0:
                    # EMI = P * r * (1+r)^n / ((1+r)^n - 1)
                    emi = P * r * pow(1 + r, n) / (pow(1 + r, n) - 1)
                    record.emi_amount = round(emi, 2)
                else:
                    record.emi_amount = P / n
            else:
                record.emi_amount = 0.0
    
    @api.depends('disbursement_date', 'tenure_months')
    def _compute_maturity_date(self):
        for record in self:
            if record.disbursement_date and record.tenure_months:
                record.maturity_date = record.disbursement_date + relativedelta(months=record.tenure_months)
            else:
                record.maturity_date = False
    
    @api.depends('transaction_ids', 'transaction_ids.amount', 'transaction_ids.status')
    def _compute_total_paid(self):
        for record in self:
            completed_txns = record.transaction_ids.filtered(
                lambda t: t.transaction_type == 'loan_repayment' and t.status == 'completed'
            )
            record.total_paid = sum(completed_txns.mapped('amount'))
    
    @api.depends('disbursed_amount', 'total_paid', 'interest_rate', 'tenure_months')
    def _compute_outstanding_amount(self):
        for record in self:
            if record.disbursed_amount:
                # Simple calculation: Total payable - Total paid
                total_payable = record.emi_amount * record.tenure_months
                record.outstanding_amount = total_payable - record.total_paid
            else:
                record.outstanding_amount = 0.0
    
    @api.depends('emi_amount', 'total_paid')
    def _compute_emi_stats(self):
        for record in self:
            if record.emi_amount > 0:
                record.emi_paid_count = int(record.total_paid / record.emi_amount)
                record.emi_pending_count = record.tenure_months - record.emi_paid_count
            else:
                record.emi_paid_count = 0
                record.emi_pending_count = 0
    
    def action_submit(self):
        """Submit loan application"""
        for record in self:
            if record.customer_id.kyc_status != 'approved':
                raise ValidationError('Customer KYC must be approved before applying for loan.')
            record.status = 'submitted'
            record.message_post(body='Loan application submitted')
    
    def action_approve(self):
        """Approve loan"""
        for record in self:
            record.write({
                'status': 'approved',
                'approved_by': self.env.user.id,
                'approval_date': fields.Date.today(),
                'approved_amount': record.requested_amount,  # Can be modified
            })
            record.message_post(body=f'Loan approved for {record.approved_amount}')
            
            # Send notification
            self.env['bank.notification'].create({
                'customer_id': record.customer_id.id,
                'notification_type': 'email',
                'subject': 'Loan Approved',
                'message': f'Your {record.loan_type} loan of {record.approved_amount} has been approved.',
            })
    
    def action_reject(self):
        """Reject loan"""
        for record in self:
            record.status = 'rejected'
            record.message_post(body=f'Loan rejected: {record.rejection_reason}')
    
    def action_disburse(self):
        """Disburse loan amount"""
        for record in self:
            if record.status != 'approved':
                raise ValidationError('Only approved loans can be disbursed.')
            
            # Create disbursement transaction
            txn = self.env['bank.transaction'].create({
                'account_id': record.account_id.id,
                'transaction_type': 'loan_disbursement',
                'amount': record.approved_amount,
                'description': f'Loan disbursement - {record.loan_number}',
                'reference': record.loan_number,
                'loan_id': record.id,
                'status': 'pending',
            })
            txn.action_complete()
            
            record.write({
                'status': 'active',
                'disbursed_amount': record.approved_amount,
                'disbursement_date': fields.Date.today(),
                'first_emi_date': fields.Date.today() + relativedelta(months=1),
            })
            
            record.message_post(body='Loan disbursed successfully')
    
    def action_make_payment(self, amount):
        """Make loan repayment"""
        self.ensure_one()
        
        if self.status not in ['active', 'disbursed']:
            raise ValidationError('Cannot make payment for inactive loan.')
        
        # Create repayment transaction
        txn = self.env['bank.transaction'].create({
            'account_id': self.account_id.id,
            'transaction_type': 'loan_repayment',
            'amount': amount,
            'description': f'Loan repayment - {self.loan_number}',
            'reference': self.loan_number,
            'loan_id': self.id,
            'status': 'pending',
        })
        txn.action_complete()
        
        # Check if loan is fully paid
        if self.outstanding_amount <= 0:
            self.status = 'closed'
            self.message_post(body='Loan fully repaid and closed')
        
        return txn
