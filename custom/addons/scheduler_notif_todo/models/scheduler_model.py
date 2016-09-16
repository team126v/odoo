# -*- coding: utf-8 -*-
from openerp import models, fields, api, tools, _
from collections import defaultdict
#Import itertools
import itertools
#Import logger
import logging
#Get the logger
_logger = logging.getLogger(__name__)

#External import
import datetime

class res_partner(models.Model):
    _inherit = 'res.partner'

    def _get_messages_by_email(self, cr, uid, ids=None, context=None):
        today = datetime.datetime.now()
        today_to_s = today.strftime('%Y-%m-%d')
        query = '''SELECT res_partner.email as email, crm_lead.name as lead_name, crm_lead.date_action as date_action, crm_lead.title_action as title,
                    mail_message_subtype.name as action_name
                    FROM res_users
                    JOIN crm_lead
                        ON crm_lead.user_id = res_users.id
                    JOIN res_partner
                        ON res_users.partner_id = res_partner.id
                    JOIN crm_activity
                        ON crm_lead.next_activity_id = crm_activity.id
                    JOIN mail_message_subtype
                        ON crm_activity.subtype_id = mail_message_subtype.id
                    WHERE crm_lead.date_action=%s'''
        cr.execute(query, (today_to_s,))
        messages = cr.dictfetchall()
        messages_by_email = {k: [v for v in messages if v['email'] == k] for k, val in itertools.groupby(messages, lambda x: x['email'])}
        return messages_by_email

    def send_notif_todo_email(self, cr, uid, ids=None, context=None):

        mail_mail = self.pool.get('mail.mail')
        mail_ids = []
        mess_by_email = self._get_messages_by_email(cr, uid, ids=None, context=None)
        if mess_by_email:
            try:
                for k,v in mess_by_email.iteritems():
                    #_logger.info('%s -> %s', k, v)
                    email_from = k
                    subject = "Today work need to be done"
                    body = "Good morning,<br/> Here are tasks need to be done to day:<br/>"
                    for i in v:
                        body += "<h5>- %s (%s) on lead: %s</h5><br/>" %(i['action_name'], i['title'], i['lead_name'])
                    body += "<br/> Have a Nice day!"
                    #_logger.info('%s', body)

                    mail_ids.append(mail_mail.create(cr, uid, {
                        'email_to': email_from,
                        'subject': subject,
                        'body_html': body
                    }, context=context))
                mail_mail.send(cr, uid, mail_ids, context=context)
            except Exception, e:
                print "Exception", e
        return None
