# -*- coding: utf-8 -*-
import unittest
from bika.mining import events
from bika.mining.events import populate_sample_template


class Record(object):
    def __init__(self, **values):
        self.__dict__.update(values)
        self.reindexed = False

    def reindexObject(self):
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
