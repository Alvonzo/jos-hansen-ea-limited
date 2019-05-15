#-*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import calendar
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo import api, models, _
from odoo.exceptions import UserError


class ReportCustomerStatement(models.AbstractModel):
    _name = 'report.biztech_customer_ageing_report.report_customerstatement'
    _description = 'Customer Statement Ageing Report'

    def get_invoice_month(self, invoice, order_date):
        if order_date == 'date_due' and invoice.date_due:
            return datetime.strptime(str(invoice.date_due), '%Y-%m-%d').month
        elif order_date == 'date_invoice' and invoice.date_invoice:
            return datetime.strptime(str(invoice.date_invoice), '%Y-%m-%d').month
        return False

    def create_period_dict(self, period_data):
        period_date = False
        current_year = date.today().year
        current_date = date.today()
        periods = ['30', '60', '90', '120']
        previous_period = '0'
        for period in periods:
            start_date = current_date - timedelta(days=int(previous_period))
            end_date = current_date - timedelta(days=int(period))
            period_data.append({'period': period, 'amount': 0.0, 'start_date': start_date, 'end_date': end_date})
            previous_period = period
        return period_data

    @api.model
    def _get_report_values(self, docids, data=None):
        partners = header_lines = payable_lines = []
        partners = self.env['res.partner'].browse(list(data['partner_ids']))
        invoice_obj = self.env['account.invoice']
        move_line_obj = self.env['account.move.line']
        final_data = []
        partner_dict = {}
        current_year = date.today().year
        order_field = False
        if data.get('aged_by', False):
            if data['aged_by'] == 'due_date':
                order_field = 'date_due'
            elif data['aged_by'] == 'invoice_date':
                order_field = 'date_invoice'
        month_range = calendar.monthrange(date.today().year, data['month'])
        start_date = date.today().replace(day=1,month=data['month'],year=date.today().year)
        last_date = date.today().replace(day=month_range[1],month=data['month'],year=date.today().year)
        for partner in partners:
            partner_dict.update({partner: {'invoice_data': [], 'as_of': last_date.strftime('%d-%m-%Y'), 'period_data': [], 'total_amt': 0,
             'total_payment': 0, 'total_due': 0, 'payment_term': '', 'no_data': '', 'total_credit': 0.0, 'total_debit': 0.0, 'total_running_bal': 0.0}})
           
            invoice_data = []
            domain = [('partner_id', '=', partner.id), ('account_id.internal_type','=', 'receivable'), ('full_reconcile_id', '=', False)]
            domain += [('date_maturity', '<=', last_date)]
           
            period_data = [{'period': '0', 'date': 'Total Outstanding', 'amount': 0.0, 'start_date': start_date, 'end_date': last_date}]
            period_data = self.create_period_dict(period_data)
            running_bal = 0
            print("======period_data====",period_data)
            for move in move_line_obj.search(domain, order='date_maturity'):
                name = ''
                if move.invoice_id:
                    name = move.invoice_id.number
                elif move.payment_id:
                    name = move.payment_id.name
                invoice_data.append({
                    'move_id': move,
                    'invoice_id':move.date,
                    'description': move.name,
                    'due_date': move.date_maturity,
                    'invoice_no': name,
                    'credit': round(move.credit, 2),
                    'debit': round(move.debit, 2),
                    'running_bal': 0,
                })
                partner_dict[partner].update({
                    'total_debit': round(partner_dict[partner]['total_debit'] + move.debit, 2),
                    'total_credit': round(partner_dict[partner]['total_credit'] + move.credit, 2),
                    'total_running_bal': 0})
                for period in period_data:
                    if period['period'] != '0':
                        if move.date_maturity <= period['start_date'] and move.date_maturity > period['end_date']:
                            if move.debit:
                                period['amount'] += round(move.debit, 2)
                            elif move.credit:
                                period['amount'] -= round(move.credit, 2)
                        if period['period'] == '120' and move.date_maturity <= period['end_date']:
                            if move.debit:
                                period['amount'] += round(move.debit, 2)
                            elif move.credit:
                                period['amount'] -= round(move.credit, 2)
            
            invoice_data = sorted(invoice_data, key=lambda i: i['due_date'])
            total_residual = 0
            for invoice in invoice_data:
                total_residual += invoice['debit']
                total_residual -= invoice['credit']
                invoice['running_bal'] = round(total_residual, 2)
            partner_dict[partner]['total_running_bal'] = round(total_residual, 2)
            for period in period_data:
                if period['period'] == '0':
                    period['period'] = 'Total Outstanding'
                    period['amount'] = round(total_residual, 2)
                # if period['period'] == '120':
                #     if period['period'] == '+120':
            if not invoice_data:
                partner_dict[partner]['no_data'] = "There is nothing due with this customer!"
            partner_dict[partner].update({'invoice_data': invoice_data, 'period_data': period_data})
        return {'docs': partner_dict}