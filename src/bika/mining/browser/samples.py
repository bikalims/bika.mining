# -*- coding: utf-8 -*-
from bika.lims import api
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
        for name, title in (("TargetTAT", u"Target TAT (h)"),
                            ("TAT", u"TAT (h)")):
            self.listing.columns[name] = {"title": _(title), "toggle": True}
            for state in self.listing.review_states:
                if name not in state["columns"]:
                    state["columns"].append(name)

    def folder_item(self, obj, item, index):
        if not is_installed():
            return item
        sample = api.get_object(obj)
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
