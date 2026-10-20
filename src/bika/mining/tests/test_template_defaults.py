# -*- coding: utf-8 -*-
import unittest
from bika.mining import events
from bika.mining.events import populate_sample_template


class Record(object):
    def __init__(self, **values):
        self.__dict__.update(values)
        self.reindexed = False

    def reindexObject(self, *args, **kwargs):
        self.reindexed = True


class Field(object):
    def __init__(self, value=None):
        self.value = value
        self.calls = []

    def get(self, context):
        return self.value

    get_raw = get

    def set(self, context, value):
        self.calls.append((context, value))
        self.value = value


class TestTemplateDefaults(unittest.TestCase):
    """Exercise save defaults independently of a running database."""

    def setUp(self):
        self.template = Record(matrix_reference=["matrix-uid"], target_tat=None)
        self.matrix = Record(target_tat=8.0)
        self.point = object()
        self.sample_type = object()
        self.matrix.accessor = lambda name: (
            lambda context: {"plant_sample_id": self.point,
                             "sample_type": self.sample_type}[name])
        self.point_field = Field()
        self.type_field = Field()

    def populate(self):
        mining, schema = events.IMiningSampleTemplate, events.ISampleTemplateSchema
        try:
            events.IMiningSampleTemplate = {"matrix_reference": Field(self.matrix)}
            events.ISampleTemplateSchema = {
                "samplepoint": self.point_field, "sampletype": self.type_field}
            populate_sample_template(self.template, None)
        finally:
            events.IMiningSampleTemplate, events.ISampleTemplateSchema = mining, schema

    def test_fills_empty_common_fields(self):
        self.populate()
        self.assertEqual(self.point_field.calls, [(self.template, self.point)])
        self.assertEqual(self.type_field.calls, [(self.template, self.sample_type)])
        self.assertEqual(self.template.target_tat, 8.0)
        self.assertTrue(self.template.reindexed)

    def test_preserves_explicit_values_including_zero_target(self):
        self.point_field.value = "existing-point"
        self.type_field.value = "existing-type"
        self.template.target_tat = 0.0
        self.populate()
        self.assertFalse(self.point_field.calls)
        self.assertFalse(self.type_field.calls)
        self.assertEqual(self.template.target_tat, 0.0)
        self.assertFalse(self.template.reindexed)

    def test_fills_only_missing_field(self):
        self.type_field.value = "existing-type"
        self.template.target_tat = 4.0
        self.populate()
        self.assertEqual(self.point_field.calls, [(self.template, self.point)])
        self.assertFalse(self.type_field.calls)
        self.assertEqual(self.template.target_tat, 4.0)

    def test_no_matrix_reference(self):
        self.template.matrix_reference = None
        populate_sample_template(self.template, None)
        self.assertFalse(self.template.reindexed)

    def test_empty_matrix_fields_leave_template_empty(self):
        self.matrix.accessor = lambda name: lambda context: None
        self.matrix.target_tat = None
        self.populate()
        self.assertFalse(self.point_field.calls)
        self.assertFalse(self.type_field.calls)
        self.assertIsNone(self.template.target_tat)
        self.assertFalse(self.template.reindexed)


class TestSamplingMethodDefaults(unittest.TestCase):
    def setUp(self):
        from bika.mining import adapters
        self.adapters = adapters
        self.method = Record(uid='method-uid', title=u'Composite')
        self.template = Record(target_tat=None)
        class Behavior(dict):
            def __call__(self, context):
                return context
        self.behavior = Behavior(matrix_reference=Field(),
                                 sampling_method=Field(self.method))
        for module in (events, adapters):
            original = module.IMiningSampleTemplate
            module.IMiningSampleTemplate = self.behavior
            self.addCleanup(setattr, module, 'IMiningSampleTemplate', original)
        original = events.api.get_uid
        events.api.get_uid = lambda obj: obj.uid
        self.addCleanup(setattr, events.api, 'get_uid', original)
        original = adapters.api.get_title
        adapters.api.get_title = lambda obj: obj.title
        self.addCleanup(setattr, adapters.api, 'get_title', original)
        original = adapters.is_installed
        adapters.is_installed = lambda: True
        self.addCleanup(setattr, adapters, 'is_installed', original)
        self.method_field = Field()
        fields = {'MatrixReference': Field(), 'TargetTAT': Field(),
                  'SamplingDeviation': self.method_field}
        self.sample = Record(Schema=lambda: Record(getField=fields.get),
                             getTemplate=lambda: self.template)

    def test_created_sample_inherits_template_method_without_matrix(self):
        events.initialize_sample(self.sample, None)
        self.assertEqual(self.method_field.value, 'method-uid')

    def test_explicit_sample_method_is_preserved(self):
        self.method_field.value = 'explicit-method-uid'
        events.initialize_sample(self.sample, None)
        self.assertEqual(self.method_field.value, 'explicit-method-uid')
        self.assertEqual(self.method_field.calls, [])

    def test_template_without_method_leaves_sample_empty(self):
        self.behavior['sampling_method'].value = None
        events.initialize_sample(self.sample, None)
        self.assertIsNone(self.method_field.value)
        self.assertEqual(self.method_field.calls, [])

    def test_sample_form_receives_template_method(self):
        values = self.adapters.SampleTemplateInfo(
            self.template).get_object_info_with_record({})['field_values']
        self.assertEqual(values['SamplingDeviation'],
                         {'value': u'Composite', 'uid': 'method-uid'})

    def test_empty_template_clears_form_method(self):
        self.behavior['sampling_method'].value = None
        values = self.adapters.SampleTemplateInfo(
            self.template).get_object_info_with_record({})['field_values']
        self.assertEqual(values['SamplingDeviation'], {'value': '', 'uid': ''})
