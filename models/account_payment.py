# -*- coding: utf-8 -*-
from odoo import api, exceptions, fields, models, _
from odoo.release import version_info
import logging

class AccountPayment(models.Model):
    _inherit = "account.payment"

    recibo_id = fields.Many2one('recibo.pago',string="Recibo")
