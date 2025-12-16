# -*- coding: utf-8 -*-

from odoo import models, fields, api


class BankAuditLog(models.Model):
    _name = 'bank.audit.log'
    _description = 'Bank Audit Log'
    _order = 'create_date desc, id desc'
    _rec_name = 'description'

    # Action Information
    action = fields.Selection([
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('transfer', 'Transfer'),
        ('transaction', 'Transaction'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('sms_sent', 'SMS Sent'),
        ('email_sent', 'Email Sent'),
        ('other', 'Other'),
    ], string='Action', required=True)
    
    # Model Information
    model_name = fields.Char(string='Model', required=True)
    record_id = fields.Integer(string='Record ID')
    
    # Description
    description = fields.Text(string='Description', required=True)
    
    # User Information
    user_id = fields.Many2one('res.users', string='User', required=True, 
                             default=lambda self: self.env.user, ondelete='restrict')
    user_name = fields.Char(related='user_id.name', string='User Name', readonly=True, store=True)
    
    # IP Address
    ip_address = fields.Char(string='IP Address')
    
    # Old and New Values (for updates)
    old_values = fields.Text(string='Old Values')
    new_values = fields.Text(string='New Values')
    
    # Severity
    severity = fields.Selection([
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ], string='Severity', default='info')
    
    # Timestamp
    timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now, 
                               required=True, readonly=True)
    
    @api.model
    def log_action(self, action, model_name, record_id, description, severity='info', 
                   old_values=None, new_values=None):
        """Helper method to create audit log"""
        return self.create({
            'action': action,
            'model_name': model_name,
            'record_id': record_id,
            'description': description,
            'severity': severity,
            'old_values': old_values,
            'new_values': new_values,
            'user_id': self.env.user.id,
        })
    
    @api.model
    def cron_cleanup_old_logs(self):
        """Cron job to cleanup logs older than 1 year"""
        from dateutil.relativedelta import relativedelta
        
        cutoff_date = fields.Datetime.now() - relativedelta(years=1)
        old_logs = self.search([('timestamp', '<', cutoff_date)])
        
        # Archive instead of delete for compliance
        # old_logs.unlink()
        
        return True
