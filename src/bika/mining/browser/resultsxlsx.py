# -*- coding: utf-8 -*-
"""Mining XLSX attachments within the standard report preview/email flow."""
from AccessControl import Unauthorized
from DateTime import DateTime
from bika.lims import api
from bika.lims.interfaces import IAnalysisRequest
from bika.lims.browser.publish.downloadview import DownloadView
from bika.lims.browser.publish.emailview import EmailView
from bika.lims.api import mail as mailapi
from bika.lims.browser.workflow.client import WorkflowActionDownloadReportsAdapter
from bika.lims.browser.workflow.client import WorkflowActionPublishSamplesAdapter
from bika.lims.utils import get_link
from bika.mining import _
from bika.mining.config import is_installed
from bika.mining.idserver import setup_xlsx_format, xlsx_filename
from bika.mining.resultsxlsx import MIME_TYPE, render_results
from bika.mining.tat import actual_tat, target_hours
from plone.namedfile.file import NamedBlobFile
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from senaite.impress.ajax import AjaxPublishView
from senaite.app.listing.interfaces import IListingViewAdapter
from senaite.core.permissions import ManageAnalysisRequests
from zope.interface import implementer
from io import BytesIO
from collections import OrderedDict
from six.moves.urllib.parse import quote
import transaction
import zipfile

try:
    from bika.coa.browser.publish.emailview import EmailView as BaseEmailView
except ImportError:
    BaseEmailView = EmailView

REPORT_TEMPLATE = "bika.mining:MiningResultsXLSXMulti.pt"


def get_xlsx(report):
    blob = getattr(report, "xlsx", None)
    if blob is None:
        # Reports created before the preview/attachment split.
        blob = report.getPdf()
    return blob if blob and blob.contentType == MIME_TYPE else None


def refresh_xlsx(report):
    if getattr(report, "xlsx", None) is None:
        return
    samples = report.getContainedSamples() or [report.getSample()]
    data = render_results([sample_row(sample) for sample in samples],
                          report_header=report_header(report, samples))
    report.xlsx = NamedBlobFile(data=data, filename=report.xlsx.filename,
                               contentType=MIME_TYPE)


def report_header(report, samples):
    published = []
    for sample in samples:
        for history in getattr(sample, "workflow_history", {}).values():
            published.extend(entry for entry in history
                             if entry.get("action") == "publish"
                             and entry.get("review_state") == "published")
    latest = max(published, key=lambda entry: entry["time"]) if published else None
    return {
        "A": title(samples[0].getClient()),
        "C": report.xlsx.filename,
        "E": latest["time"].strftime("%Y-%m-%d %H:%M") if latest else u"",
        "G": (api.get_user_fullname(latest["actor"]) or latest["actor"])
             if latest else u"",
    }


