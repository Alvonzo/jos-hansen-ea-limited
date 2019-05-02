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
        move_line_obj = self.env['account.move.line']
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
            for invoice in invoices.filtered(lambda x:x.residual > 0):
                move_lines = move_line_obj.search([('ref', '=', invoice.reference), ('full_reconcile_id', '=', False), ('account_id', '=', invoice.account_id.id)], order='id')
                payment_amount = sum(payment.amount for payment in invoice.payment_ids)
                invoice_month = self.get_invoice_month(invoice, order_field)
                period_month = [period['month'] for period in period_data]
                min_period = min([period['date'] for period in period_data])
                total_amt = total_payment = total_due = 0
                for move in move_lines:
                    if move.debit:
                        running_bal += move.debit
                    if move.credit:
                        running_bal -= move.credit
                    invoice_data.append({
                        'description': invoice.name,
                        'due_date': invoice.date_due and invoice.date_due.strftime('%d-%m-%Y') or '',
                        'invoice_no': invoice.number,
                        'invoice_amount': invoice.amount_total,
                        'payment_amount': payment_amount,
                        'due_payment': invoice.residual,
                        'credit': round(move.credit, 2),
                        'debit': round(move.debit, 2),
                        'running_bal': round(running_bal, 2),
                    })
                    partner_dict[partner].update({
                        'total_amt': partner_dict[partner]['total_amt'] + invoice.amount_total,
                        'total_payment': partner_dict[partner]['total_payment'] + payment_amount,
                        'total_due': partner_dict[partner]['total_due'] + invoice.residual,
                        'total_debit': round(partner_dict[partner]['total_debit'] + move.debit, 2),
                        'total_credit': round(partner_dict[partner]['total_credit'] + move.credit, 2),
                        'total_running_bal': round(running_bal, 2)})
                for period in period_data:
                    if period['month'] == current_month:
                        period['date'] = 'Current'
                    if invoice_month in period_month:
                        if period['month'] == invoice_month:
                            period['amount'] += invoice.residual
                        if period['month'] == 'current' and invoice_month == current_month:
                            period['amount'] = round(running_bal, 2)
                    elif period['date'] == min_date:
                        period['amount'] += invoice.residual
            if not invoice_data:
                partner_dict[partner]['no_data'] = "There is nothing due with this customer!"
            partner_dict[partner].update({'invoice_data': invoice_data, 'period_data': period_data})
        return {'docs': partner_dict}