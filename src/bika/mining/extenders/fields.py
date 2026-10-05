# -*- coding: utf-8 -*-
from archetypes.schemaextender.field import ExtensionField
from Products.Archetypes.public import FloatField, StringField
from bika.lims.browser.fields import UIDReferenceField


class ExtUIDReferenceField(ExtensionField, UIDReferenceField):
    """Annotation-backed sample lookup."""


class ExtFloatField(ExtensionField, FloatField):
    """Annotation-backed numeric sample field."""


class ExtStringField(ExtensionField, StringField):
    """Annotation-backed publication status."""
