# -*- coding: utf-8 -*-
{
    'name': "Recibo de pago",

    'summary': """ Recibo de pago """,

    'description': """
         Recibo de pago
    """,

    'author': "Aquih S.A.",
    'website': "http://www.aquih.com",

    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['account','hr'],

    'data': [
        'views/account_payment_view.xml',
        'views/recibo_pago_views.xml',
        'security/ir.model.access.csv',
    ],
}
