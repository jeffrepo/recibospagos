# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime
import logging

class RaciboPago(models.Model):
    _name = 'recibo.pago'
    _rec_name = 'cliente_id'

    cliente_id = fields.Many2one('res.partner','Cliente', required=True)
    empleado_id = fields.Many2one('hr.employee','Empleado')
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
                linea.cancel()
            self.estado = 'nuevo'

    def pagar(self):
        pago_id = False
        if self.linea_pago_ids:
            pagos = []
            existe_pago = self.env['account.payment'].search([('pago_origen_id','=',self.id),('state','=','posted')])
            if len(existe_pago) == 0:
                for linea in self.linea_pago_ids:
                    if linea.pago > 0 and linea.pago <= linea.saldo:
                        factura_id = False
                        if linea.factura_id.source_id:
                            factura_original_id = self.env['account.move'].search([('source_id','=',linea.factura_id.source_id.id)])
                            factura_id = factura_original_id.id
                        else:
                            factura_id = linea.factura_id.id

                        pago_id= self.env['account.payment'].create({'amount': linea.pago,
                                                    'partner_id': self.cliente_id.id,
                                                    'date': self.fecha,
                                                    'partner_type': 'customer',
                                                    'payment_type': 'inbound',
                                                    'reconciled_invoice_ids': [(4,factura_id)],
                                                    'journal_id': self.diario_id.id,
                                                    'payment_method_id': 1})
                        pago_id.action_post()
                        pago_id.pago_origen_id = self.id
                        pagos.append(pago_id.id)
            self.update({
                'estado':  'validado',
            })
        return True

    @api.onchange('cliente_id')
    def onchange_cliente_id(self):
        if self.cliente_id:
            factura_ids = self.env['account.move'].search([('partner_id','=',self.cliente_id.id),('state','=','posted'),('move_type','=','out_invoice')]).ids
            logging.warning(factura_ids)
            if factura_ids:
                logging.warning(factura_ids)
                facturas = []
                for factura in factura_ids:
                    facturas.append((0,0,{'factura_id': factura}))

                self.update({
                    'linea_pago_ids': facturas,
                })

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
        if self.factura_id.move_type in ['in_refund', 'out_refund'] :
            self.saldo = self.factura_id.amount_residual * -1
            self.total = self.factura_id.amount_total * -1
        else:
            self.saldo = self.factura_id.amount_residual * 1
            self.total = self.factura_id.amount_total * 1

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
        self.pago = self.saldo
