# -*- coding: utf-8 -*-
"""Module where all interfaces, events and exceptions live."""

from zope.publisher.interfaces.browser import IDefaultBrowserLayer
from zope.interface import Interface


class IBikaMiningLayer(IDefaultBrowserLayer):
    """Marker interface that defines a browser layer."""


class IMatrixReference(Interface):
    """A recurring plant sample reference, distinct from SampleMatrix."""


class IMatrixReferences(Interface):
    """Matrix Reference setup folder."""


class IShift(Interface):
    """A lab-managed shift."""


class IShifts(Interface):
    """Shift setup folder."""


class IClassification(Interface):
    """A process sample classification."""


class IClassifications(Interface):
    """Classification setup folder."""


class IDrumBatch(Interface):
    """A drum or batch value."""


class IDrumBatches(Interface):
    """Drum/Batch setup folder."""
