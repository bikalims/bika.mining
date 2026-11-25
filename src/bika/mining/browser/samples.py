# -*- coding: utf-8 -*-
from bika.lims import api
from bika.lims.utils import get_link_for
from bika.mining import _
from bika.mining.config import is_installed
from bika.mining.tat import actual_tat, target_hours
from senaite.app.listing.interfaces import IListingViewAdapter
from senaite.core.i18n import translate
from bika.lims import _ as core_message
from zope.interface import implementer


@implementer(IListingViewAdapter)
class SamplesListingViewAdapter(object):
    def __init__(self, listing, context):
        self.listing = listing
        self.context = context

    def before_render(self):
        if not is_installed():
            return
        self.listing.columns["MatrixReference"] = {
            "title": _(u"Matrix Reference"), "toggle": True}
        for state in self.listing.review_states:
            columns = state["columns"]
            if "MatrixReference" not in columns:
                position = (columns.index("getId") + 1
                            if "getId" in columns else 0)
                columns.insert(position, "MatrixReference")
        for name, title in (("TimeTransferred", u"Time Transferred"),
                            ("TargetTAT", u"Target TAT (h)"),
                            ("TAT", u"TAT (h)")):
            self.listing.columns[name] = {"title": _(title), "toggle": True}
            for state in self.listing.review_states:
                if name not in state["columns"]:
                    state["columns"].append(name)

    def folder_item(self, obj, item, index):
        if not is_installed():
            return item
        sample = api.get_object(obj)
        field = sample.Schema().getField("MatrixReference")
        matrix = field.get(sample) if field is not None else None
        item["MatrixReference"] = (
            api.get_title(matrix) if matrix is not None else u"")
        if matrix is not None:
            item.setdefault("replace", {})["MatrixReference"] = get_link_for(
                matrix)
        field = sample.Schema().getField("TimeTransferred")
        transferred = field.get(sample) if field is not None else None
        item["TimeTransferred"] = self.listing.str_date(transferred)
        for name, value in (("TargetTAT", target_hours(sample)),
                            ("TAT", actual_tat(sample))):
            item[name] = ("" if value is None else
                          ("{:.2f}" if name == "TAT" else "{:g}").format(value))
        if target_hours(sample) is not None:
            icons = item.get("after", {}).get("getId", "")
            item.setdefault("after", {})["getId"] = icons.replace(
                translate(core_message("Late Analyses")),
                translate(_(u"Late Sample")))
        return item
