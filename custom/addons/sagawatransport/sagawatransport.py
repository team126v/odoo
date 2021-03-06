import time
import re
from lxml import etree

_phone_reg = '^(\+?\d{1,2}[ -]?)?(\(\+?\d{1,4}\)|\+?\d{1,4})?[ -]?\d{3,4}[ -]?\d{3,4}$'
_email_reg = '^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$'

from openerp import models, fields, api, tools, _
class sale_order(models.Model):
    _inherit = 'sale.order'
    version = fields.Integer(string=None,default=1,copy=True)
    crm_lead_id = fields.Many2one('crm.lead', string='Leads', index=True)
    is_copied = fields.Boolean(string='Is Copied?',default=False,copy=False)
    is_templete = fields.Boolean('Is Templete')
    profit_percentage = fields.Float(string='Profit Percentage (%)', default=10)
    total_confirm_sale = fields.Float(string='Total Sale Value')
    order_details = fields.Html('Quotation Details')
    templete_id = fields.Many2one('sale.order', 'Choose Templete', domain="[('is_templete', '=', True)]")
    state = fields.Selection(selection_add=[('early_payment', 'Early payment: Discount early payment')])
    paid_company_id = fields.Char(string='Mother Company',store=True, related='partner_id.mom_company_id.name', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approve', 'Approved'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sale Order'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')

    @api.one
    @api.constrains('profit_percentage')
    def _check_values(self):
        if self.profit_percentage < 0.0 or self.profit_percentage > 100.0:
            raise Warning(_('Profit percentage should be in range 0 .. 100!.'))

    @api.multi
    def action_quotation_approve(self):
        self.write({'state': 'approve'})

    @api.onchange('crm_lead_id')
    def _onchange_crm_lead_id(self):
        # this will set crm_lead_id on record new creation
        if not self.crm_lead_id and self.opportunity_id:
            self.crm_lead_id = self.opportunity_id
        self.opportunity_id = self.crm_lead_id

    @api.onchange('templete_id')
    def _onchange_is_templete(self):
        if self.templete_id:
            templete = self.env['sale.order'].browse(self.templete_id.id)
            self.order_details = templete.order_details
    @api.multi
    def copy_button(self, default=None):
        default = dict(default or {})
        default.update({
            'name': self.name.split('_')[0] + "_" + str(self.version),
            'version': self.version + 1
        })
        ret = super(sale_order, self).copy(default)
        self.write({'is_copied': True})
        return {
            'name': _("Products to Process"),
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': 'sale.order',
            'res_id': ret.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
            'domain': '[]',
            'flags' : {'initial_mode': 'edit'}
        }
    @api.multi
    def print_quotation(self):
        self.filtered(lambda s: s.state == 'approve').write({'state': 'sent'})
        return self.env['report'].get_action(self, 'sale.report_saleorder')

class SagawaMailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    @api.multi
    def send_mail(self, auto_commit=False):
        if self._context.get('default_model') == 'sale.order' and self._context.get('default_res_id') and self._context.get('mark_so_as_sent'):
            order = self.env['sale.order'].browse([self._context['default_res_id']])
            if order.state in ('draft', 'approve'):
                order.state = 'sent'
        return super(SagawaMailComposeMessage, self.with_context(mail_post_autofollow=True)).send_mail(auto_commit=auto_commit)

class crm_lead(models.Model):
    _inherit = 'crm.lead'
    sale_revenue = fields.Float('Revenue')
    reason_to_fail = fields.Text('Reason to fail')
    co_sales_ids = fields.Many2many('res.users', 'crm_lead_user_rel', 'lead_id', 'user_id', 'Co Sale man')

    sg_partner_id = fields.Many2one('res.partner', 'Partner 2', ondelete='set null', track_visibility='onchange',select=True, help="Linked partner 2")
    sg_email_from = fields.Char('Email', size=128, help="Email address of the contact 2", select=1)
    sg_contact_name = fields.Char('Contact Name', size=64)
    sg_partner_name = fields.Char('Customer Name 2', size=64)
    sg_street = fields.Char('Street')
    sg_street2 = fields.Char('Street2')
    sg_zip = fields.Char('Zip', change_default=True, size=24)
    sg_city = fields.Char('City')
    sg_state_id = fields.Many2one("res.country.state", 'State')
    sg_country_id = fields.Many2one('res.country', 'Country')
    sg_phone = fields.Char('Phone')
    sg_fax = fields.Char('Fax')
    sg_mobile = fields.Char('Mobile')
    sg_function = fields.Char('Function')

    @api.onchange('sg_partner_id')
    def _change_sg_partner_id(self):
        if self.sg_partner_id:
            partner = self.env['res.partner'].browse(self.sg_partner_id.id)
            partner_name = (partner.parent_id and partner.parent_id.name) or (partner.is_company and partner.name) or False
            self.sg_partner_name = partner_name
            self.sg_contact_name = (not partner.is_company and partner.name) or False
            self.sg_street = partner.street
            self.sg_street2 = partner.street2
            self.sg_city = partner.city
            self.sg_state_id = partner.state_id and partner.state_id.id or False
            self.sg_country_id = partner.country_id and partner.country_id.id or False
            self.sg_email_from = partner.email
            self.sg_phone = partner.phone
            self.sg_mobile = partner.mobile
            self.sg_fax = partner.fax
            self.sg_zip = partner.zip
            self.sg_function = partner.function

    @api.constrains('email_from')
    def _validate_email(self):
        if self.email_from and not re.match(_email_reg, self.email_from):
            raise Warning(_("Invalid e-mail"))

    @api.constrains('sg_email_from')
    def _validate_sg_email(self):
        if self.sg_email_from and not re.match(_email_reg, self.sg_email_from):
            raise Warning(_("Invalid customer 2's e-mail"))

    @api.constrains('phone')
    def _validate_phone(self):
        if self.phone and not re.match(_phone_reg, self.phone):
            raise Warning(_("Invalid phone number"))

    @api.constrains('sg_phone')
    def _validate_sg_phone(self):
        if self.sg_phone and not re.match(_phone_reg, self.sg_phone):
            raise Warning(_("Invalid customer 2's phone number"))

    @api.constrains('fax')
    def _validate_fax(self):
        if self.fax and not re.match(_phone_reg, self.fax):
            raise Warning(_("Invalid fax number"))

    @api.constrains('sg_fax')
    def _validate_sg_fax(self):
        if self.sg_fax and not re.match(_phone_reg, self.sg_fax):
            raise Warning(_("Invalid customer 2's fax number"))

    @api.constrains('mobile')
    def _validate_mobile(self):
        if self.mobile and not re.match(_phone_reg, self.mobile):
            raise Warning(_("Invalid mobile number"))

    @api.constrains('sg_mobile')
    def _validate_sg_mobile(self):
        if self.sg_mobile and not re.match(_phone_reg, self.sg_mobile):
            raise Warning(_("Invalid customer 2's mobile number"))
