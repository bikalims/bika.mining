# -*- coding: utf-8 -*-
"""Mining publication uses XLSX in the existing report binary field."""
from AccessControl import Unauthorized
from DateTime import DateTime
from bika.lims import api
from bika.lims.interfaces import IAnalysisRequest
from bika.lims.browser.publish.downloadview import DownloadView
from bika.lims.browser.publish.emailview import EmailView
from bika.lims.browser.workflow.client import WorkflowActionDownloadReportsAdapter
from bika.lims.browser.workflow.client import WorkflowActionPublishSamplesAdapter
from bika.lims.utils import get_link
from bika.mining import _
from bika.mining.config import is_installed
from bika.mining.resultsxlsx import MIME_TYPE, render_results
from bika.mining.tat import actual_tat, target_hours
from plone import protect
from plone.namedfile.file import NamedBlobFile
from Products.Five.browser import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from senaite.app.listing.interfaces import IListingViewAdapter
from senaite.core.permissions import ManageAnalysisRequests
from zope.interface import implementer
from zExceptions import BadRequest
from io import BytesIO
import zipfile


def title(value):
    return api.get_title(value) if value else u""


def sample_field(sample, name):
    field = sample.Schema().getField(name)
    return field.get(sample) if field is not None else None


def sample_row(sample):
    received = sample.getDateReceived()
    point = sample.getSamplePoint()
    analysts = [api.get_user_fullname(user) for user in sample.getAnalysts()
                if user]
    metadata = {
        "A": sample.getId(), "B": title(sample_field(sample, "MatrixReference")),
        "C": title(point), "D": point.Description() if point else u"",
        "E": sample.getSampleTypeTitle(), "F": sample.getPriorityText(),
        "G": title(sample_field(sample, "Classification")),
        "H": title(sample_field(sample, "DrumBatch")),
        "I": title(sample_field(sample, "Shift")),
        "J": received.strftime("%Y-%m-%d") if received else u"",
        "K": received.strftime("%H:%M") if received else u"",
        "L": u", ".join(analysts), "M": target_hours(sample),
        "N": actual_tat(sample), "O": sample_field(sample, "TATStatus"),
    }
    results = {}
    for analysis in sample.getAnalyses(full_objects=True):
        if analysis.getHidden():
            continue
        if analysis.getResult() in (None, ""):
            continue
        name = analysis.getService().Title()
        if name in results:
            raise ValueError("Duplicate AS Title on sample {}: {}".format(
                sample.getId(), name))
        results[name] = analysis.getFormattedResult(html=False)
    return {"metadata": metadata, "results": results}


