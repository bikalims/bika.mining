# -*- coding: utf-8 -*-
import unittest
import zipfile
from io import BytesIO
from openpyxl import load_workbook
from bika.mining.resultsxlsx import TEMPLATE, render_results
from senaite.core.tests.layers import BASE_LAYER_FIXTURE
from plone.app.testing import PloneSandboxLayer, IntegrationTesting, applyProfile
import bika.mining
from bika.mining.interfaces import IBikaMiningLayer
from zope.interface import alsoProvides
from zope.component import getMultiAdapter
from bika.lims.interfaces import IClient
from zope.interface import implementer


class TestResultsXLSX(unittest.TestCase):
    def export(self, rows):
        return load_workbook(BytesIO(render_results(rows)))

    def test_fixed_columns_blank_cells_and_zero(self):
        workbook = self.export([
            {"metadata": {"A": "Sample-1", "M": 0},
             "results": {"Moisture (%)": "0", "NH4 (ug/gU)": "<0.1"}},
            {"metadata": {"A": "Sample-2"},
             "results": {"U3O8 solids (ppm)": "12.30"}},
        ])
        sheet = workbook["Reporting"]
        self.assertEqual(sheet["Y4"].value, "0")
        self.assertEqual(sheet["CX4"].value, "<0.1")
        self.assertEqual(sheet["P5"].value, "12.30")
        self.assertIsNone(sheet["P4"].value)
        self.assertIsNone(sheet["Y5"].value)
        self.assertIsNone(sheet["B4"].value)
        self.assertEqual(sheet["M4"].value, 0)
        self.assertEqual(sheet.max_row, 5)
        self.assertEqual(sheet.max_column, 102)
        self.assertEqual(sheet.auto_filter.ref, "B3:CX5")

    def test_template_formatting_and_headers_preserved(self):
        original = load_workbook(TEMPLATE)["Reporting"]
        sheet = self.export([{"metadata": {}, "results": {}}])["Reporting"]
        for row in original.iter_rows(min_row=1, max_row=3):
            for cell in row:
                self.assertEqual(sheet[cell.coordinate].value, cell.value)
                self.assertEqual(sheet[cell.coordinate]._style, cell._style)
        self.assertEqual(list(sheet.merged_cells.ranges),
                         list(original.merged_cells.ranges))
        self.assertEqual(sheet["CX4"]._style, original["CX4"]._style)
        self.assertEqual(sheet.column_dimensions["P"].width,
                         original.column_dimensions["P"].width)

    def test_more_samples_than_example_rows(self):
        rows = [{"metadata": {"A": "Sample-{}".format(i)},
                 "results": {"NH4 (ug/gU)": str(i)}} for i in range(12)]
        sheet = self.export(rows)["Reporting"]
        self.assertEqual(sheet["A15"].value, "Sample-11")
        self.assertEqual(sheet["CX15"].value, "11")

    def test_unknown_service_title_is_rejected(self):
        with self.assertRaises(ValueError):
            render_results([{"metadata": {}, "results": {"Unknown AS": "1"}}])

    def test_results_are_literal_text(self):
        sheet = self.export([{"metadata": {},
                              "results": {"Moisture (%)": "=1+1"}}])["Reporting"]
        self.assertEqual(sheet["Y4"].data_type, "s")

    def test_other_workbook_parts_are_unchanged(self):
        data = render_results([{"metadata": {}, "results": {}}])
        with zipfile.ZipFile(TEMPLATE) as source:
            with zipfile.ZipFile(BytesIO(data)) as output:
                for name in source.namelist():
                    if name not in ("xl/worksheets/sheet1.xml", "xl/workbook.xml"):
                        self.assertEqual(source.read(name), output.read(name))


