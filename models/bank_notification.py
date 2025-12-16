# -*- coding: utf-8 -*-

from odoo import models, fields, api


class BankNotification(models.Model):
    _name = 'bank.notification'
    _description = 'Bank Notification'
    _order = 'create_date desc, id desc'
    _rec_name = 'subject'

    # Notification Information
    customer_id = fields.Many2one('bank.customer', string='Customer', 
                                 required=True, ondelete='cascade')
    notification_type = fields.Selection([
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
        ('in_app', 'In-App Notification'),
    ], string='Type', required=True, default='email')
    
    # Content
    subject = fields.Char(string='Subject', required=True)
    message = fields.Text(string='Message', required=True)
    
    # Recipient
    recipient_email = fields.Char(string='Recipient Email', 
                                  related='customer_id.email', readonly=True)
    recipient_phone = fields.Char(string='Recipient Phone', 
                                  related='customer_id.phone', readonly=True)
    
    # Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('read', 'Read'),
    ], string='Status', default='draft', tracking=True)
    
    # Delivery
    sent_date = fields.Datetime(string='Sent Date', readonly=True)
    delivered_date = fields.Datetime(string='Delivered Date', readonly=True)
    read_date = fields.Datetime(string='Read Date', readonly=True)
    
    # Error
    error_message = fields.Text(string='Error Message')
    retry_count = fields.Integer(string='Retry Count', default=0)
    
    # Gateway Reference (for SMS/Email services)
    gateway_reference = fields.Char(string='Gateway Reference')
    
    # Priority
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string='Priority', default='normal')
    
    @api.model
    def create(self, vals):
        result = super(BankNotification, self).create(vals)
        # Auto-send if not draft
        if result.status != 'draft':
            result.action_send()
        return result
    
    def action_send(self):
        """Send notification"""
        for record in self:
            try:
                if record.notification_type == 'email':
                    record._send_email()
                elif record.notification_type == 'sms':
                    record._send_sms()
                elif record.notification_type == 'push':
                    record._send_push()
                elif record.notification_type == 'in_app':
                    record._send_in_app()
                
                record.write({
                    'status': 'sent',
                    'sent_date': fields.Datetime.now(),
                })
            except Exception as e:
                record.write({
                    'status': 'failed',
                    'error_message': str(e),
                    'retry_count': record.retry_count + 1,
                })
    
    def _send_email(self):
        """Send email notification"""
        self.ensure_one()
        
        # Use Odoo's mail system
        mail_values = {
            'subject': self.subject,
            'body_html': self.message,
            'email_to': self.recipient_email,
            'email_from': self.env.company.email or 'noreply@bank.com',
        }
        
        mail = self.env['mail.mail'].create(mail_values)
        mail.send()
        
        self.gateway_reference = f'EMAIL-{mail.id}'
    
    def _send_sms(self):
        """Send SMS notification (Placeholder)"""
        self.ensure_one()
        
        # Placeholder for SMS gateway integration
        # In production, integrate with SMS provider like Twilio, AWS SNS, etc.
        
        # Simulate SMS sending
        import random
        gateway_ref = f'SMS-{random.randint(100000, 999999)}'
        
        self.gateway_reference = gateway_ref
        
        # Log the SMS
        self.env['bank.audit.log'].create({
            'action': 'sms_sent',
            'model_name': 'bank.notification',
            'record_id': self.id,
            'description': f'SMS sent to {self.recipient_phone}: {self.message[:50]}...',
            'user_id': self.env.user.id,
        })
    
    def _send_push(self):
        """Send push notification (Placeholder)"""
        self.ensure_one()
        
        # Placeholder for push notification service
        # In production, integrate with Firebase Cloud Messaging, OneSignal, etc.
        
        import random
        gateway_ref = f'PUSH-{random.randint(100000, 999999)}'
        
        self.gateway_reference = gateway_ref
    
    def _send_in_app(self):
        """Send in-app notification"""
        self.ensure_one()
        
        # Create activity for in-app notification
        self.env['mail.activity'].create({
            'res_model_id': self.env['ir.model']._get('bank.customer').id,
            'res_id': self.customer_id.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': self.subject,
            'note': self.message,
            'user_id': self.customer_id.user_id.id if self.customer_id.user_id else self.env.user.id,
        })
    
    def action_retry(self):
        """Retry sending failed notification"""
        for record in self:
            if record.status == 'failed' and record.retry_count < 3:
                record.action_send()
    
    @api.model
    def cron_retry_failed(self):
        """Cron job to retry failed notifications"""
        failed_notifications = self.search([
            ('status', '=', 'failed'),
            ('retry_count', '<', 3)
        ])
        
        for notification in failed_notifications:
            notification.action_retry()
