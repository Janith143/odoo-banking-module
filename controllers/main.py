# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request


class BankController(http.Controller):
    
    @http.route('/bank/dashboard', type='http', auth='user', website=True)
    def bank_dashboard(self, **kwargs):
        """Customer banking dashboard"""
        return request.render('odoo_bank.customer_dashboard', {})
    
    @http.route('/bank/api/transfer', type='json', auth='user', methods=['POST'])
    def api_transfer(self, **kwargs):
        """API endpoint for money transfers"""
        # This will be used by OWL components
        return {'status': 'success'}
