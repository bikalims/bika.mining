# -*- coding: utf-8 -*-
"""Sample deadlines, independent of analysis service turnaround times."""
from DateTime import DateTime
from bika.lims import api
from bika.lims.content.analysisrequest import AnalysisRequest


_get_due_date = AnalysisRequest.getDueDate
_get_late = AnalysisRequest.getLate


def target_hours(sample):
    field = sample.Schema().getField("TargetTAT")
    return field.get(sample) if field is not None else None


def elapsed_hours(received, published):
    if received is None or published is None:
        return None
    hours = (DateTime(published).timeTime() -
             DateTime(received).timeTime()) / 3600.0
    return hours if hours >= 0 else None


def get_due_date(self):
    hours = target_hours(self)
    if hours is None:
        return _get_due_date(self)
    received = self.getDateReceived()
    return DateTime(received) + hours / 24.0 if received else None


def get_late(self):
    if target_hours(self) is None:
        return _get_late(self)
    due = get_due_date(self)
    return bool(due and due < (self.getDatePublished() or DateTime()))


def actual_tat(sample):
    """Compute for existing published samples too, without a data migration."""
    if api.get_workflow_status_of(sample) != "published":
        return None
    field = sample.Schema().getField("TAT")
    value = field.get(sample) if field is not None else None
    if value is not None:
        return value
    return elapsed_hours(sample.getDateReceived(), sample.getDatePublished())
