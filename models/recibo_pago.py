# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime
from odoo.release import version_info
import logging

class RaciboPago(models.Model):
    _name = 'recibo.pago'
    _rec_name = 'cliente_id'

    cliente_id = fields.Many2one('res.partner','Cliente', required=True)
    pagar_todas = fields.Boolean('Pagar todas')
    pago_ids = fields.One2many('account.payment','pago_origen_id',string='Pago',readonly=True)
    diario_id = fields.Many2one('account.journal','Diario')
    fecha = fields.Date('Fecha')
    linea_pago_ids = fields.One2many('recibo.pago.linea','recibo_id',string='Lineas')
    total = fields.Float(string='Total',store=True, readonly=True, compute='_calcular_total')
    estado = fields.Selection([
        ('nuevo', 'Nuevo'),
        ('validado', 'Validado'),
        ], string='Estado', readonly=True, copy=False, index=True, track_visibility='onchange', default='nuevo')
    pago_id = fields.Many2one('account.payment','Pago')
    numero_recibo = fields.Char('Número de recibo', required=True)
    cobrador_id = fields.Many2one('hr.employee','Cobrador')
    forma_pago = fields.Selection([ ('efectivo', 'Efectivo'),('tarjeta','Tarjeta'),
        ('cheque', 'Cheque'),('transferencia','Transferencia')],'Forma de pago')

    @api.depends('linea_pago_ids.pago')
    def _calcular_total(self):
        for pago in self:
            total = 0
            for linea in pago.linea_pago_ids:
                total += linea.pago
            pago.update({
                'total': total,
            })

    def cancelar_pagos(self):
        if self.pago_ids:
            for linea in self.pago_ids:
                linea.action_draft()
                if version_info[0] == 13:
                    linea.cancel()
                else:
                    linea.action_cancel()
            self.estado = 'nuevo'

    def pagar(self):
        pago_id = False
        if self.numero_recibo:
            recibo_ids = self.env['recibo.pago'].search([('id','!=',self.id),('numero_recibo','=',self.numero_recibo)])
            if recibo_ids:
                raise UserError(_('Número de recibo repetido.'))

        if self.linea_pago_ids:
            pagos = []
            existe_pago = self.env['account.payment'].search([('pago_origen_id','=',self.id),('state','=','posted')])
            if len(existe_pago) == 0:
                for linea in self.linea_pago_ids:
                    if linea.pago > 0 and linea.pago <= linea.saldo:
                        factura_id = False
                        if linea.factura_id.source_id:
                            factura_original_id = self.env['account.move'].search([('source_id','=',linea.factura_id.source_id.id)])
                            factura_id = factura_original_id
                        else:
                            factura_id = linea.factura_id

                        pago_dic = {'amount': linea.pago,
                                    'partner_id': self.cliente_id.id,
                                    'partner_type': 'customer',
                                    'payment_type': 'inbound',
                                    'journal_id': self.diario_id.id,
                                    'payment_method_id': 1}

                        if version_info[0] == 13:
                            pago_dic['payment_date'] = self.fecha
                        else:
                            pago_dic['date'] = self.fecha

                        pago_id= self.env['account.payment'].create(pago_dic)
                        if version_info[0] == 13:
                            pago_id.post()
                            for linea_gasto in pago_id.move_line_ids.filtered(lambda r: r.account_id.user_type_id.type == 'receivable' and not r.reconciled):
                                for linea_factura in factura_id.line_ids.filtered(lambda r: r.account_id.user_type_id.type == 'receivable' and not r.reconciled):
                                    if (linea_gasto.debit == linea_factura.credit or linea_gasto.credit - linea_factura.debit ):
                                        (linea_gasto | linea_factura).reconcile()
                                        break
                        else:
                            pago_id.action_post()
                            for linea_gasto in pago_id.move_id.line_ids.filtered(lambda r: r.account_id.user_type_id.type == 'receivable' and not r.reconciled):
                                for linea_factura in factura_id.line_ids.filtered(lambda r: r.account_id.user_type_id.type == 'receivable' and not r.reconciled):
                                    if (linea_gasto.debit == linea_factura.credit or linea_gasto.credit - linea_factura.debit ):
                                        (linea_gasto | linea_factura).reconcile()
                                        break

                        pago_id.pago_origen_id = self.id
                        pagos.append(pago_id.id)
            self.update({
                'estado':  'validado',
            })
        return True

    @api.onchange('cliente_id')
    def onchange_cliente_id(self):
        if self.cliente_id:
            dominio = [('partner_id','=',self.cliente_id.id),('state','=','posted'),('move_type','=','out_invoice'),('amount_residual','>',0)]
            if version_info[0] == 13:
                dominio = [('partner_id','=',self.cliente_id.id),('state','=','posted'),('type','=','out_invoice')]

            factura_ids = self.env['account.move'].search(dominio).ids
            if factura_ids:
                facturas = []
                for factura in factura_ids:
                    facturas.append((0,0,{'factura_id': factura}))

                self.write({
                    'linea_pago_ids' : [(5, 0, 0)],
                })
                self.write({'linea_pago_ids' : facturas})

    @api.onchange('pagar_todas')
    def onchange_pagar_todas(self):
        if self.linea_pago_ids:
            for linea in self.linea_pago_ids:
                linea.pago = linea.saldo
                linea.pagar_completa = True

class ReciboPagoLinea(models.Model):
    _name = 'recibo.pago.linea'

    @api.depends('total')
    def _compute_total(self):
        for linea in self:
            if version_info[0] == 13:
                if linea.factura_id.type in ['in_refund', 'out_refund'] :
                    linea.saldo = linea.factura_id.amount_residual * -1
                    linea.total = linea.factura_id.amount_total * -1
                else:
                    linea.saldo = linea.factura_id.amount_residual * 1
                    linea.total = linea.factura_id.amount_total * 1
            else:
                if linea.factura_id.move_type in ['in_refund', 'out_refund'] :
                    linea.saldo = linea.factura_id.amount_residual * -1
                    linea.total = linea.factura_id.amount_total * -1
                else:
                    linea.saldo = linea.factura_id.amount_residual * 1
                    linea.total = linea.factura_id.amount_total * 1

    recibo_id = fields.Many2one('recibo.pago','Recibo de pago')
    factura_id = fields.Many2one('account.move','Factura')
    currency_id = fields.Many2one('res.currency',related='factura_id.currency_id',string='Moneda')
    fecha_factura = fields.Date('Fecha factura',related='factura_id.invoice_date')
    saldo = fields.Monetary('Saldo',related='factura_id.amount_residual')
    total = fields.Monetary('Total',compute='_compute_total')
    pago = fields.Float('Pago')
    pagar_completa = fields.Boolean('Pagar toda')

    @api.onchange('pagar_completa')
    def onchange_pagar_completa(self):
        for linea in self:
            linea.pago = linea.saldo
