# -*- coding: utf-8 -*-
from bika.mining.interfaces import IMatrixReferences
from plone.dexterity.content import Container
from plone.supermodel import model
from senaite.core.interfaces import IHideActionsMenu
from zope.interface import implementer


class IMatrixReferencesSchema(model.Schema):
    """Matrix References folder schema."""


@implementer(IMatrixReferences, IMatrixReferencesSchema, IHideActionsMenu)
class MatrixReferences(Container):
    """Setup lookup table for recurring plant samples."""
