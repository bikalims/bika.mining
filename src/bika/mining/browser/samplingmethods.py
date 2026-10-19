# -*- coding: utf-8 -*-
from bika.mining import _
from senaite.core.browser.controlpanel.samplingdeviations.view import SamplingDeviationsView


class SamplingMethodsView(SamplingDeviationsView):
    """Use mining terminology for the existing sampling lookup listing."""

    def __init__(self, context, request):
        super(SamplingMethodsView, self).__init__(context, request)
        self.title = _(u"Sampling Methods")
        self.columns["Title"]["title"] = _(u"Sampling Method")
