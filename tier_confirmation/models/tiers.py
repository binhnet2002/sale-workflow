# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from openerp.exceptions import ValidationError
from openerp.tools.safe_eval import safe_eval

from lxml import etree


# yellow msg after header? see https://github.com/OCA/social/pull/210 and
# base_exception.

# auto add elements to a view: https://github.com/OCA/stock-logistics-workflow/pull/370/files

class TierValidation(models.AbstractModel):
    _name = "tier.validation"

    _state_field = 'state'
    _state_from = 'draft'
    _state_to = 'confirmed'

    # compute_need_validation_process -> show button "request validation".

    # TODO: able to search by reviewers ids?
    reviewer_id = fields.Many2one(
        comodel_name="res.users", name="Reviewer?¿"
    )
    review_ids = fields.One2many(
        comodel_name='tier.review', inverse_name='res_id',
        string='Validations',
        domain=lambda self: [('model', '=', self._name)],
        auto_join=True,
    )
    validated = fields.Boolean(compute="_compute_validated")
    need_validation = fields.Boolean(
        compute="_compute_need_validation",
        store=True,
    )

    @api.multi
    def _compute_validated(self):
        """Override for different validation policy."""
        for rec in self:
            # sort by tier
            rec.validated = not any(
                [s != 'approved' for s in self.review_ids.mapped('status')])

    @api.multi
    def _compute_need_validation(self):
        for rec in self:
            rec.need_validation = not self.review_ids and self.env[
                'tier.definition'].search([('model', '=', self._name)])

    @api.multi
    def evaluate_tier(self, tier):
        # evaluate if the expression in the tier.definition is true.
        # TODO: maybe and improvement:
        # https://github.com/OCA/server-tools/blob/10.0/base_exception/models/base_exception.py#L178
        return safe_eval(tier.python_code, globals_dict={'rec': self})

    @api.multi
    def write(self, vals):
        td_obj = self.env['tier.definition']
        tr_obj = self.env['tier.review']
        for rec in self:
            if (getattr(rec, self._state_field) == self._state_from and
                    vals.get(self._state_field) == self._state_to):
                if rec.need_validation:
                    raise ValidationError(_(
                        "This action needs to be validated for at least one "
                        "record. \nPlease request a validation."))
                if not rec.validated:
                    raise ValidationError(_(
                        "A validation process is still open for at least "
                        "one record."))
        if vals.get(self._state_field) == self._state_from:
            self.mapped('review_ids').sudo().unlink()
        return super(TierValidation, self).write(vals)

    @api.multi
    def validate_tier(self):
        for rec in self:
            user_reviews = rec.review_ids.filtered(
                lambda r: r.status == 'pending' and
                (r.reviewer_id == self.env.user or
                 r.reviewer_group_id in self.env.user.groups_id))
            user_reviews.write({'status': 'approved'})

    @api.multi
    def reject_tier(self):
        for rec in self:
            user_reviews = rec.review_ids.filtered(
                lambda r: r.status == 'pending' and
                (r.reviewer_id == self.env.user or
                 r.reviewer_group_id in self.env.user.groups_id))
            user_reviews.write({'status': 'rejected'})

    @api.multi
    def request_validation(self):
        td_obj = self.env['tier.definition']
        tr_obj = self.env['tier.review']
        for rec in self:
            if getattr(rec, self._state_field) == self._state_from:
                if rec.need_validation:
                    tier_definitions = td_obj.search([
                        ('model', '=', self._name)], order="sequence desc")
                    sequence = 0
                    for td in tier_definitions:
                        if self.evaluate_tier(td):
                            sequence += 1
                            tr_obj.create({
                                'model': self._name,
                                'res_id': rec.id,
                                'definition_id': td.id,
                                'sequence': sequence,
                            })
                    # TODO: notify? post some msg in chatter?
        return True

    @api.model
    def _get_warning_xml_string(self):
        """Override for a different under-validation message."""
        return """
            <p><i class="fa fa-info-circle"/> Test test <b>Emails Sent</b>
            smart-butto.</p>
        """
    # TODO: cannot add fields in this text... why?

    @api.model
    def _get_success_xml_string(self):
        """Override for a different validation message."""
        return """<p>Operation has been validated!</p>"""

    @api.model
    def _get_danger_xml_string(self):
        """Override for a different rejection message."""
        return """<p>Operation has been rejected.</p>"""

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False,
                        submenu=False):
        """Alter view of tier.validation objects."""
        res = super(TierValidation, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar,
            submenu=submenu)
        eview = etree.fromstring(res['arch'])
        xml_header = eview.xpath("//header")
        xml_form = eview.xpath("//form")
        if not xml_form and not xml_header:
            return res
        # TODO: fix this.
        # FIXME: works with name but not with reviewer_id for instance.
        need_validation = etree.Element(
            'field', {
                'name': 'name',
                'modifiers': '{"invisible": 1}',
            }
        )
        alert_warning = etree.Element(
            'div', {
                'class': 'alert alert-warning',
                # 'attrs': "{'invisible': [('state', '!=', 'draft')]}",
                'modifiers': '{"invisible": [["state", "=", "draft"]]}',
                'style': 'margin-bottom:0px;',
            })
        alert_success = etree.Element(
            'div', {
                'class': 'alert alert-success',
                'modifiers': '{"invisible": [["state", "!=", "draft"]]}',
            })
        alert_danger = etree.Element(
            'div', {
                'class': 'alert alert-danger',
                'modifiers': '{"invisible": 1}',
            })
        warning_p = etree.fromstring(self._get_warning_xml_string())
        success_p = etree.fromstring(self._get_success_xml_string())
        alert_warning.append(warning_p)
        alert_success.append(success_p)
        position = xml_form[0].index(xml_header[0]) + 1 if xml_header else 0
        for alert in [need_validation, alert_warning, alert_success,
                      alert_danger]:
            xml_form[0].insert(position, alert)
        res['arch'] = etree.tostring(eview)
        return res


