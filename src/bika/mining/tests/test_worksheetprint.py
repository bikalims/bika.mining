# -*- coding: utf-8 -*-
import unittest

from Acquisition import Implicit
from OFS.Folder import Folder
from Testing.makerequest import makerequest
from bika.mining.browser.worksheetprint import MiningPrintTemplates
from zope.component import provideAdapter
from zope.component.testing import setUp, tearDown
from zope.interface import Interface
from zope.traversing.adapters import DefaultTraversable
from zope.traversing.interfaces import ITraversable


class Matrix(object):
    def Title(self):
        return u'MATRIX-17'


class Sample(object):
    matrix = Matrix()
    has_field = True

    def __call__(self):
        raise AssertionError('Printing must not call the sample object')

    def Schema(self):
        return self

    def getField(self, name):
        return self if self.has_field else None

    def get(self, sample):
        return self.matrix


class PrintHarness(MiningPrintTemplates, Implicit):
    def __init__(self, sample, template):
        self.context = makerequest(Folder('portal'))
        self.request = self.context.REQUEST
        self.request.form['template'] = template
        self._TEMPLATES_LIST = [template]
        self._current_ws_index = 0
        self._worksheets = [self.worksheet_data(sample)]

    def worksheet_data(self, sample):
        person = dict(fullname='Analyst', email='analyst@example.test')
        ar = dict(id='SAMPLE-1', url='#sample', date_received='2026-11-15',
                  client=dict(name='Client', url='#client'),
                  sample=dict(obj=sample, id='SAMPLE-1', url='#sample',
                              sample_type=dict(title='Slurry', url='#type'),
                              sample_point=dict(title='Feed', url='#point'),
                              date_sampled='2026-11-14 13:35'))
        return dict(id='WS-1', url='#worksheet', laboratory=dict(url='#lab'),
                    portal={}, ars=[ar], analyses_titles=['Slurry SG'],
                    createdby=person, printedby=person, analyst=person,
                    date_created='2026-11-15', date_printed='2026-11-15')

    def getWorksheet(self):
        return self._worksheets[self._current_ws_index]

    def getNumColumns(self):
        return 3

    def splitList(self, items, size):
        return [items]

    def get_analyses_data_by_title(self, ar, title):
        return [dict(review_state='verified', formatted_result='1.00',
                     unit='t/m3')]


class TestWorksheetPrint(unittest.TestCase):
    def setUp(self):
        setUp()
        provideAdapter(DefaultTraversable, (Interface,), ITraversable)

    def tearDown(self):
        tearDown()

    def test_render_callable_sample_without_rendering_the_sample(self):
        for layout in ('sample_by_row', 'sample_by_column'):
            for prefix in ('', 'Worksheet Print Templates:'):
                view = PrintHarness(Sample(), prefix + layout + '.pt')
                html = view.renderWSTemplate()
                self.assertIn('MATRIX-17', html)
                self.assertIn('SAMPLE-1', html)
                self.assertIn('1.00', html)
                self.assertEqual(view._current_ws_index, 1)
                if layout == 'sample_by_row':
                    self.assertNotIn('Request ID', html)
                    self.assertNotIn('#client', html)
                    self.assertIn('Feed', html)
                    self.assertIn('2026-11-14 13:35', html)
                else:
                    self.assertIn('Matrix Reference', html)

    def test_missing_matrix_reference_prints_blank(self):
        for layout in ('sample_by_row', 'sample_by_column'):
            for has_field in (True, False):
                sample = Sample()
                sample.matrix = None
                sample.has_field = has_field
                html = PrintHarness(sample, layout + '.pt').renderWSTemplate()
                self.assertNotIn('MATRIX-17', html)
                self.assertIn('SAMPLE-1', html)
