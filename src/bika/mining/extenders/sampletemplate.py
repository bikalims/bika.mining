# -*- coding: utf-8 -*-
from bika.mining import _
from plone.autoform import directives
from plone.autoform.interfaces import IFormFieldProvider
from plone.supermodel import model
from senaite.core.catalog import SETUP_CATALOG
from senaite.core.schema import UIDReferenceField
from senaite.core.z3cform.widgets.uidreference import UIDReferenceWidgetFactory
from zope import schema
from zope.interface import implementer, provider


@provider(IFormFieldProvider)
class IMiningSampleTemplate(model.Schema):
    directives.widget(
        "matrix_reference", UIDReferenceWidgetFactory,
        catalog=SETUP_CATALOG,
        query={"is_active": True, "sort_on": "title"},
    )
    matrix_reference = UIDReferenceField(
        title=_(u"Matrix Reference"), allowed_types=("MatrixReference",),
        multi_valued=False, relationship="SampleTemplateMatrixReference",
        required=False,
    )
    target_tat = schema.Float(
        title=_(u"Target TAT (h)"), min=0.0, required=False,
    )


@implementer(IMiningSampleTemplate)
class MiningSampleTemplate(object):
    """Store template defaults on the content object."""

    def __init__(self, context):
        self.context = context

    @property
    def matrix_reference(self):
        return getattr(self.context, "matrix_reference", None)

    @matrix_reference.setter
    def matrix_reference(self, value):
        self.context.matrix_reference = value

    @property
    def target_tat(self):
        return getattr(self.context, "target_tat", None)

    @target_tat.setter
    def target_tat(self, value):
        self.context.target_tat = value