class ResultsPublicationLayer(PloneSandboxLayer):
    defaultBases = (BASE_LAYER_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        import plone.restapi
        import senaite.impress
        self.loadZCML(package=plone.restapi)
        self.loadZCML(package=senaite.impress)
        self.loadZCML(package=bika.mining)

    def setUpPloneSite(self, portal):
        # The SENAITE base fixture retains its earlier global registry.
        # Rebase the test site so this layer's add-on registrations are visible.
        from zope.component import getGlobalSiteManager
        portal.getSiteManager().__bases__ = (getGlobalSiteManager(),)
        from zope.component.hooks import setSite
        setSite(portal)
        applyProfile(portal, 'bika.mining:default')


RESULTS_TESTING = IntegrationTesting(bases=(ResultsPublicationLayer(),),
                                    name='MiningResults:Integration')


class TestResultsPublicationRegistration(unittest.TestCase):
    layer = RESULTS_TESTING

    def setUp(self):
        from zope.component.hooks import setSite
        from zope.component import getGlobalSiteManager
        self.layer['portal'].getSiteManager().__bases__ = (getGlobalSiteManager(),)
        setSite(self.layer['portal'])
        applyProfile(self.layer['portal'], 'bika.mining:default')

    def test_mining_publish_and_download_routes(self):
        from senaite.impress.publishview import PublishView
        from bika.mining.browser.resultsxlsx import ReportEmailView
        from bika.mining.browser.resultsxlsx import MiningAjaxPublishView

        @implementer(IClient)
        class Client(object):
            pass
        request = self.layer['request']
        from senaite.impress.interfaces import ISenaiteImpressLayer
        alsoProvides(request, ISenaiteImpressLayer)
        alsoProvides(request, IBikaMiningLayer)
        from zope.traversing.interfaces import BeforeTraverseEvent
        from zope.event import notify
        notify(BeforeTraverseEvent(self.layer['portal'], request))
        self.assertIsInstance(getMultiAdapter((Client(), request), name='publish'),
                              PublishView)
        self.assertIsInstance(getMultiAdapter((Client(), request), name='email'),
                              ReportEmailView)
        self.assertIsInstance(getMultiAdapter((Client(), request), name='ajax_publish'),
                              MiningAjaxPublishView)

    def test_publication_stores_xlsx_and_updates_sample_tat(self):
        from bika.lims import api
        from bika.mining.browser.resultsxlsx import MiningAjaxPublishView
        from bika.mining.browser.resultsxlsx import REPORT_TEMPLATE, refresh_xlsx
        from bika.mining.resultsxlsx import MIME_TYPE
        from plone.app.testing import setRoles, TEST_USER_ID
        from DateTime import DateTime
        portal = self.layer['portal']
        request = self.layer['request']
        setRoles(portal, TEST_USER_ID, ['Manager'])
        from bika.mining.idserver import REPORT_TYPE, DEFAULT_FORMAT
        setup = api.get_senaite_setup()
        rows = list(setup.getIDFormatting())
        for row in rows:
            if row['portal_type'] == REPORT_TYPE:
                row['form'] = DEFAULT_FORMAT
                row['sequence_type'] = 'generated'
                row['split_length'] = 1
        setup.setIDFormatting(rows)
        alsoProvides(request, IBikaMiningLayer)
        from plone.browserlayer.utils import registered_layers
        self.assertIn(IBikaMiningLayer, registered_layers())
        from archetypes.schemaextender.extender import disableCache
        disableCache(request)
        client = api.create(portal.clients, 'Client', title=u'Lotus test',
                            ClientID='LOTUS')
        sample = api.create(client, 'AnalysisRequest',
                            DateReceived=DateTime() - 1.0 / 24,
                            TargetTAT=8.0)
        sample.Schema().getField('TargetTAT').set(sample, 8.0)
        workflow = api.get_tool('portal_workflow')
        chain = workflow.getChainFor(sample)
        workflow.setStatusOf(chain[0], sample, {'review_state': 'verified'})
        workflow[chain[0]].updateRoleMappingsFor(sample)
        sample.reindexObject()
        portal.uid_catalog.catalog_object(sample, sample._getURL())
        request.method = 'POST'
        view = MiningAjaxPublishView(sample, request)
        payload = {'template': REPORT_TEMPLATE, 'items': [api.get_uid(sample)],
                   'action': 'email', 'format': 'A4', 'orientation': 'portrait'}
        view.get_json = lambda: payload
        html = view.ajax_render_reports()
        self.assertIn('NO data', html)
        self.assertIn(api.get_uid(sample), html)
        payload['html'] = html
        preview = view.ajax_load_preview()
        self.assertIn('data:image/png', preview)
        url = view.ajax_save_reports()
        self.assertIn('/email?uids=', url)
        self.assertEqual(api.get_workflow_status_of(sample), 'verified')
        reports = [obj for obj in sample.objectValues()
                   if obj.portal_type == 'ResultsReport']
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].getPdf().contentType, 'application/pdf')
        self.assertTrue(reports[0].getPdf().data.startswith('%PDF'))
        self.assertEqual(reports[0].xlsx.contentType, MIME_TYPE)
        self.assertRegexpMatches(
            reports[0].xlsx.filename,
            r'^COA\d{2}-\d{4} LOTUS \d{6} \d{2}:\d{2}\.xlsx$')
        filename = reports[0].xlsx.filename
        self.assertEqual(api.normalize_filename(filename[:-5]),
                         api.get_id(reports[0]))
        self.assertEqual(reports[0].getContainedSamples(), [sample])
        workflow.doActionFor(sample, 'publish')
        refresh_xlsx(reports[0])
        self.assertEqual(reports[0].xlsx.filename, filename)
        data = reports[0].xlsx.data
        sheet = load_workbook(BytesIO(data))['Reporting']
        self.assertEqual(sheet['A4'].value, sample.getId())
        self.assertEqual(sheet['M4'].value, 8.0)
        self.assertAlmostEqual(sheet['N4'].value, 1.0, places=2)
        self.assertEqual(sheet['O4'].value, 'On Time')
        self.assertIsNone(sheet['P4'].value)
        from bika.mining.browser.resultsxlsx import XLSXDownloadView
        downloaded = []
        request.response.write = downloaded.append
        XLSXDownloadView(reports[0], request)()
        self.assertEqual(downloaded, [data])
        self.assertEqual(request.response.getHeader('Content-Type'), MIME_TYPE)
        self.assertIn('.xlsx', request.response.getHeader('Content-Disposition'))

        from bika.mining.browser.resultsxlsx import ReportEmailView
        class Email(ReportEmailView):
            attachments = []
        Email.reports = reports
        email = Email(sample, request)
        self.assertEqual(email.generated_attachments, [reports[0].xlsx])
        attachments = email.email_attachments
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].get_filename(), filename)
        self.assertEqual(attachments[0].get_content_type(), MIME_TYPE)
        self.assertEqual(attachments[0].get_payload(decode=True), data)
        self.assertEqual(email.attachment_count, 1)
        self.assertAlmostEqual(email.total_size, len(data) / 1024.0)
        self.assertTrue(email.report_attachment_data[0]['url'].endswith('/download_xlsx'))

        from bika.mining.idserver import setup_xlsx_format, xlsx_filename
        setup = api.get_senaite_setup()
        rows = list(setup.getIDFormatting())
        for row in rows:
            if row['portal_type'] == REPORT_TYPE:
                row['form'] = u'TEST{year}-{seq:04d} {clientId} {hh:mm}'
        setup.setIDFormatting(rows)
        setup_xlsx_format()
        self.assertFalse(any(row['portal_type'] == 'MiningResultsXLSX'
                             for row in setup.getIDFormatting()))
        extra = api.create(sample, 'ResultsReport', sample=api.get_uid(sample))
        first = xlsx_filename(extra)
        self.assertEqual(xlsx_filename(extra), first)
        extra = api.create(sample, 'ResultsReport', sample=api.get_uid(sample))
        second = xlsx_filename(extra)
        self.assertRegexpMatches(first, r'^TEST\d{2}-0001 LOTUS \d{2}:\d{2}\.xlsx$')
        self.assertRegexpMatches(second, r'^TEST\d{2}-0002 LOTUS \d{2}:\d{2}\.xlsx$')

        from bika.mining.browser.resultsxlsx import DownloadReportsAdapter
        adapter = DownloadReportsAdapter(sample, request)
        adapter.download = lambda data, name, **kw: name
        self.assertEqual(adapter('download', [api.get_uid(reports[0])]), filename)


