# -*- coding: utf-8 -*-
"""Verify mining registrations against the configured Plone fixture."""
import unittest

from bika.mining.interfaces import IBikaMiningLayer
from bika.mining.testing import BIKA_MINING_INTEGRATION_TESTING
from senaite.sampleimporter.content.sampleimport import SampleImport, SampleData
from zope.component import queryMultiAdapter
from zope.interface import alsoProvides
from bika.lims.interfaces import IClient


class TestSampleImportIntegration(unittest.TestCase):
    layer = BIKA_MINING_INTEGRATION_TESTING

    def test_registered_modifier_extends_instance_schema_only(self):
        sampleimport = SampleImport('test-import').__of__(self.layer['portal'])
        field = sampleimport.Schema()['SampleData']
        self.assertIn('TargetTAT', field.columns)
        self.assertIn('SamplingDeviation', field.columns)
        self.assertNotIn('TargetTAT', SampleData.columns)

    def test_registered_validation_wrapper_rejects_negative_hours(self):
        request = self.layer['request']
        alsoProvides(request, IBikaMiningLayer)
        sampleimport = SampleImport('test-import').__of__(self.layer['portal'])
        with self.assertRaises(ValueError):
            sampleimport.munge_field_value({'TargetTAT': object()},
                                          1, 'TargetTAT', '-1')

    def test_template_view_registered_for_mining_request(self):
        request = self.layer['request']
        alsoProvides(request, IBikaMiningLayer)
        client = type('Client', (object,), {})()
        alsoProvides(client, IClient)
        view = queryMultiAdapter((client, request), name='sampleimport_template')
        self.assertIsNotNone(view)
