# -*- coding: utf-8 -*-
import csv
from StringIO import StringIO
from bika.lims import api
from bika.lims.browser import BrowserView
from bika.mining.sampleimport import MINING_COLUMNS


class SampleImportTemplateView(BrowserView):
    """Download a client-specific CSV template, including mining inputs."""

    def __call__(self):
        output = StringIO()
        writer = csv.writer(output)

        def write_row(values):
            writer.writerow([v.encode('utf-8') if isinstance(v, unicode)
                             else v for v in values])
        write_row(['Header', 'Client name', 'Client ID', 'Contact'])
        write_row(['Header Data', self.context.Title(),
                   self.context.getClientID(), ''])
        write_row([])
        columns = ['ClientSampleID', 'DateSampled', 'SamplePoint', 'SampleType',
                   'SampleContainer'] + [
                       label if name == 'SamplingDeviation' else name
                       for name, label in MINING_COLUMNS]
        catalog = api.get_tool('senaite_catalog_setup')
        keywords = sorted(k for k in catalog.uniqueValuesFor('getKeyword')
                          if k and k not in columns)
        write_row(['Samples'] + columns + keywords)
        write_row(['Sample 1'] + [''] * (len(columns) + len(keywords)))
        self.request.response.setHeader('Content-Type', 'text/csv; charset=utf-8')
        self.request.response.setHeader(
            'Content-Disposition',
            'attachment; filename="SampleImportTemplate.csv"')
        return output.getvalue()
