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

    def create_period_dict(self, aged_month, period_data):
        period_date = False
        current_year = date.today().year
        for period in range(0,5):
            month_range = calendar.monthrange(current_year, aged_month)
            period_date = date.today().replace(day=month_range[1],month=aged_month,year=current_year)
            period_data.append({'month': aged_month, 'date': period_date.strftime('%d-%m-%Y'), 'amount': 0.0})
            aged_month = (period_date - relativedelta(months=1)).month
            if aged_month == 12:
                current_year -= 1
        return period_data, period_date.strftime('%d-%m-%Y')

    @api.model
    def _get_report_values(self, docids, data=None):
        partners = header_lines = payable_lines = []
        partners = self.env['res.partner'].browse(list(data['partner_ids']))
        invoice_obj = self.env['account.invoice']
        final_data = []
        partner_dict = {}
        order_field = False
        if data.get('aged_by', False):
            if data['aged_by'] == 'due_date':
                order_field = 'date_due'
            elif data['aged_by'] == 'invoice_date':
                order_field = 'date_invoice'
        month_range = calendar.monthrange(date.today().year, data['month'])
        last_date = date.today().replace(day=month_range[1],month=data['month'],year=date.today().year)
        for partner in partners:
            partner_dict.update({partner: {'invoice_data': [], 'as_of': last_date.strftime('%d-%m-%Y'), 'period_data': [], 'total_amt': 0,
             'total_payment': 0, 'total_due': 0, 'payment_term': '', 'no_data': '', 'total_credit': 0.0, 'total_debit': 0.0, 'total_running_bal': 0.0}})
            if partner.property_payment_term_id:
                partner_dict[partner]['payment_term'] = partner.property_payment_term_id and partner.property_payment_term_id.name or ''
            invoice_data = []
            domain = [('partner_id', '=', partner.id), ('state', 'in', ['open', 'in_payment']), ('type', 'in', ['out_invoice', 'out_refund'])]
            domain += [(order_field, '<=', last_date)]
            invoices = invoice_obj.search(domain, order=order_field)
            current_month = last_date.month
            period_data = [{'month': 'current', 'date': 'Total Outstanding', 'amount': 0.0}]
            period_data, min_date = self.create_period_dict(data['month'], period_data)
            running_bal = 0
            period_month = [period['month'] for period in period_data]
            min_period = min([period['date'] for period in period_data])
            payments = self.env['account.payment'].search([('partner_id', '=', partner.id), ('state', '=', 'posted'), ('invoice_ids', '=', False), ('payment_type', '=', 'inbound')])
            for invoice in invoices.filtered(lambda x:x.residual > 0):
                payment_amount = sum(payment.amount for payment in invoice.payment_ids)
                invoice_month = self.get_invoice_month(invoice, order_field)
                total_amt = total_payment = total_due = 0
                debit = credit = 0
                if invoice.type == 'out_invoice':
                    debit = invoice.residual
                    running_bal += invoice.residual
                elif invoice.type == 'out_refund':
                    credit = invoice.residual
                    running_bal -= invoice.residual
                invoice_data.append({
                    'description': invoice.name,
                    'due_date': invoice.date_due,
                    'invoice_no': invoice.number,
                    'credit': round(credit, 2),
                    'debit': round(debit, 2),
                    'running_bal': round(running_bal, 2),
                })
                partner_dict[partner].update({
                    'total_debit': round(partner_dict[partner]['total_debit'] + debit, 2),
                    'total_credit': round(partner_dict[partner]['total_credit'] + credit, 2),
                    'total_running_bal': round(running_bal, 2)})
                for period in period_data:
                    if period['month'] == current_month:
                        period['date'] = 'Current'
                    if invoice_month in period_month:
                        if period['month'] == invoice_month:
                            if invoice.type == 'out_invoice':
                                period['amount'] += invoice.residual
                            elif invoice.type == 'out_refund':
                                period['amount'] -= invoice.residual
                        if period['month'] == 'current' and invoice_month == current_month:
                            period['amount'] = round(running_bal, 2)
                    elif period['date'] == min_date:
                        if invoice.type == 'out_invoice':
                            period['amount'] += invoice.residual
                        elif invoice.type == 'out_refund':
                            period['amount'] -= invoice.residual
            for pay in payments:
                running_bal -= pay.amount
                invoice_month = datetime.strptime(str(pay.payment_date), '%Y-%m-%d').month
                invoice_data.append({
                    'description': pay.name,
                    'due_date': pay.payment_date,
                    'invoice_no': 'Customer Payment',
                    'credit': round(pay.amount, 2),
                    'debit': round(0, 2),
                    'running_bal': round(running_bal, 2),
                })
                for period in period_data:
                    if period['month'] == current_month:
                        period['date'] = 'Current'
                    if invoice_month in period_month:
                        if period['month'] == invoice_month:
                            period['amount'] -= pay.amount
                        if period['month'] == 'current' and invoice_month == current_month:
                            period['amount'] = round(running_bal, 2)
                    elif period['date'] == min_date:
                        period['amount'] -= pay.amount
                partner_dict[partner].update({
                    'total_debit': round(partner_dict[partner]['total_debit'], 2),
                    'total_credit': round(partner_dict[partner]['total_credit'] + pay.amount, 2),
                    'total_running_bal': round(running_bal, 2)})
            if not invoice_data:
                partner_dict[partner]['no_data'] = "There is nothing due with this customer!"
            invoice_data = sorted(invoice_data, key=lambda i: i['due_date'])
            partner_dict[partner].update({'invoice_data': invoice_data, 'period_data': period_data})
        return {'docs': partner_dict}