class TestMiningReportSelection(unittest.TestCase):
    def test_time_variable_uses_hours_and_minutes(self):
        from DateTime import DateTime
        from bika.mining.idserver import ReportTime
        self.assertEqual(u'{hh:mm}'.format(
            hh=ReportTime(DateTime('2026/10/08 09:15:00'))), u'09:15')

    def test_other_templates_keep_their_existing_handlers(self):
        from bika.mining.browser.resultsxlsx import MiningAjaxPublishView, REPORT_TEMPLATE
        calls = []
        class Legacy(object):
            def ajax_templates(self):
                return ['bika.coa:OtherMulti.pt']
            def ajax_render_reports(self, *args):
                calls.append('render')
                return 'normal report'
            def ajax_load_preview(self):
                calls.append('preview')
                return 'normal preview'
            def ajax_save_reports(self):
                calls.append('save')
                return 'normal save'
        view = MiningAjaxPublishView(None, None)
        view.legacy_view = lambda: Legacy()
        view.get_json = lambda: {'template': 'bika.coa:OtherMulti.pt'}
        self.assertEqual(view.ajax_templates(), ['bika.coa:OtherMulti.pt', REPORT_TEMPLATE])
        self.assertEqual(view.ajax_render_reports(), 'normal report')
        self.assertEqual(view.ajax_load_preview(), 'normal preview')
        self.assertEqual(view.ajax_save_reports(), 'normal save')
        self.assertEqual(calls, ['render', 'preview', 'save'])

    def test_mining_emails_exclude_placeholder_but_preserve_normal_pdf_and_csv(self):
        from bika.mining.browser.resultsxlsx import ReportEmailView, MIME_TYPE
        from ZPublisher.HTTPRequest import HTTPRequest
        from ZPublisher.HTTPResponse import HTTPResponse
        class Report(object):
            def __init__(self, pdf, xlsx=None, csv=None):
                self.pdf, self.xlsx, self.csv = pdf, xlsx, csv
            def getPdf(self):
                return self.pdf
            def getMetadata(self):
                return {'template': 'bika.coa:OtherMulti.pt'}
        def blob(name, kind, data):
            return type('Blob', (object,), {
                'data': data, 'filename': unicode(name), 'contentType': kind})()
        xlsx = blob('MiningResults.xlsx', MIME_TYPE, 'xlsx content')
        placeholder = blob('MiningResultsPreview.pdf', 'application/pdf', 'NO data')
        pdf = blob('OtherReport.pdf', 'application/pdf', 'normal PDF')
        csv = blob('OtherReport.csv', 'text/csv', 'normal CSV')
        class Email(ReportEmailView):
            reports = [Report(placeholder, xlsx), Report(placeholder, xlsx),
                       Report(pdf, csv=csv)]
            attachments = []
            email_csv_report_enabled = True
        request = HTTPRequest(BytesIO(), {'SERVER_NAME': 'localhost',
                                         'SERVER_PORT': '80',
                                         'REQUEST_METHOD': 'GET'}, HTTPResponse())
        view = Email(None, request)
        self.assertEqual(view.generated_attachments, [xlsx, pdf, csv])
        attachments = view.email_attachments
        self.assertEqual([a.get_filename() for a in attachments],
                         ['MiningResults.xlsx', 'OtherReport.pdf', 'OtherReport.csv'])
        self.assertEqual([a.get_content_type() for a in attachments],
                         [MIME_TYPE, 'application/pdf', 'text/csv'])
