# -*- coding: utf-8 -*-
from bika.lims.interfaces import IDeactivable
from bika.mining import _
from bika.mining.interfaces import IClassification, IClassifications
from bika.mining.interfaces import IDrumBatch, IDrumBatches
from bika.mining.interfaces import IShift, IShifts
from bika.mining.content.matrixreference import SetupItem
from plone.dexterity.content import Container
from plone.supermodel import model
from senaite.core.interfaces import IHideActionsMenu
from zope import schema
from zope.interface import implementer


class ILookupSchema(model.Schema):
    title = schema.TextLine(title=_(u"Title"), required=True)
    description = schema.Text(title=_(u"Description"), required=False)


class ILookupFolderSchema(model.Schema):
    """Setup lookup container schema."""


@implementer(IShift, ILookupSchema, IDeactivable)
class Shift(SetupItem):
    """Shift code and description, e.g. DS / Day shift."""


@implementer(IClassification, ILookupSchema, IDeactivable)
class Classification(SetupItem):
    """Process classification, e.g. Heads or Tails."""


@implementer(IDrumBatch, ILookupSchema, IDeactivable)
class DrumBatch(SetupItem):
    """Drum or batch designation, including percentage values."""


@implementer(IShifts, ILookupFolderSchema, IHideActionsMenu)
class Shifts(Container):
    """Shift setup table."""


@implementer(IClassifications, ILookupFolderSchema, IHideActionsMenu)
class Classifications(Container):
    """Classification setup table."""


@implementer(IDrumBatches, ILookupFolderSchema, IHideActionsMenu)
class DrumBatches(Container):
    """Drum/Batch setup table."""
