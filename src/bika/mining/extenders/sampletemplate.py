# -*- coding: utf-8 -*-
from bika.mining import _
from plone.autoform import directives
from plone.autoform.interfaces import IFormFieldProvider
from plone.supermodel import model
from senaite.core.catalog import SETUP_CATALOG
from senaite.core.schema import UIDReferenceField
from senaite.core.content.sampletemplate import ISampleTemplateSchema
from senaite.core.z3cform.widgets.uidreference import UIDReferenceWidgetFactory
from zope import schema
from zope.interface import implementer, provider


class IMiningSampleTemplateSchema(ISampleTemplateSchema):
    """Mining templates use Sampling Method instead of Composite."""

    directives.omitted("composite")


@provider(IFormFieldProvider)
class IMiningSampleTemplate(model.Schema):
    directives.widget(
        "sampling_method", UIDReferenceWidgetFactory,
        catalog=SETUP_CATALOG,
        query={"is_active": True, "sort_on": "title"},
    )
    sampling_method = UIDReferenceField(
        title=_(u"Sampling Method"), allowed_types=("SamplingDeviation",),
        description=_(u"Default sampling method for samples using this template."),
        multi_valued=False, relationship="SampleTemplateSamplingMethod",
        required=False,
    )
    directives.widget(
        "matrix_reference", UIDReferenceWidgetFactory,
        catalog=SETUP_CATALOG,
        query={"is_active": True, "sort_on": "title"},
    )
    matrix_reference = UIDReferenceField(
        title=_(u"Matrix Reference"), allowed_types=("MatrixReference",),
        description=_(u"Default matrix reference for samples using this template. "
                      u"On save, it supplies the sample point, sample type and "
                      u"target turnaround time where these are blank."),
        multi_valued=False, relationship="SampleTemplateMatrixReference",
        required=False,
    )
    target_tat = schema.Float(
        title=_(u"Target TAT (h)"), min=0.0, required=False,
        description=_(u"Default turnaround time in hours from laboratory receipt "
                      u"to results publication. Leave blank to use the selected "
                      u"matrix reference's target."),
    )


@implementer(IMiningSampleTemplate)
class MiningSampleTemplate(object):
    """Store template defaults on the content object."""

    def __init__(self, context):
        self.context = context

    @property
    def sampling_method(self):
        return getattr(self.context, "sampling_method", None)

    @sampling_method.setter
    def sampling_method(self, value):
        self.context.sampling_method = value

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
