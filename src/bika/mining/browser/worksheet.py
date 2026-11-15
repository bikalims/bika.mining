# -*- coding: utf-8 -*-
from collections import OrderedDict

from bika.lims import api
from bika.lims.browser.worksheet.views.add_analyses import (
    AddAnalysesView as LegacyAddAnalysesView)
from bika.mining import _
from senaite.core.browser.worksheets.worksheet.add_analyses import AddAnalysesView


class MatrixReferenceColumns(object):
    """Show and sort analyses by their sample's Matrix Reference."""

    def __init__(self, context, request):
        super(MatrixReferenceColumns, self).__init__(context, request)
        columns = OrderedDict()
        for name, column in self.columns.items():
            columns[name] = column
            if name == "getRequestID":
                columns["MatrixReference"] = {
                    "title": _(u"Matrix Reference"),
                    "sortable": True,
                    "toggle": True,
                }
        self.columns = columns
        for state in self.review_states:
            state["columns"] = list(columns)

    def matrix_reference_title(self, analysis):
        sample = api.get_object(analysis).getRequest()
        field = sample.Schema().getField("MatrixReference")
        matrix = field.get(sample) if field is not None else None
        return api.get_title(matrix) if matrix is not None else u""

    def folderitem(self, obj, item, index):
        item = super(MatrixReferenceColumns, self).folderitem(obj, item, index)
        item["MatrixReference"] = self.matrix_reference_title(obj)
        return item

    def sort_brains(self, brains, sort_on=None, instance_fallback=True):
        if sort_on == "MatrixReference":
            # Listing search sorts all matches before applying pagination.
            return sorted(brains, key=lambda brain:
                          self.matrix_reference_title(brain).lower(),
                          reverse=self.get_sort_order() == "descending")
        return super(MatrixReferenceColumns, self).sort_brains(
            brains, sort_on=sort_on, instance_fallback=instance_fallback)


class MiningAddAnalysesView(MatrixReferenceColumns, LegacyAddAnalysesView):
    """Mining columns for Archetypes worksheets."""


class MiningDexterityAddAnalysesView(MatrixReferenceColumns, AddAnalysesView):
    """Mining columns for Dexterity worksheets."""
