# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class BankCustomer(models.Model):
    _name = 'bank.customer'
    _description = 'Bank Customer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'full_name'

    # Personal Information
    full_name = fields.Char(string='Full Name', required=True, tracking=True)
    date_of_birth = fields.Date(string='Date of Birth', required=True)
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], string='Gender', required=True)
    email = fields.Char(string='Email', required=True, tracking=True)
    phone = fields.Char(string='Phone', required=True, tracking=True)
    mobile = fields.Char(string='Mobile')
    
    # Address
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street2')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    zip = fields.Char(string='ZIP')
    country_id = fields.Many2one('res.country', string='Country')
    
    # KYC Information
    customer_id = fields.Char(string='Customer ID', required=True, copy=False, 
                             readonly=True, default=lambda self: 'New')
    id_type = fields.Selection([
        ('passport', 'Passport'),
        ('national_id', 'National ID'),
        ('driving_license', 'Driving License'),
        ('voter_id', 'Voter ID')
    ], string='ID Type', required=True)
    id_number = fields.Char(string='ID Number', required=True)
    id_expiry_date = fields.Date(string='ID Expiry Date')
    
    # KYC Documents
    id_document = fields.Binary(string='ID Document', attachment=True)
    id_document_filename = fields.Char(string='ID Document Filename')
    address_proof = fields.Binary(string='Address Proof', attachment=True)
    address_proof_filename = fields.Char(string='Address Proof Filename')
    photo = fields.Binary(string='Photo', attachment=True)
    photo_filename = fields.Char(string='Photo Filename')
    
    # KYC Status
    kyc_status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='KYC Status', default='draft', tracking=True)
    kyc_verified_by = fields.Many2one('res.users', string='Verified By', readonly=True)
    kyc_verified_date = fields.Datetime(string='Verified Date', readonly=True)
    kyc_rejection_reason = fields.Text(string='Rejection Reason')
    
    # Risk Assessment
    risk_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ], string='Risk Level', default='low')
    
    # Relations
    account_ids = fields.One2many('bank.account', 'customer_id', string='Accounts')
    account_count = fields.Integer(string='Account Count', compute='_compute_account_count')
    
    # User Link
    user_id = fields.Many2one('res.users', string='Related User')
    
    # Status
    active = fields.Boolean(string='Active', default=True)
    
    _sql_constraints = [
        ('email_unique', 'unique(email)', 'Email must be unique!'),
        ('id_number_unique', 'unique(id_number)', 'ID Number must be unique!'),
    ]
    
    @api.model
    def create(self, vals):
        if vals.get('customer_id', 'New') == 'New':
            vals['customer_id'] = self.env['ir.sequence'].next_by_code('bank.customer') or 'New'
        return super(BankCustomer, self).create(vals)
    
    @api.depends('account_ids')
    def _compute_account_count(self):
        for record in self:
            record.account_count = len(record.account_ids)
    
    def action_submit_kyc(self):
        """Submit KYC for review"""
        for record in self:
            if not record.id_document or not record.address_proof or not record.photo:
                raise ValidationError('Please upload all required KYC documents.')
            record.kyc_status = 'submitted'
            record.message_post(body='KYC submitted for review')
    
    def action_approve_kyc(self):
        """Approve KYC"""
        for record in self:
            record.write({
                'kyc_status': 'approved',
                'kyc_verified_by': self.env.user.id,
                'kyc_verified_date': fields.Datetime.now()
            })
            record.message_post(body='KYC approved')
            # Send notification
            self.env['bank.notification'].create({
                'customer_id': record.id,
                'notification_type': 'email',
                'subject': 'KYC Approved',
                'message': f'Your KYC has been approved. Customer ID: {record.customer_id}',
            })
    
    def action_reject_kyc(self):
        """Reject KYC"""
        for record in self:
            record.kyc_status = 'rejected'
            record.message_post(body=f'KYC rejected: {record.kyc_rejection_reason}')
            # Send notification
            self.env['bank.notification'].create({
                'customer_id': record.id,
                'notification_type': 'email',
                'subject': 'KYC Rejected',
                'message': f'Your KYC has been rejected. Reason: {record.kyc_rejection_reason}',
            })
    
    def action_view_accounts(self):
        """View customer accounts"""
        return {
            'name': 'Customer Accounts',
            'type': 'ir.actions.act_window',
            'res_model': 'bank.account',
            'view_mode': 'tree,form',
            'domain': [('customer_id', '=', self.id)],
            'context': {'default_customer_id': self.id}
        }
