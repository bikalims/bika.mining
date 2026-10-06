# -*- coding: utf-8 -*-
from AccessControl import ClassSecurityInfo
from bika.lims import api
from bika.lims.interfaces import IDeactivable
from bika.mining import _
from bika.mining.interfaces import IMatrixReference
from plone.autoform import directives
from plone.dexterity.content import Item
from plone.supermodel import model
from senaite.core.catalog import SETUP_CATALOG
from senaite.core.schema import UIDReferenceField
from senaite.core.z3cform.widgets.uidreference import UIDReferenceWidgetFactory
from zope import schema
from zope.interface import implementer


class IMatrixReferenceSchema(model.Schema):
    """Information shared by recurring samples at the plant."""

    title = schema.TextLine(title=_(u"Matrix Ref"), required=True)
    area = schema.TextLine(title=_(u"Area"), required=False)
    circuit_area = schema.TextLine(title=_(u"Circuit / Area"), required=False)

    # No client or path restriction: include setup and all clients' points.
    directives.widget(
        "plant_sample_id", UIDReferenceWidgetFactory,
        catalog=SETUP_CATALOG,
        query={"is_active": True, "sort_on": "title"},
        columns=[{"name": "Title", "label": _(u"Sample Point")},
                 {"name": "Description", "label": _(u"Description")}],
    )
    plant_sample_id = UIDReferenceField(
        title=_(u"Plant Sample ID"),
        description=_(u"Select a Sample Point from setup or any client."),
        allowed_types=("SamplePoint",), multi_valued=False,
        relationship="MatrixReferenceSamplePoint", required=False,
    )
    target_tat = schema.Float(
        title=_(u"Target TAT (h)"), min=0.0, required=False,
    )
    directives.widget(
        "sample_type", UIDReferenceWidgetFactory,
        catalog=SETUP_CATALOG,
        query={"is_active": True, "sort_on": "title"},
    )
    sample_type = UIDReferenceField(
        title=_(u"Sample Type"), allowed_types=("SampleType",),
        multi_valued=False, relationship="MatrixReferenceSampleType",
        required=False,
    )


class SetupItem(Item):
    """Common catalog and schema access support for setup records."""

    _catalogs = [SETUP_CATALOG]
    security = ClassSecurityInfo()

    @security.private
    def accessor(self, fieldname):
        field = api.get_schema(self).get(fieldname)
        return field.get if field is not None else None

    @security.private
    def mutator(self, fieldname):
        field = api.get_schema(self).get(fieldname)
        if field is None:
            return None

        def set_value(context, value):
            field.set(context, value)
            context.reindexObject()
        return set_value


@implementer(IMatrixReference, IMatrixReferenceSchema, IDeactivable)
class MatrixReference(SetupItem):
    """Setup record referenced by samples rather than copied into them."""
