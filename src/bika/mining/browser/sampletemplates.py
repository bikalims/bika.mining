# -*- coding: utf-8 -*-
from bika.lims import api
from bika.mining import _
from bika.mining.config import is_installed
from bika.mining.extenders.sampletemplate import IMiningSampleTemplate
from senaite.app.listing.interfaces import IListingViewAdapter
from zope.interface import implementer


@implementer(IListingViewAdapter)
class SampleTemplatesListingViewAdapter(object):
    def __init__(self, listing, context):
        self.listing = listing
        self.context = context

    def before_render(self):
        if not is_installed():
            return
        for name, title in (("SamplePoint", u"Sample Point"),
                            ("SampleType", u"Sample Type"),
                            ("SamplingMethod", u"Sampling Method"),
                            ("MatrixReference", u"Matrix Reference"),
                            ("TargetTAT", u"Target TAT (h)")):
            self.listing.columns[name] = {"title": _(title), "toggle": True}
            for state in self.listing.review_states:
                if name not in state["columns"]:
                    state["columns"].append(name)

    def folder_item(self, obj, item, index):
        if not is_installed():
            return item
        template = api.get_object(obj)
        defaults = IMiningSampleTemplate(template)
        method = IMiningSampleTemplate["sampling_method"].get(defaults)
        matrix = IMiningSampleTemplate["matrix_reference"].get(defaults)
        for name, value in (("SamplePoint", template.getSamplePoint()),
                            ("SampleType", template.getSampleType()),
                            ("SamplingMethod", method),
                            ("MatrixReference", matrix)):
            item[name] = api.get_title(value) if value is not None else u""
        target = defaults.target_tat
        if target is None and matrix is not None:
            target = matrix.target_tat
        item["TargetTAT"] = "" if target is None else "{:g}".format(target)
        return item
