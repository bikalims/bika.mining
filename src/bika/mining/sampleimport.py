# -*- coding: utf-8 -*-
"""Optional mining integration for senaite.sampleimporter."""
from archetypes.schemaextender.interfaces import IBrowserLayerAwareExtender
from archetypes.schemaextender.interfaces import ISchemaModifier
from bika.lims.vocabularies import CatalogVocabulary
from bika.mining.config import is_installed
from bika.mining.extenders.analysisrequest import validate_target_tat
from bika.mining.interfaces import IBikaMiningLayer
from Products.Archetypes.interfaces import IVocabulary
from Products.DataGridField import Column, SelectColumn
from senaite.sampleimporter.content.sampleimport import SampleImport
from senaite.sampleimporter.interfaces import ISampleImport
from zope.component import adapts
from zope.interface import implementer


MINING_COLUMNS = (
    ('MatrixReference', 'Matrix Reference'),
    ('Shift', 'Shift'),
    ('Classification', 'Classification'),
    ('DrumBatch', 'Drum/Batch'),
    ('SamplingDeviation', 'Sampling Method'),
    ('TargetTAT', 'Target TAT (h)'),
)


@implementer(IVocabulary)
class MiningVocabulary(object):
    """Supply lookup choices without adding methods to SampleImport."""

    def __init__(self, portal_type):
        self.portal_type = portal_type

    def getDisplayList(self, instance):
        vocabulary = CatalogVocabulary(instance)
        vocabulary.catalog = 'senaite_catalog_setup'
        return vocabulary(allow_blank=True, portal_type=self.portal_type,
                          is_active=True)


@implementer(ISchemaModifier, IBrowserLayerAwareExtender)
class SampleImportSchemaModifier(object):
    adapts(ISampleImport)
    layer = IBikaMiningLayer

    def __init__(self, context):
        self.context = context

    def fiddle(self, schema):
        # Copy the field and widget before modifying shared importer schema.
        field = schema['SampleData'].copy()
        columns = list(field.columns)
        position = columns.index('SampleType') + 1
        for name, label in MINING_COLUMNS:
            if name not in columns:
                columns.insert(position, name)
                position += 1
            if name == 'TargetTAT':
                column = Column(label)
            else:
                column = SelectColumn(label, MiningVocabulary(name))
            field.widget.columns[name] = column
        field.columns = tuple(columns)
        schema['SampleData'] = field
        return schema


def target_hours(row_nr, value):
    error = validate_target_tat(value)
    if error is not True:
        raise ValueError('Row %s: TargetTAT: %s (%s)' %
                         (row_nr, error, value))
    return None if value in (None, '') else float(value)


# Keep the importer implementation available for every other field and site.
_munge_field_value = SampleImport.munge_field_value.im_func
_validate_against_schema = SampleImport.validate_against_schema.im_func
_get_sample_values = SampleImport.get_sample_values.im_func


def get_sample_values(self):
    data = _get_sample_values(self)
    if not is_installed():
        return data
    aliases = {'Sampling Method': 'SamplingDeviation',
               'SamplingMethod': 'SamplingDeviation'}
    headers = [aliases.get(name, name) for name in data.get('headers', [])]
    if headers.count('SamplingDeviation') > 1:
        raise ValueError('Use only one Sampling Method column')
    if 'headers' in data:
        data['headers'] = headers
    data['samples'] = [
        [(aliases.get(name, name), value) for name, value in row]
        for row in data['samples']]
    return data


def munge_field_value(self, schema, row_nr, fieldname, value):
    if fieldname == 'TargetTAT' and is_installed():
        hours = target_hours(row_nr, value)
        # DataGridField scalar cells must remain strings, including zero.
        return '' if hours is None else str(hours)
    return _munge_field_value(self, schema, row_nr, fieldname, value)


def validate_against_schema(self, schema, row_nr, fieldname, value):
    if fieldname == 'TargetTAT' and is_installed():
        return target_hours(row_nr, value)
    return _validate_against_schema(self, schema, row_nr, fieldname, value)
