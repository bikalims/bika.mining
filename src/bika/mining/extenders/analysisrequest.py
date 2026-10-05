# -*- coding: utf-8 -*-
from archetypes.schemaextender.interfaces import IBrowserLayerAwareExtender
from archetypes.schemaextender.interfaces import ISchemaExtender
from bika.lims import FieldEditContact
from bika.lims.interfaces import IAnalysisRequest
from bika.mining import _
from bika.mining.extenders.fields import ExtFloatField, ExtStringField
from bika.mining.extenders.fields import ExtUIDReferenceField
from bika.mining.interfaces import IBikaMiningLayer
from Products.Archetypes.Widget import DecimalWidget, StringWidget
from Products.CMFCore.permissions import View
from senaite.core.browser.widgets.referencewidget import ReferenceWidget
from zope.component import adapts
from zope.interface import implementer


def reference_field(name, portal_type, label):
    return ExtUIDReferenceField(
        name, required=False, allowed_types=(portal_type,),
        relationship="AnalysisRequest" + name, format="select", mode="rw",
        read_permission=View, write_permission=FieldEditContact,
        widget=ReferenceWidget(
            label=_(label), render_own_label=True, showOn=True,
            catalog_name="senaite_catalog_setup",
            base_query={"is_active": True, "sort_on": "sortable_title"},
            visible={"add": "edit", "header_table": "visible",
                     "secondary": "disabled", "verified": "view",
                     "published": "view"},
            ui_item="title",
            colModel=[dict(columnName="UID", hidden=True),
                      dict(columnName="title", label=_(label))],
        ),
    )


def validate_target_tat(value):
    """Allow blank targets; reject negative and non-finite hours."""
    if value in (None, ""):
        return True
    try:
        hours = float(value)
    except (TypeError, ValueError):
        return "Target TAT must be a number of hours"
    if not 0 <= hours < float("inf"):
        return "Target TAT must be a finite, non-negative number of hours"
    return True


@implementer(ISchemaExtender, IBrowserLayerAwareExtender)
class AnalysisRequestSchemaExtender(object):
    adapts(IAnalysisRequest)
    layer = IBikaMiningLayer

    fields = [
        reference_field("MatrixReference", "MatrixReference", u"Matrix Reference"),
        reference_field("Shift", "Shift", u"Shift"),
        reference_field("Classification", "Classification", u"Classification"),
        reference_field("DrumBatch", "DrumBatch", u"Drum/Batch"),
        ExtFloatField(
            "TargetTAT", required=False, default=None,
            validators=(validate_target_tat,),
            read_permission=View, write_permission=FieldEditContact,
            widget=DecimalWidget(
                label=_(u"Target TAT (h)"), render_own_label=True,
                visible={"add": "edit", "header_table": "visible",
                         "secondary": "disabled", "verified": "view",
                         "published": "view"},
            ),
        ),
        ExtStringField(
            "TATStatus", required=False, mode="r", read_permission=View,
            widget=StringWidget(
                label=_(u"TAT Status"), render_own_label=True,
                visible={"add": "invisible", "edit": "invisible",
                         "header_table": "visible"},
            ),
        ),
    ]

    def __init__(self, context):
        self.context = context

    def getFields(self):
        return self.fields

    def getOrder(self, schematas):
        return schematas
