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
        from bika.mining.browser.resultsxlsx import ResultsXLSXView
        from bika.mining.browser.resultsxlsx import ReportEmailView

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
                              ResultsXLSXView)
        self.assertIsInstance(getMultiAdapter((Client(), request), name='email'),
                              ReportEmailView)

    def test_publication_stores_xlsx_and_updates_sample_tat(self):
        from bika.lims import api
        from bika.mining.browser.resultsxlsx import ResultsXLSXView
        from bika.mining.resultsxlsx import MIME_TYPE
        from plone.app.testing import setRoles, TEST_USER_ID
        from plone.protect.authenticator import createToken
        from DateTime import DateTime
        portal = self.layer['portal']
        request = self.layer['request']
        setRoles(portal, TEST_USER_ID, ['Manager'])
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
        request.form.update(action='publish', _authenticator=createToken())
        data = ResultsXLSXView(sample, request)()
        self.assertEqual(api.get_workflow_status_of(sample), 'published')
        reports = [obj for obj in sample.objectValues()
                   if obj.portal_type == 'ResultsReport']
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].getPdf().contentType, MIME_TYPE)
        self.assertEqual(reports[0].getPdf().data, data)
        self.assertEqual(reports[0].getContainedSamples(), [sample])
        sheet = load_workbook(BytesIO(data))['Reporting']
        self.assertEqual(sheet['A4'].value, sample.getId())
        self.assertEqual(sheet['M4'].value, 8.0)
        self.assertAlmostEqual(sheet['N4'].value, 1.0, places=2)
        self.assertEqual(sheet['O4'].value, 'On Time')
        self.assertIsNone(sheet['P4'].value)
        from bika.mining.browser.resultsxlsx import ReportDownloadView
        downloaded = []
        request.response.write = downloaded.append
        ReportDownloadView(reports[0], request)()
        self.assertEqual(downloaded, [data])
        self.assertEqual(request.response.getHeader('Content-Type'), MIME_TYPE)
        self.assertIn('.xlsx', request.response.getHeader('Content-Disposition'))
