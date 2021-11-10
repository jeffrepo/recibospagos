# -*- coding: utf-8 -*-
from odoo import api, exceptions, fields, models, _
from odoo.release import version_info
import logging

class AccountPayment(models.Model):
    _inherit = "account.payment"

    pago_origen_id = fields.Many2one('recibo.pago',string="Pago origen")
    # empleado_id = fields.Many2one('hr.employee','Empleado')
    pago_liquidacion_ids = fields.One2many('recibo.pago' if version_info[0] == 13 else 'account.payment',
        'pago_id' if version_info[0] == 13 else 'pago_origen_id',
        domain="[('estado', '=', 'validado'),('pago_id','=',False)]" if version_info[0] == 13 else "[('state','=','posted'),('pago_origen_id','!=',False)]" ,string="Pagos")

    @api.onchange('pago_liquidacion_ids')
    def onchange_pago_liquidacion_ids(self):
        total = 0
        if self.pago_liquidacion_ids:
            if version_info[0] == 14:
                cuenta_destino_id = self.pago_liquidacion_ids[0].pago_origen_id.diario_id.default_account_id
                self.destination_account_id = cuenta_destino_id.id
            for pago in self.pago_liquidacion_ids:
                if version_info[0] == 13:
                    if pago.linea_pago_ids:
                        for linea in pago.linea_pago_ids:
                            total += linea.pago
                else:
                    total += pago.amount
        self.amount = total

    if version_info[0] == 13:
        def post(self):
            res = super(AccountPayment, self).post()
            for rec in self:
                if rec.pago_liquidacion_ids:
                    for pago in rec.pago_liquidacion_ids:
                        pago.write({'pago_id': rec.id})
            return True
    else:
        def action_post(self):
            res = super(AccountPayment, self).action_post()
            for rec in self:
                if rec.pago_liquidacion_ids:
                    for pago in rec.pago_liquidacion_ids:
                        pago.write({'pago_id': rec.id})
            return True

        @api.depends('partner_id', 'destination_account_id', 'journal_id','pago_liquidacion_ids')
        def _compute_is_internal_transfer(self):
            res = super(AccountPayment, self)._compute_is_internal_transfer()
            for payment in self:
                if payment.pago_liquidacion_ids:
                    payment.is_internal_transfer = True
                    cuenta_destino_id = payment.pago_liquidacion_ids[0].pago_origen_id.diario_id.default_account_id
                    payment.destination_account_id = cuenta_destino_id.id
            return res
