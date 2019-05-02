# -*- coding: utf-8 -*-
{
    'name': "Customer Statement Ageing Report",
    'version': '12.0.1.0.0',
    'summary': """Generate Customer Statement Ageing Report from Customer Form""",
    'author': "BiztechCS",
    'license': 'AGPL-3',
    'website': 'http://www.biztechcs.com/',
    'depends': [
        'account',
    ],
    'data': [
        'wizard/customer_ageing_wizard_view.xml',
        'report/customer_ageing_report_view.xml',
        'views/customer_statement_reports.xml',
    ],
    'application': True
}