class MiningAjaxPublishView(AjaxPublishView):
    """Add one XLSX template to the standard PDF preview and Save/Email flow."""

    def legacy_view(self):
        try:
            from bika.coa import is_installed as coa_installed
            from bika.coa.ajax import AjaxPublishView as CoaAjaxPublishView
        except ImportError:
            return AjaxPublishView(self.context, self.request)
        if coa_installed():
            return CoaAjaxPublishView(self.context, self.request)
        return AjaxPublishView(self.context, self.request)

    def ajax_templates(self):
        templates = list(self.legacy_view().ajax_templates())
        if REPORT_TEMPLATE not in templates:
            templates.append(REPORT_TEMPLATE)
        return templates

    def ajax_render_reports(self, *args):
        if self.get_json().get("template") == REPORT_TEMPLATE:
            groups = self.selected_groups(self.get_json())
            body = self.read_template(self.get_report_template(REPORT_TEMPLATE), self)
            return u"\n".join(
                u'<div class="report" uids="{}" client_uid="{}">{}</div>'.format(
                    ",".join(api.get_uid(s) for s in samples), client_uid, body)
                for client_uid, samples in groups.items())
        return self.legacy_view().ajax_render_reports(*args)

    def ajax_load_preview(self):
        if self.get_json().get("template") == REPORT_TEMPLATE:
            return super(MiningAjaxPublishView, self).ajax_load_preview()
        return self.legacy_view().ajax_load_preview()

    def ajax_save_reports(self):
        data = self.get_json()
        if data.get("template") != REPORT_TEMPLATE:
            return self.legacy_view().ajax_save_reports()
        if self.request.method != "POST":
            raise Unauthorized
        groups = self.selected_groups(data)
        # Build every workbook before storing any reports.
        workbooks = [(samples, render_results([sample_row(s) for s in samples]))
                     for samples in groups.values()]
        publisher = self.publisher
        publisher.add_inline_css(self.get_print_css(
            paperformat=data.get("format", "A4"),
            orientation=data.get("orientation", "portrait")))
        # The placeholder is generated on the server; submitted preview HTML
        # is never used as the source of either results or sample selection.
        html = '<div class="report"><h1>Mining Results XLSX</h1><p>NO data</p></div>'
        pdf = publisher.write_pdf(publisher.parse_reports(html)[0])
        reports = []
        savepoint = transaction.savepoint(optimistic=True)
        try:
            setup_xlsx_format()
            for samples, workbook in workbooks:
                primary = samples[0]
                report = api.create(
                    primary, "ResultsReport", sample=api.get_uid(primary),
                    contained_samples=[api.get_uid(s) for s in samples],
                    pdf=NamedBlobFile(data=pdf, filename=u"MiningResultsPreview.pdf",
                                      contentType="application/pdf"),
                    metadata={"template": api.safe_unicode(REPORT_TEMPLATE),
                              "format": u"xlsx",
                              "timestamp": api.safe_unicode(DateTime().ISO8601())})
                report.xlsx = NamedBlobFile(data=workbook,
                                           filename=xlsx_filename(report),
                                           contentType=MIME_TYPE)
                refresh_xlsx(report)
                reports.append(report)
        except Exception:
            savepoint.rollback()
            raise
        return self.get_exit_url_for(reports, action=data.get("action", "save"))

    def selected_groups(self, data):
        membership = api.get_tool("portal_membership")
        groups = OrderedDict()
        seen = set()
        for uid in data.get("items", []):
            sample = api.get_object_by_uid(uid, default=None) if api.is_uid(uid) else None
            if sample is None or not IAnalysisRequest.providedBy(sample):
                raise ValueError("Select valid samples for Mining Results XLSX")
            if not membership.checkPermission(ManageAnalysisRequests, sample):
                raise Unauthorized
            if uid not in seen:
                groups.setdefault(sample.getClientUID(), []).append(sample)
                seen.add(uid)
        if not groups:
            raise ValueError("Select samples for Mining Results XLSX")
        return groups


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
        "E": sample.getSamplingDeviationTitle(), "F": sample.getPriorityText(),
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


class ReportDownloadView(DownloadView):
    def __call__(self):
        blob = self.context.getPdf()
        if blob and blob.contentType == MIME_TYPE:
            return self.download(blob.data, blob.filename, MIME_TYPE)
        return super(ReportDownloadView, self).__call__()


class XLSXDownloadView(DownloadView):
    def download(self, data, filename, content_type=MIME_TYPE):
        download_xlsx(self.request, data, filename)

    def __call__(self):
        blob = get_xlsx(self.context)
        if blob is None:
            from zExceptions import NotFound
            raise NotFound("No XLSX attachment on this report")
        return self.download(blob.data, blob.filename, MIME_TYPE)