class TierReview(models.Model):
    _name = "tier.review"

    status = fields.Selection(
        selection=[("pending", "Pending"),
                   ("rejected", "Rejected"),
                   ("approved", "Approved")],
        default="pending",
    )
    model = fields.Char(string='Related Document Model', index=True)
    res_id = fields.Integer(string='Related Document ID', index=True)
    definition_id = fields.Many2one(
        comodel_name="tier.definition",
    )
    review_type = fields.Selection(
        related="definition_id.review_type", readonly=True,
    )
    reviewer_id = fields.Many2one(
        related="definition_id.reviewer_id", readonly=True,
    )
    reviewer_group_id = fields.Many2one(
        related="definition_id.reviewer_group_id", readonly=True,
    )
    sequence = fields.Integer(string="Tier")
    # TODO: coloring background depending on status?


class TierDefinition(models.Model):
    _name = "tier.definition"  # tier.validation.line ??

    model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Referenced Model",
    )  # TODO: add domain to tier.validation models.
    model = fields.Char(
        related='model_id.model', index=True, store=True,
    )
    review_type = fields.Selection(
        string="Validated by", default="individual",
        selection=[("individual", "Specific user"),
                   ("group", "Any user in a specific group.")]
    )
    reviewer_id = fields.Many2one(
        comodel_name="res.users", string="Reviewer",
    )
    reviewer_group_id = fields.Many2one(
        comodel_name="res.groups", string="Reviewer group",
    )
    python_code = fields.Text(
        string='Tier Definition Expression',
        help="Write Python code that defines when this tier confirmation "
             "will be needed. The result of executing the expresion must be "
             "a boolean.",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=30)
    company_id = fields.Many2one(
        comodel_name="res.company", string="Company",
        default=lambda self: self.env["res.company"]._company_default_get(
                "tier.definition"),
    )

    # python formula
    # parent and child logic. or sequence/priority. same sequence any of them
        # validates the tier, more sequence validates, less squeence need
        # validation of above sequence.

    # notification hacia arriba.

    # readonly con ir.rules??