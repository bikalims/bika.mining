# -*- coding: utf-8 -*-
import unittest
import zipfile
from datetime import datetime
from io import BytesIO
from copy import copy
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
            {"metadata": {"A": "Sample-1", "N": 0},
             "results": {"Moisture (%)": "0", "NH4 (ug/gU)": "<0.1"}},
            {"metadata": {"A": "Sample-2"},
             "results": {"U3O8 solids (ppm)": "12.30"}},
        ])
        sheet = workbook["Reporting"]
        self.assertEqual(sheet["Z4"].value, "0")
        self.assertEqual(sheet["DV4"].value, "<0.1")
        self.assertEqual(sheet["Q5"].value, "12.30")
        self.assertIsNone(sheet["Q4"].value)
        self.assertIsNone(sheet["Z5"].value)
        self.assertIsNone(sheet["B4"].value)
        self.assertEqual(sheet["N4"].value, 0)
        self.assertEqual(sheet.max_row, 5)
        self.assertEqual(sheet.max_column, 126)
        self.assertEqual(sheet.auto_filter.ref, "B3:DV5")

    def test_template_formatting_and_headers_preserved(self):
        original = load_workbook(TEMPLATE)["Reporting"]
        sheet = self.export([{"metadata": {}, "results": {}}])["Reporting"]
        updated_headings = {
            'A2': 'LIMS sample ID',
            'C2': 'Plant sample ID',
            'DH3': 'Cl final (ppm)',
        }
        for row in original.iter_rows(min_row=2, max_row=3):
            for cell in row:
                expected = updated_headings.get(cell.coordinate, cell.value)
                self.assertEqual(sheet[cell.coordinate].value, expected)
                self.assertEqual(sheet[cell.coordinate]._style, cell._style)
        self.assertEqual(list(sheet.merged_cells.ranges),
                         list(original.merged_cells.ranges))
        for row in sheet.iter_rows(min_row=4, max_row=4):
            for cell in row:
                self.assertEqual(cell.font.name, 'Arial')
                self.assertEqual(cell.font.color.rgb, 'FF000000')
                self.assertFalse(cell.font.italic)
                self.assertFalse(cell.font.bold)
                source_cell = original[cell.coordinate]
                self.assertEqual(copy(cell.alignment), copy(source_cell.alignment))
                self.assertEqual(copy(cell.fill), copy(source_cell.fill))
                self.assertEqual(copy(cell.border), copy(source_cell.border))
                if cell.column_letter == 'J':
                    self.assertEqual(cell.number_format, 'm/d/yy h:mm')
                else:
                    self.assertEqual(cell.number_format, source_cell.number_format)
        self.assertEqual(sheet.column_dimensions["P"].width,
                         original.column_dimensions["P"].width)
        for definition in sheet.column_dimensions.values():
            self.assertFalse(definition.hidden)
            self.assertFalse(definition.collapsed)

    def test_transfer_datetime_and_separate_receipt_columns(self):
        transferred = datetime(2026, 11, 25, 8, 15)
        sheet = self.export([
            {"metadata": {"J": transferred, "K": "2026-11-25", "L": "09:30"},
             "results": {}},
            {"metadata": {}, "results": {}},
        ])["Reporting"]
        self.assertEqual(sheet["J4"].value, transferred)
        self.assertEqual(sheet["K4"].value, "2026-11-25")
        self.assertEqual(sheet["L4"].value, "09:30")
        self.assertIsNone(sheet["J5"].value)

    def test_chlorine_and_final_chlorine_use_separate_columns(self):
        sheet = self.export([
            {"metadata": {}, "results": {"Cl (ppm)": "12",
                                         "Cl final (ppm)": "15"}},
            {"metadata": {}, "results": {}},
        ])["Reporting"]
        self.assertEqual(sheet["CC3"].value, "Cl (ppm)")
        self.assertEqual(sheet["DH3"].value, "Cl final (ppm)")
        self.assertEqual(sheet["CC4"].value, "12")
        self.assertEqual(sheet["DH4"].value, "15")
        self.assertIsNone(sheet["CC5"].value)
        self.assertIsNone(sheet["DH5"].value)

    def test_more_samples_than_example_rows(self):
        rows = [{"metadata": {"A": "Sample-{}".format(i)},
                 "results": {"NH4 (ug/gU)": str(i)}} for i in range(12)]
        sheet = self.export(rows)["Reporting"]
        self.assertEqual(sheet["A15"].value, "Sample-11")
        self.assertEqual(sheet["DV15"].value, "11")

    def test_mockup_services_and_layout(self):
        destinations = {
            'AF': 'Granulometry (% passing 6 mm)', 'AG': 'Slurry SG (t/m3)',
            'AI': 'Solids (% w/w)', 'AJ': 'Resin concentration (% v/v)',
            'AK': 'Resin carry-over (g/L)', 'AL': 'Wet mass of cut (kg)',
            'AM': 'Dry mass of cut (kg)', 'AN': 'Mass recovered (kg)',
            'AO': 'Mass produced (t)', 'AP': 'Volume (m3)',
            'AU': 'pH', 'AV': 'ORP (mV)', 'AY': 'Dissolved oxygen (ppb)',
            'CO': 'Cycles of concentration (ratio)',
            'CP': 'Corrosion inhibitor residual (ppm)',
            'CR': 'Resin working capacity (g U/L)',
            'CS': 'Bead size distribution (%)', 'CT': 'Whole-bead count (%)',
            'CW': 'U3O8 solids titration (%)', 'CX': 'Moisture final (%)',
            'DF': 'S (%)', 'DJ': 'CO3 (ug/gU)', 'DM': 'V (%)',
        }
        results = dict((name, str(index)) for index, name in
                       enumerate(sorted(destinations.values())))
        sheet = self.export([{'metadata': {}, 'results': results}])['Reporting']
        for col, name in destinations.items():
            self.assertEqual(sheet[col + '3'].value, name)
            self.assertEqual(sheet[col + '4'].value, results[name])
        self.assertEqual(sheet['AU2'].value, 'Field / water')
        self.assertEqual(sheet['CW2'].value, 'Final product impurities')
        for row in sheet.iter_rows(min_row=3, max_row=3, min_col=17, max_col=126):
            for cell in row:
                self.assertEqual(cell.alignment.textRotation, 90)

    def test_report_header_and_empty_export(self):
        header = {'A': 'Plant', 'C': 'COA26-0001',
                  'E': '2026-10-18 09:15', 'G': 'Publisher',
                  'I': 'COA26-0001 Plant.xlsx'}
        sheet = load_workbook(BytesIO(render_results(
            [], report_header=header)))['Reporting']
        self.assertEqual([cell.value for cell in sheet[1][:15]], [
            'Client', 'Plant', None, 'COA ID', 'COA26-0001', None,
            'Date Published', '2026-10-18 09:15', None,
            'Published by', 'Publisher', None,
            'File name', 'COA26-0001 Plant.xlsx', None,
        ])
        for cell in sheet[1][:15:3]:
            self.assertTrue(cell.font.bold)
            self.assertEqual(cell.font.color.rgb, 'FFFFFFFF')
            self.assertEqual(copy(cell.fill), copy(sheet['A2'].fill))
        for cell, spill in zip(sheet[1][1:15:3], sheet[1][2:15:3]):
            self.assertFalse(cell.font.bold)
            self.assertEqual(cell.font.color.rgb, 'FF000000')
            self.assertEqual(cell.fill.fgColor.rgb, 'FFFFFFFF')
            self.assertEqual(cell.alignment.horizontal, 'left')
            self.assertFalse(cell.alignment.wrap_text)
            self.assertFalse(cell.alignment.shrink_to_fit)
            self.assertEqual(copy(cell.fill), copy(spill.fill))
        self.assertEqual(sheet.max_row, 3)
        self.assertEqual(sheet.auto_filter.ref, 'B3:DV3')

    def test_unknown_service_title_is_rejected(self):
        with self.assertRaises(ValueError):
            render_results([{"metadata": {}, "results": {"Unknown AS": "1"}}])

    def test_results_are_literal_text(self):
        sheet = self.export([{"metadata": {},
                              "results": {"Moisture (%)": "=1+1"}}])["Reporting"]
        self.assertEqual(sheet["Z4"].data_type, "s")

    def test_other_workbook_parts_are_unchanged(self):
        data = render_results([{"metadata": {}, "results": {}}])
        with zipfile.ZipFile(TEMPLATE) as source:
            with zipfile.ZipFile(BytesIO(data)) as output:
                for name in source.namelist():
                    if name not in ("xl/worksheets/sheet1.xml", "xl/workbook.xml",
                                    "xl/styles.xml"):
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

    def test_sampling_methods_reuse_existing_records(self):
        from bika.lims import api
        from bika.mining.setuphandlers import setup_sampling_methods
        from plone.app.testing import setRoles, TEST_USER_ID
        setRoles(self.layer['portal'], TEST_USER_ID, ['Manager'])
        folder = api.get_senaite_setup().samplingdeviations
        original = dict((obj.Title(), api.get_uid(obj))
                        for obj in folder.objectValues())
        self.assertEqual(set(original), {'Grab', 'Composite', 'Profile/Inventory'})
        legacy = api.create(folder, 'SamplingDeviation', title=u'Existing method')
        setup_sampling_methods()
        self.assertEqual(folder.Title(), 'Sampling Methods')
        self.assertEqual(api.get_title(legacy), 'Existing method')
        for obj in folder.objectValues():
            if obj.Title() in original:
                self.assertEqual(api.get_uid(obj), original[obj.Title()])
        self.assertEqual(len(folder.objectValues()), 4)

    def test_drum_batch_exports_as_literal_text(self):
        from bika.lims import api
        from bika.mining.browser.resultsxlsx import sample_row
        from plone.app.testing import setRoles, TEST_USER_ID

        portal = self.layer['portal']
        request = self.layer['request']
        setRoles(portal, TEST_USER_ID, ['Manager'])
        alsoProvides(request, IBikaMiningLayer)
        client = api.create(portal.clients, 'Client', title=u'Drum test',
                            ClientID='DRUM')
        setup = api.get_senaite_setup()
        sample_type = api.create(setup.sampletypes, 'SampleType',
                                 title=u'Ore', Prefix='ORE')
        sample = api.create(client, 'AnalysisRequest', SampleType=sample_type)
        sample.Schema().getField('DrumBatch').set(sample, u'A 543')

        sheet = load_workbook(BytesIO(render_results([sample_row(sample)])))['Reporting']
        self.assertEqual(sheet['H4'].value, u'A 543')

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
        sample_type = api.create(setup.sampletypes, 'SampleType',
                                 title=u'Ore', Prefix='ORE')
        sample = api.create(client, 'AnalysisRequest',
                            SampleType=sample_type,
                            DateReceived=DateTime() - 1.0 / 24,
                            TargetTAT=8.0)
        sample.Schema().getField('TargetTAT').set(sample, 8.0)
        methods = api.get_senaite_setup().samplingdeviations
        method = next(obj for obj in methods.objectValues()
                      if obj.Title() == 'Composite')
        sample.Schema().getField('SamplingDeviation').set(sample, method)
        self.assertEqual(sample.Schema().getField('SamplingDeviation').widget.label,
                         'Sampling Method')
        workflow = api.get_tool('portal_workflow')
        chain = workflow.getChainFor(sample)
        workflow.setStatusOf(chain[0], sample, {'review_state': 'verified'})
        workflow[chain[0]].updateRoleMappingsFor(sample)
        sample.reindexObject()
        portal.uid_catalog.catalog_object(sample, sample._getURL())
        second_sample = api.create(client, 'AnalysisRequest',
                                   SampleType=sample_type)
        workflow.setStatusOf(chain[0], second_sample, {'review_state': 'verified'})
        workflow[chain[0]].updateRoleMappingsFor(second_sample)
        second_sample.reindexObject()
        portal.uid_catalog.catalog_object(second_sample, second_sample._getURL())
        request.method = 'POST'
        view = MiningAjaxPublishView(sample, request)
        payload = {'template': REPORT_TEMPLATE,
                   'items': [api.get_uid(sample), api.get_uid(second_sample)],
                   'action': 'email', 'format': 'A4', 'orientation': 'portrait'}
        view.get_json = lambda: payload
        html = view.ajax_render_reports()
        self.assertIn('An XLSX report of the results', html)
        self.assertIn('name="coa_num"', html)
        self.assertIn('COA', html)
        self.assertNotIn('NO data', html)
        self.assertIn(api.get_uid(sample), html)
        self.assertIn(api.get_uid(second_sample), html)
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
        saved_sheet = load_workbook(BytesIO(reports[0].xlsx.data))['Reporting']
        self.assertEqual(saved_sheet['B1'].value, 'Lotus test')
        self.assertEqual(saved_sheet['E1'].value, api.get_id(reports[0]))
        self.assertEqual(saved_sheet['N1'].value, filename)
        self.assertEqual(saved_sheet['H1'].value,
                         reports[0].created().strftime('%Y-%m-%d %H:%M'))
        self.assertEqual(saved_sheet['K1'].value,
                         api.get_user_fullname(reports[0].Creator()) or
                         reports[0].Creator())
        self.assertEqual(api.normalize_filename(filename[:-5]),
                         api.get_id(reports[0]))
        self.assertEqual(reports[0].getContainedSamples(), [sample, second_sample])
        self.assertEqual(saved_sheet['A5'].value, second_sample.getId())
        workflow.doActionFor(sample, 'publish')
        refresh_xlsx(reports[0])
        self.assertEqual(reports[0].xlsx.filename, filename)
        data = reports[0].xlsx.data
        sheet = load_workbook(BytesIO(data))['Reporting']
        self.assertEqual(sheet['A4'].value, sample.getId())
        self.assertEqual(sheet['A5'].value, second_sample.getId())
        self.assertEqual(sheet['E4'].value, 'Composite')
        self.assertEqual(sheet['H1'].value,
                         sample.getDatePublished().strftime('%Y-%m-%d %H:%M'))
        self.assertTrue(sheet['K1'].value)
        self.assertEqual(sheet['E1'].value, api.get_id(reports[0]))
        self.assertEqual(sheet['N1'].value, filename)
        self.assertEqual(sheet['N4'].value, 8.0)
        self.assertAlmostEqual(sheet['O4'].value, 1.0, places=2)
        self.assertEqual(sheet['P4'].value, 'On Time')
        self.assertIsNone(sheet['Q4'].value)
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
    def test_header_uses_saved_report_id(self):
        from DateTime import DateTime
        from bika.lims import api
        from bika.mining.browser.resultsxlsx import report_header

        class Report(object):
            xlsx = type('Blob', (object,), {'filename': u'Attachment name.xlsx'})()

            def getId(self):
                return 'saved-results-report-id'

            def created(self):
                return DateTime('2026/11/15 21:49:00')

            def Creator(self):
                return 'saved-user'

        class Sample(object):
            def getClient(self):
                return None

        fullname = api.get_user_fullname
        api.get_user_fullname = lambda actor: {
            'saved-user': 'Saved User', 'publisher': 'Publishing User'}.get(actor)
        try:
            sample = Sample()
            header = report_header(Report(), [sample])
            self.assertEqual(header['E'], '2026-11-15 21:49')
            self.assertEqual(header['G'], 'Saved User')
            sample.workflow_history = {'sample_workflow': [{
                'action': 'publish', 'review_state': 'published',
                'time': DateTime('2026/11/16 09:00:00'), 'actor': 'publisher'}]}
            published_header = report_header(Report(), [sample])
            self.assertEqual(published_header['E'], '2026-11-16 09:00')
            self.assertEqual(published_header['G'], 'Publishing User')
        finally:
            api.get_user_fullname = fullname
        self.assertEqual(header['C'], 'saved-results-report-id')
        self.assertEqual(header['I'], 'Attachment name.xlsx')

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
