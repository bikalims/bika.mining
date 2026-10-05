# -*- coding: utf-8 -*-
from collections import OrderedDict
from bika.lims import api
from bika.lims.utils import get_link_for
from bika.mining import _
from bika.mining.permissions import AddMatrixReference, AddShift
from bika.mining.permissions import AddClassification, AddDrumBatch
from senaite.app.listing import ListingView


class SetupLookupView(ListingView):
    """Manage active and inactive lookup values without losing references."""

    item_type = None
    heading = None
    add_permission = None

    def __init__(self, context, request):
        super(SetupLookupView, self).__init__(context, request)
        self.catalog = "senaite_catalog_setup"
        self.contentFilter = {
            "portal_type": self.item_type, "sort_on": "sortable_title",
            "path": {"query": api.get_path(context), "depth": 1},
        }
        self.context_actions = {_(u"Add"): {
            "url": "++add++" + self.item_type,
            "permission": self.add_permission,
            "icon": "senaite_theme/icon/plus",
        }}
        self.title = self.heading
        self.show_select_column = True
        self.columns = self.get_columns()
        self.review_states = [
            {"id": "default", "title": _(u"Active"),
             "contentFilter": {"is_active": True},
             "columns": list(self.columns)},
            {"id": "inactive", "title": _(u"Inactive"),
             "contentFilter": {"is_active": False},
             "columns": list(self.columns)},
            {"id": "all", "title": _(u"All"), "contentFilter": {},
             "columns": list(self.columns)},
        ]

    def get_columns(self):
        return OrderedDict([
            ("Title", {"title": _(u"Title"), "index": "sortable_title"}),
            ("Description", {"title": _(u"Description"), "sortable": False}),
        ])

    def folderitem(self, obj, item, index):
        obj = api.get_object(obj)
        item["replace"]["Title"] = get_link_for(obj)
        item["Description"] = api.get_description(obj)
        return item


class MatrixReferencesView(SetupLookupView):
    item_type = "MatrixReference"
    add_permission = AddMatrixReference
    heading = _(u"Matrix References")

    def get_columns(self):
        columns = OrderedDict([
            ("Title", {"title": _(u"Matrix Ref"), "index": "sortable_title"}),
        ])
        for name, title in [
            ("area", u"Area"), ("circuit_area", u"Circuit / Area"),
            ("plant_sample_id", u"Plant Sample ID"),
            ("sample_point_description", u"Sample Point Description"),
            ("target_tat", u"Target TAT (h)"), ("sample_type", u"Sample Type"),
        ]:
            columns[name] = {"title": _(title), "sortable": False}
        return columns

    def folderitem(self, obj, item, index):
        obj = api.get_object(obj)
        item["replace"]["Title"] = get_link_for(obj)
        for name in ("area", "circuit_area", "sample_point_description",
                     "target_tat"):
            value = getattr(obj, name, None)
            item[name] = value if value is not None else ""
        for name in ("plant_sample_id", "sample_type"):
            target = obj.accessor(name)(obj)
            item[name] = api.get_title(target) if target else ""
            if target:
                item["replace"][name] = get_link_for(target)
        return item


class ShiftsView(SetupLookupView):
    item_type = "Shift"
    add_permission = AddShift
    heading = _(u"Shifts")


class ClassificationsView(SetupLookupView):
    item_type = "Classification"
    add_permission = AddClassification
    heading = _(u"Classifications")


class DrumBatchesView(SetupLookupView):
    item_type = "DrumBatch"
    add_permission = AddDrumBatch
    heading = _(u"Drum/Batch")
