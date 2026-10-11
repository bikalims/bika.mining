# -*- coding: utf-8 -*-
"""Mining CSV values must survive parsing and validate before import."""
import unittest
from bika.mining import sampleimport as integration
from senaite.sampleimporter.content import sampleimport as upstream


def method(name):
    value = getattr(upstream.SampleImport, name)
    return getattr(value, 'im_func', value)


class Importer(object):
    get_sample_values = method('get_sample_values')
    lookup = method('lookup')

    def getOriginalFile(self):
        return self


class Field(object):
    type = 'uidreference'
    multiValued = False
    required = False


class Brain(object):
    UID = 'lookup-uid'


class MiningImporter(Importer):
    munge_field_value = integration.munge_field_value
    validate_against_schema = integration.validate_against_schema
    validate_target_tat = staticmethod(integration.target_hours)


class TestMiningValues(unittest.TestCase):
    def setUp(self):
        self.importer = MiningImporter()
        original = integration.is_installed
        integration.is_installed = lambda: True
        self.addCleanup(setattr, integration, 'is_installed', original)

    def test_mining_columns_parse_by_name(self):
        self.importer.data = (
            'Samples,MatrixReference,Shift,Classification,DrumBatch,TargetTAT\n'
            'Sample 1,Ore,Day,Production,Batch 1,0')
        row = dict(self.importer.get_sample_values()['samples'][0])
        self.assertEqual(row['MatrixReference'], 'Ore')
        self.assertEqual(row['Shift'], 'Day')
        self.assertEqual(row['Classification'], 'Production')
        self.assertEqual(row['DrumBatch'], 'Batch 1')
        self.assertEqual(row['TargetTAT'], '0')

    def test_mining_references_accept_title_and_uid(self):
        for name in ('MatrixReference', 'Shift', 'Classification', 'DrumBatch'):
            field = Field()
            field.allowed_types = (name,)
            schema = {name: field}
            for value in ('Lookup title', Brain.UID):
                self.importer.lookup = lambda types, **kw: (
                    [Brain()] if kw.get('title') == 'Lookup title' or
                    kw.get('UID') == Brain.UID else [])
                self.assertEqual(self.importer.munge_field_value(
                    schema, 1, name, value), Brain.UID)
            self.importer.lookup = lambda *args, **kw: []
            with self.assertRaises(ValueError):
                self.importer.munge_field_value(schema, 2, name, 'Missing')

    def test_target_tat_is_numeric_including_zero(self):
        schema = {'TargetTAT': object()}
        for value, expected in (('', None), ('0', 0.0), ('8.5', 8.5)):
            self.assertEqual(self.importer.munge_field_value(
                schema, 1, 'TargetTAT', value),
                '' if expected is None else str(expected))
            self.assertEqual(self.importer.validate_against_schema(
                schema, 1, 'TargetTAT', value), expected)

    def test_invalid_target_tat_reports_row(self):
        for value in ('-1', 'nan', 'inf', '-inf', 'tomorrow'):
            with self.assertRaises(ValueError) as error:
                self.importer.validate_target_tat(3, value)
            self.assertIn('Row 3', str(error.exception))
            self.assertIn('TargetTAT', str(error.exception))

    def test_grid_storage_preserves_all_mining_cells(self):
        from Products.Archetypes.Storage import AttributeStorage
        from senaite.sampleimporter.content.sampleimport import SampleData
        from Products.Archetypes.atapi import Schema
        schema = Schema((SampleData.copy(),))
        integration.SampleImportSchemaModifier(None).fiddle(schema)
        field = schema['SampleData']
        field.storage = AttributeStorage()
        record = type('Record', (object,), {})()
        row = dict(ClientSampleID='ID1', MatrixReference='matrix-uid',
                   Shift='shift-uid', Classification='class-uid',
                   DrumBatch='drum-uid', TargetTAT='0.0')
        field.set(record, [row])
        saved = field.get(record)[0]
        for name, value in row.items():
            self.assertEqual(saved[name], value)

    def test_download_template_has_mining_columns_and_client(self):
        import csv
        from StringIO import StringIO
        from bika.mining.browser import sampleimport as browser
        class Client(object):
            def Title(self):
                return u'Mining, Client'
            def getClientID(self):
                return 'MC'
        class Response(object):
            def setHeader(self, name, value):
                pass
        class Request(object):
            response = Response()
        class Catalog(object):
            def uniqueValuesFor(self, name):
                return ['Au', 'Fe']
        original = browser.api.get_tool
        browser.api.get_tool = lambda name: Catalog()
        try:
            data = browser.SampleImportTemplateView(Client(), Request())()
        finally:
            browser.api.get_tool = original
        rows = list(csv.reader(StringIO(data)))
        self.assertEqual(rows[1][1:3], ['Mining, Client', 'MC'])
        for name in ('MatrixReference', 'Shift', 'Classification',
                     'DrumBatch', 'TargetTAT', 'Au', 'Fe'):
            self.assertIn(name, rows[3])
        self.assertNotIn('TATStatus', rows[3])
        self.assertEqual(len(rows[3]), len(rows[4]))


    def test_modifier_keeps_upstream_schema_unchanged(self):
        from Products.Archetypes.atapi import Schema
        field = upstream.SampleData
        columns = field.columns
        widgets = dict(field.widget.columns)
        schema = Schema((field.copy(),))
        modifier = integration.SampleImportSchemaModifier(None)
        modifier.fiddle(schema)
        modifier.fiddle(schema)
        for name, label in integration.MINING_COLUMNS:
            self.assertEqual(schema['SampleData'].columns.count(name), 1)
        self.assertEqual(field.columns, columns)
        self.assertEqual(field.widget.columns, widgets)
        self.assertNotIn('TargetTAT', field.columns)

    def test_without_mining_layer_uses_upstream_behavior(self):
        integration.is_installed = lambda: False
        schema = {'TargetTAT': type('Field', (object,), {'type': 'float'})()}
        self.assertEqual(self.importer.munge_field_value(
            schema, 1, 'TargetTAT', '-1'), '-1')
        self.assertEqual(self.importer.validate_against_schema(
            schema, 1, 'TargetTAT', '-1'), '-1')
