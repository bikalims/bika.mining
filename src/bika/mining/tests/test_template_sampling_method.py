# -*- coding: utf-8 -*-
import unittest

from bika.lims import api
from bika.lims.interfaces import IAddSampleObjectInfo
from bika.mining.extenders.sampletemplate import IMiningSampleTemplate
from bika.mining.interfaces import IBikaMiningLayer
from bika.mining.tests.test_resultsxlsx import RESULTS_TESTING
from plone.app.testing import TEST_USER_ID, setRoles
from zope.component import getAdapter
from zope.interface import Interface, alsoProvides


class TestTemplateSamplingMethod(unittest.TestCase):
    layer = RESULTS_TESTING

    def setUp(self):
        portal = self.layer['portal']
        request = self.layer['request']
        setRoles(portal, TEST_USER_ID, ['Manager'])
        alsoProvides(request, IBikaMiningLayer)
        from archetypes.schemaextender.extender import disableCache
        disableCache(request)
        setup = api.get_senaite_setup()
        self.method = next(obj for obj in setup.samplingdeviations.objectValues()
                           if obj.Title() == 'Composite')
        self.template = api.create(setup.sampletemplates, 'SampleTemplate',
                                   title=u'Mining sampling template')
        field = IMiningSampleTemplate['sampling_method']
        field.set(IMiningSampleTemplate(self.template), self.method)
        self.client = api.create(portal.clients, 'Client',
                                 title=u'Mining client', ClientID='MINING')

    def test_composite_is_omitted_from_template_forms(self):
        from plone.autoform.interfaces import OMITTED_KEY
        from zope.component import getUtility
        from plone.dexterity.interfaces import IDexterityFTI
        schema = getUtility(IDexterityFTI, name='SampleTemplate').lookupSchema()
        self.assertIn((Interface, 'composite', 'true'),
                      schema.queryTaggedValue(OMITTED_KEY))

    def test_lookup_uses_sampling_deviations(self):
        field = IMiningSampleTemplate['sampling_method']
        self.assertEqual(field.get_allowed_types(), ('SamplingDeviation',))
        self.assertEqual(field.get(IMiningSampleTemplate(self.template)),
                         self.method)

    def test_registered_form_adapter_supplies_sampling_method(self):
        adapter = getAdapter(self.template, IAddSampleObjectInfo,
                             name='bika.mining.sampletemplate.info')
        values = adapter.get_object_info_with_record({})['field_values']
        self.assertEqual(values['SamplingDeviation'],
                         {'value': u'Composite', 'uid': api.get_uid(self.method)})

    def test_new_sample_inherits_template_sampling_method(self):
        sample = api.create(self.client, 'AnalysisRequest',
                            Template=api.get_uid(self.template))
        self.assertEqual(sample.getSamplingDeviation(), self.method)

    def test_explicit_sample_sampling_method_is_preserved(self):
        methods = api.get_senaite_setup().samplingdeviations
        grab = next(obj for obj in methods.objectValues() if obj.Title() == 'Grab')
        sample = api.create(self.client, 'AnalysisRequest',
                            Template=api.get_uid(self.template),
                            SamplingDeviation=api.get_uid(grab))
        self.assertEqual(sample.getSamplingDeviation(), grab)