class ReportEmailView(BaseEmailView):
    template = ViewPageTemplateFile("templates/email.pt")

    @property
    def report_attachment_data(self):
        files = self.generated_attachments
        rows = []
        for blob in files:
            for report in self.reports:
                if get_xlsx(report) is blob:
                    url = report.absolute_url() + "/download_xlsx"
                    break
                if report.getPdf() is blob:
                    url = report.absolute_url() + "/download_pdf"
                    break
                if getattr(report, "csv", None) is blob:
                    url = report.absolute_url() + "/download/csv"
                    break
            rows.append({"filename": blob.filename, "url": url,
                         "filesize": "{:.2f} KB".format(len(blob.data) / 1024.0)})
        return rows

    @property
    def generated_attachments(self):
        files = []
        seen_xlsx = set()
        csv_found = False
        for report in self.reports:
            xlsx = get_xlsx(report)
            if xlsx:
                key = (xlsx.filename, xlsx.data)
                if key not in seen_xlsx:
                    files.append(xlsx)
                    seen_xlsx.add(key)
                continue
            pdf = self.get_pdf(report)
            if pdf is not None:
                files.append(pdf)
            # Preserve the COA rule for normal reports: at most one CSV,
            # excluding templates marked as Single.
            csv = getattr(report, "csv", None)
            if (pdf is not None and csv and not csv_found and
                    "Single" not in report.getMetadata().get("template", "") and
                    getattr(self, "email_csv_report_enabled", False)):
                files.append(csv)
                csv_found = True
        return files

    @property
    def email_attachments(self):
        files = self.generated_attachments + [a.getAttachmentFile()
                                              for a in self.attachments]
        return [mailapi.to_email_attachment(blob.data, blob.filename,
                                            mime_type=blob.contentType)
                for blob in files]

    @property
    def attachment_count(self):
        return len(self.generated_attachments) + len(self.attachments)

    @property
    def total_size(self):
        files = self.generated_attachments + [a.getAttachmentFile()
                                              for a in self.attachments]
        return sum(len(blob.data) for blob in files) / 1024.0

    def publish_samples(self):
        super(ReportEmailView, self).publish_samples()
        for report in self.reports:
            refresh_xlsx(report)

    def get_report_filename(self, report):
        blob = get_xlsx(report)
        if blob:
            return blob.filename
        return super(ReportEmailView, self).get_report_filename(report)


def xlsx_disposition(filename):
    return "attachment; filename*=UTF-8''{}".format(
        quote(api.safe_unicode(filename).encode("utf-8"), safe=""))


def download_xlsx(request, data, filename):
    response = request.response
    response.setHeader("Content-Disposition", xlsx_disposition(filename))
    response.setHeader("Content-Type", MIME_TYPE)
    response.setHeader("Content-Length", len(data))
    response.setHeader("Cache-Control", "no-store")
    response.setHeader("Pragma", "no-cache")
    response.write(data)


class DownloadReportsAdapter(WorkflowActionDownloadReportsAdapter):
    def download(self, data, filename, type="application/zip"):
        if type == MIME_TYPE:
            return download_xlsx(self.request, data, filename)
        return super(DownloadReportsAdapter, self).download(data, filename, type=type)

    def __call__(self, action, uids):
        reports = [api.get_object_by_uid(uid) for uid in uids]
        files = []
        for report in reports:
            if not api.get_tool("portal_membership").checkPermission("View", report):
                raise Unauthorized
            blob = get_xlsx(report) or self.get_pdf(report)
            if blob is None:
                continue
            extension = "xlsx" if blob.contentType == MIME_TYPE else "pdf"
            filename = u"{}-{}.{}".format(
                api.get_id(report.getSample()), api.get_id(report), extension)
            if blob.contentType == MIME_TYPE:
                filename = blob.filename
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

    def __call__(self, action, uids):
        response = super(PublishReportsAdapter, self).__call__(action, uids)
        for uid in uids:
            refresh_xlsx(api.get_object_by_uid(uid))
        return response


@implementer(IListingViewAdapter)
class ResultsListingAdapter(object):
    # Apply after bika.coa's default-priority report listing adapter.
    priority_order = 2000

    def __init__(self, listing, context):
        self.listing = listing
        self.context = context

    def before_render(self):
        if is_installed():
            self.listing.columns["XLSX"] = {"title": _(u"Download XLSX")}
            for state in self.listing.review_states:
                if "XLSX" not in state["columns"]:
                    state["columns"].append("XLSX")

    def folder_item(self, obj, item, index):
        if not is_installed():
            return item
        report = api.get_object(obj)
        xlsx = get_xlsx(report)
        if xlsx:
            item.setdefault("replace", {})["COA"] = get_link(
                report.getSample().absolute_url(),
                value=xlsx.filename.rsplit(u".", 1)[0])
            item.setdefault("replace", {})["XLSX"] = get_link(
                report.absolute_url() + "/download_xlsx", value="XLSX")
        return item
