# -*- coding: utf-8 -*-
"""Mining setup-data worksheet importers."""
import math

from Products.CMFPlone.utils import safe_unicode
from bika.lims import api, logger
from senaite.core.catalog import SETUP_CATALOG
from senaite.core.exportimport.setupdata import WorksheetImporter


def _as_text(value):
    if value is None:
        return u""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    value = safe_unicode(value)
    if not hasattr(value, "strip"):
        value = safe_unicode(str(value))
    return value.strip()


def _key(value):
    return u" ".join(_as_text(value).split()).lower()


class Matrix_References(WorksheetImporter):
    """Import the Matrix References sheet using the setup-data conventions.

    Headers occupy row 1, descriptions row 2, examples row 3 and data row 4
    onwards. References are deferred so sheet order does not matter.
    """

    def value(self, row, *names):
        for name in names:
            if _key(name) in row:
                return _as_text(row[_key(name)])
        return u""

    def Import(self):
        folder = api.get_senaite_setup().matrixreferences
        existing = set(_key(obj.Title())
                       for obj in folder.objectValues("MatrixReference"))
        for number, source in enumerate(self.get_rows(3), 4):
            row = {_key(name): value for name, value in source.items()}
            title = self.value(row, "Title", "Matrix Ref", "Matrix Reference")
            if not title:
                continue
            if _key(title) in existing:
                logger.info("Skipping existing Matrix Reference '%s'", title)
                continue
            tat = self.value(row, "Target TAT (h)", "Target TAT", "target_tat")
            target_tat = None
            if tat:
                try:
                    target_tat = float(tat)
                except ValueError:
                    raise ValueError("Matrix References row %s: invalid Target TAT '%s'"
                                     % (number, tat))
                if (target_tat < 0 or math.isnan(target_tat)
                        or math.isinf(target_tat)):
                    raise ValueError("Matrix References row %s: Target TAT must be finite and non-negative"
                                     % number)
            obj = api.create(
                folder, "MatrixReference", title=title,
                description=self.value(row, "Description"),
                area=self.value(row, "Area"),
                circuit_area=self.value(row, "Circuit / Area", "Circuit Area", "circuit_area"),
                target_tat=target_tat,
            )
            for field, portal_type, names in (
                    ("plant_sample_id", "SamplePoint", ("Plant Sample ID", "Sample Point", "plant_sample_id")),
                    ("sample_type", "SampleType", ("Sample Type", "sample_type"))):
                value = self.value(row, *names)
                if value:
                    self.defer(src_obj=obj, src_field=field,
                               dest_catalog=SETUP_CATALOG,
                               dest_query={"portal_type": portal_type,
                                           "title": value})
            obj.reindexObject()
            existing.add(_key(title))
            logger.info("Created Matrix Reference '%s'", title)
