# -*- coding: utf-8 -*-
"""ID Server configuration and readable filenames for mining workbooks."""
import re

from DateTime import DateTime
from bika.lims import api
from senaite.core.idserver import idserver
from senaite.core.interfaces import IIdServerVariables
from zope.interface import implementer


REPORT_TYPE = "ResultsReport"
DEFAULT_FORMAT = u"COA{year}-{seq:04d} {clientId} {yymmdd} {hh:mm}"


class ReportTime(object):
    """Python parses {hh:mm} as variable hh with format specification mm."""

    def __init__(self, now):
        self.now = now

    def __format__(self, spec):
        if spec == "mm":
            return self.now.strftime("%H:%M")
        return format(self.now.strftime("%H"), spec)


@implementer(IIdServerVariables)
class ReportVariables(object):
    def __init__(self, context):
        self.context = context

    def get_variables(self, **kw):
        return {"hh": ReportTime(DateTime())}


def setup_xlsx_format(context=None):
    """Use ResultsReport formatting, retaining administrator customizations."""
    setup = api.get_senaite_setup()
    rows = list(setup.getIDFormatting() or [])
    rows = [row for row in rows
            if row.get("portal_type", "").lower() != "miningresultsxlsx"]
    if any(row.get("portal_type", "").lower() == REPORT_TYPE.lower()
           for row in rows):
        if rows != list(setup.getIDFormatting() or []):
            setup.setIDFormatting(rows)
        return
    rows.append({"portal_type": REPORT_TYPE, "form": DEFAULT_FORMAT,
                 "sequence_type": "generated", "split_length": 1,
                 "prefix": "resultsreport"})
    setup.setIDFormatting(rows)


def xlsx_filename(report):
    """Use ID Server counters without its content-ID whitespace normalization."""
    setup_xlsx_format()
    kw = {"portal_type": REPORT_TYPE}
    config = idserver.get_config(report, **kw)
    variables = idserver.get_variables(report, **kw)
    number = 0
    sequence_type = config.get("sequence_type", "generated")
    if sequence_type == "generated":
        # Report creation has already advanced this counter. Read its value
        # immediately after creation rather than issuing a second number.
        number = idserver.get_generated_number(
            report, config, variables, dry_run=True, **kw)
    elif sequence_type == "counter":
        number = idserver.get_counted_number(report, config, variables, **kw)
    variables["seq"] = idserver.to_int(number)
    variables["alpha"] = number
    name = api.safe_unicode(config["form"]).format(**variables)
    # Keep the requested spaces and time colon; exclude paths/header controls.
    name = re.sub(u'[\\\\/\x00-\x1f\x7f]', u"_", name).strip().strip(u".")
    if not name:
        raise ValueError("Mining Results XLSX filename must not be empty")
    return name + u".xlsx"
