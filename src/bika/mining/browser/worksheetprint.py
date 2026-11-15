# -*- coding: utf-8 -*-
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from bika.lims.browser.worksheet.views.printview import (
    PrintView as LegacyPrintView)
from senaite.core.browser.worksheets.worksheet.printview import PrintView


class MiningPrintTemplates(object):
    """Load mining templates explicitly: print embeds bypass jbot binding."""

    sample_by_row = ViewPageTemplateFile('templates/print/sample_by_row.pt')
    sample_by_column = ViewPageTemplateFile(
        'templates/print/sample_by_column.pt')

    def matrix_reference_title(self, ar):
        # TAL path expressions auto-call content objects. Retrieve the sample
        # directly from its dictionary so it remains an object, not HTML.
        sample = ar.get('sample', {}).get('obj')
        if sample is None:
            return u''
        field = sample.Schema().getField('MatrixReference')
        matrix = field.get(sample) if field is not None else None
        return matrix.Title() if matrix is not None else u''

    def renderWSTemplate(self):
        selected = self.request.get('template', self._TEMPLATES_LIST[0])
        prefix, _, filename = selected.rpartition(':')
        templates = {
            'sample_by_row.pt': 'sample_by_row',
            'sample_by_column.pt': 'sample_by_column',
        }
        if (prefix not in ('', 'Worksheet Print Templates') or
                filename not in templates):
            return super(MiningPrintTemplates, self).renderWSTemplate()
        html = getattr(self, templates[filename])()
        if self._current_ws_index < len(self._worksheets):
            self._current_ws_index += 1
        return html


class MiningPrintView(MiningPrintTemplates, LegacyPrintView):
    """Print mining worksheets using the legacy worksheet implementation."""


class MiningDexterityPrintView(MiningPrintTemplates, PrintView):
    """Print mining worksheets using the Dexterity implementation."""
