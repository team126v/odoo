from openerp import models, fields, api, tools, _
import logging
import re

_logger = logging.getLogger(__name__)
_phone_reg = '^(\+?\d{1,2}[ -]?)?(\(\+?\d{1,4}\)|\+?\d{1,4})?[ -]?\d{3,4}[ -]?\d{3,4}$'
_email_reg = '^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$'

class res_partner(models.Model):
    _inherit = 'res.partner'
    mom_company_id = fields.Many2one('res.partner', string="Mother Company")

    @api.onchange('parent_id')
    def _onchange_partner_id(self):
        parent = self.env['res.partner'].browse(self.parent_id.id)
        if parent:
            self.phone = parent.phone
            self.fax = parent.fax
            self.lang = parent.lang
        return super(res_partner, self).onchange_parent_id(self)

    @api.constrains('email')
    def _validate_email(self):
        if not re.match(_email_reg, self.email):
            raise Warning(_("Invalid e-mail"))

    @api.constrains('phone')
    def _validate_phone(self):
        if not re.match(_phone_reg, self.phone):
            raise Warning(_("Invalid phone number"))

    @api.constrains('fax')
    def _validate_fax(self):
        if not re.match(_phone_reg, self.fax):
            raise Warning(_("Invalid fax number"))

    @api.constrains('mobile')
    def _validate_mobile(self):
        if not re.match(_phone_reg, self.mobile):
            raise Warning(_("Invalid mobile number"))