from datetime import datetime
from odoo import fields, models, _
from odoo.exceptions import UserError


class CustomerAgeingWizard(models.TransientModel):
    _name = "customer.ageing.wizard"

    month = fields.Selection([
        (1, 'January'),
        (2, 'February'),
        (3, 'March'),
        (4, 'April'),
        (5, 'May'),
        (6, 'June'),
        (7, 'July'),
        (8, 'August'),
        (9, 'September'),
        (10, 'October'),
        (11, 'November'),
        (12, 'December')], "Month", default=datetime.now().month, required=True)
    aged_by = fields.Selection([('due_date', 'Due Date'), ('invoice_date', 'Invoice Date')], "Aged By", default='due_date', required=True)
    previous_year = fields.Boolean("Print for Previous Year")

    def print_ageing_report(self):
        active_ids = self.env.context.get('active_ids') and self.env.context['active_ids'] or []
        partner_ids = self.env['res.partner'].browse(active_ids)
        data = {"partner_ids": partner_ids.ids, "month": self.month, 'aged_by': self.aged_by, 'previous_year': self.previous_year}
        return self.env.ref('biztech_customer_ageing_report.action_report_customerstatment').with_context(from_transient_model=True).report_action(None, data=data)