class ResultsXLSXView(BrowserView):
    template = ViewPageTemplateFile("templates/resultsxlsx.pt")

    def samples(self):
        items = self.request.get("items", "")
        uids = ([uid for uid in items.split(",") if uid]
                if isinstance(items, basestring) else items)
        if not uids and IAnalysisRequest.providedBy(self.context):
            uids = [api.get_uid(self.context)]
        samples = []
        for uid in uids:
            sample = (api.get_object_by_uid(uid, default=None)
                      if api.is_uid(uid) else None)
            if sample is None or not IAnalysisRequest.providedBy(sample):
                raise ValueError("Select valid samples for Results XLSX")
            if not api.get_tool("portal_membership").checkPermission(
                    "View", sample):
                raise Unauthorized
            if sample not in samples:
                samples.append(sample)
        if not samples:
            raise ValueError("Select samples for Results XLSX")
        return samples

    def __call__(self):
        self.selected_samples = self.samples()
        self.items = ",".join(api.get_uid(s) for s in self.selected_samples)
        self.error = None
        self.can_publish = all(api.get_workflow_status_of(s) in
                               ("verified", "published")
                               for s in self.selected_samples)
        action = self.request.form.get("action")
        if action == "download":
            try:
                data = render_results([sample_row(s) for s in self.selected_samples])
            except ValueError as error:
                self.error = api.safe_unicode(error)
                return self.template()
            return self.download(data)
        if action == "publish":
            if self.request.method != "POST":
                raise Unauthorized
            protect.CheckAuthenticator(self.request)
            membership = api.get_tool("portal_membership")
            workflow = api.get_tool("portal_workflow")
            for sample in self.selected_samples:
                if not membership.checkPermission(
                        ManageAnalysisRequests, sample):
                    raise Unauthorized
            if not self.can_publish:
                self.error = u"Only verified or published samples can be published"
                return self.template()
            if len(set(s.getClientUID() for s in self.selected_samples)) > 1:
                self.error = u"Publish samples for one client at a time"
                return self.template()
            # Validate all title mappings before changing workflow state.
            try:
                render_results([sample_row(s) for s in self.selected_samples])
            except ValueError as error:
                self.error = api.safe_unicode(error)
                return self.template()
            for sample in self.selected_samples:
                transition = ("republish" if api.get_workflow_status_of(sample)
                              == "published" else "publish")
                workflow.doActionFor(sample, transition)
            data = render_results([sample_row(s) for s in self.selected_samples])
            uids = [api.get_uid(s) for s in self.selected_samples]
            for sample in self.selected_samples:
                api.create(sample, "ResultsReport", sample=api.get_uid(sample),
                           contained_samples=uids,
                           pdf=NamedBlobFile(data=data, filename=u"Results.xlsx",
                                             contentType=MIME_TYPE),
                           metadata={"format": u"xlsx", "template": u"Lotus Results XLSX",
                                     "timestamp": api.safe_unicode(DateTime().ISO8601())})
            return self.download(data)
        return self.template()

    def download(self, data):
        self.request.response.setHeader("Content-Type", MIME_TYPE)
        self.request.response.setHeader("Content-Disposition",
                                       'attachment; filename="Results.xlsx"')
        self.request.response.setHeader("Content-Length", len(data))
        self.request.response.setHeader("Cache-Control", "no-store")
        return data


class XLSXPublicationOnly(BrowserView):
    """Prevent the old HTML-to-PDF AJAX endpoint on mining sites."""
    def __call__(self):
        raise BadRequest("Use Results XLSX to publish mining results")


class ReportDownloadView(DownloadView):
    def __call__(self):
        blob = self.context.getPdf()
        if blob and blob.contentType == MIME_TYPE:
            return self.download(blob.data, blob.filename, MIME_TYPE)
        return super(ReportDownloadView, self).__call__()


class ReportEmailView(EmailView):
    def get_report_filename(self, report):
        blob = report.getPdf()
        if blob and blob.contentType == MIME_TYPE:
            return u"{}.xlsx".format(api.get_id(report.getSample()))
        return super(ReportEmailView, self).get_report_filename(report)


class DownloadReportsAdapter(WorkflowActionDownloadReportsAdapter):
    def __call__(self, action, uids):
        reports = [api.get_object_by_uid(uid) for uid in uids]
        files = []
        for report in reports:
            if not api.get_tool("portal_membership").checkPermission("View", report):
                raise Unauthorized
            blob = self.get_pdf(report)
            if blob is None:
                continue
            extension = "xlsx" if blob.contentType == MIME_TYPE else "pdf"
            filename = u"{}-{}.{}".format(
                api.get_id(report.getSample()), api.get_id(report), extension)
            files.append((filename, blob))
        if len(files) == 1:
            filename, blob = files[0]
            return self.download(blob.data, filename, type=blob.contentType)
        output = BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for filename, blob in files:
                archive.writestr(filename, blob.data)
        return self.download(output.getvalue(), "Results.zip", type="application/zip")


class PublishReportsAdapter(WorkflowActionPublishSamplesAdapter):
    def get_sample_uids_in_report(self, report):
        return report.getContainedSampleUIDs() or [report.getSampleUID()]


@implementer(IListingViewAdapter)
class ResultsListingAdapter(object):
    def __init__(self, listing, context):
        self.listing = listing
        self.context = context

    def before_render(self):
        if is_installed():
            self.listing.columns["PDF"]["title"] = _(u"Download XLSX")

    def folder_item(self, obj, item, index):
        if not is_installed():
            return item
        report = api.get_object(obj)
        blob = report.getPdf()
        if blob and blob.contentType == MIME_TYPE:
            item.setdefault("replace", {})["PDF"] = get_link(
                report.absolute_url() + "/download_pdf", value="XLSX")
        return item
