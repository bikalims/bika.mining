# -*- coding: utf-8 -*-
import unittest

from bika.lims import api
from bika.mining.browser.worksheet import MatrixReferenceColumns


class TestWorksheetMatrixReference(unittest.TestCase):

    def test_sample_lookup_and_sorting(self):
        class Field(object):
            def get(self, sample):
                return sample.matrix

        class Schema(dict):
            def getField(self, name):
                return self.get(name)

        class Sample(object):
            def __init__(self, matrix):
                self.matrix = matrix

            def Schema(self):
                return Schema(MatrixReference=Field())

        class Analysis(object):
            def __init__(self, sample):
                self.sample = sample

            def getRequest(self):
                return self.sample

        class View(MatrixReferenceColumns):
            def __init__(self):
                self.order = 'ascending'

            def get_sort_order(self):
                return self.order

        analyses = [Analysis(Sample(value)) for value in
                    (u'Zulu', u'alpha', None)]
        originals = api.get_object, api.get_title
        api.get_object = lambda obj: obj
        api.get_title = lambda obj: obj
        try:
            view = View()
            self.assertEqual([view.matrix_reference_title(a) for a in analyses],
                             [u'Zulu', u'alpha', u''])
            self.assertEqual(view.sort_brains(analyses, 'MatrixReference'),
                             [analyses[2], analyses[1], analyses[0]])
            view.order = 'descending'
            self.assertEqual(view.sort_brains(analyses, 'MatrixReference'),
                             [analyses[0], analyses[1], analyses[2]])
        finally:
            api.get_object, api.get_title = originals
