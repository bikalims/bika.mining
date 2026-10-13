# -*- coding: utf-8 -*-
import unittest
from DateTime import DateTime
from bika.mining import tat, events
from bika.mining.browser import samples
from bika.mining import setuphandlers


class Field(object):
    def __init__(self, value=None):
        self.value = value

    def get(self, context):
        return self.value

    def set(self, context, value):
        self.value = value


class Sample(object):
    def __init__(self, target=8.0):
        self.fields = dict(TargetTAT=Field(target), TAT=Field(),
                           TATStatus=Field())
        self.received = DateTime("2026/10/01 08:00 UTC")
        self.published = None
        self.reindexed = False

    def Schema(self):
        return self

    def getField(self, name):
        return self.fields.get(name)

    def getDateReceived(self):
        return self.received

    def getDatePublished(self):
        return self.published

    def reindexObject(self, **kw):
        self.reindexed = True


class TestSampleTAT(unittest.TestCase):
    def test_sample_target_overrides_analysis_due_date(self):
        sample = Sample()
        self.assertEqual(tat.get_due_date(sample), sample.received + 8.0 / 24)

    def test_zero_target_is_receipt_deadline(self):
        sample = Sample(0.0)
        self.assertEqual(tat.get_due_date(sample), sample.received)

    def test_no_receipt_has_no_deadline(self):
        sample = Sample()
        sample.received = None
        self.assertIsNone(tat.get_due_date(sample))
        self.assertFalse(tat.get_late(sample))

    def test_missing_target_delegates_to_core(self):
        due, late = tat._get_due_date, tat._get_late
        try:
            tat._get_due_date = lambda sample: "core deadline"
            tat._get_late = lambda sample: "core late"
            sample = Sample(None)
            self.assertEqual(tat.get_due_date(sample), "core deadline")
            self.assertEqual(tat.get_late(sample), "core late")
            del sample.fields["TargetTAT"]
            self.assertEqual(tat.get_due_date(sample), "core deadline")
        finally:
            tat._get_due_date, tat._get_late = due, late

    def test_publication_at_deadline_is_on_time(self):
        sample = Sample()
        sample.published = tat.get_due_date(sample)
        self.assertFalse(tat.get_late(sample))
        self.assertEqual(events.tat_status(8, sample.received,
                                           sample.published), "On Time")
        sample.published += 1.0 / 86400
        self.assertTrue(tat.get_late(sample))
        self.assertEqual(events.tat_status(8, sample.received,
                                           sample.published), "Late")

    def test_publication_records_actual_hours_and_clears_on_reopen(self):
        sample = Sample()
        sample.published = sample.received + 10.0 / 24
        event = type("Event", (), {})()
        event.transition = type("Transition", (), {
            "id": "publish", "new_state_id": "published"})()
        events.after_transition(sample, event)
        self.assertAlmostEqual(sample.fields["TAT"].value, 10)
        self.assertEqual(sample.fields["TATStatus"].value, "Late")
        event.transition.id = "retract"
        event.transition.new_state_id = "sample_received"
        sample.reindexed = False
        events.after_transition(sample, event)
        self.assertIsNone(sample.fields["TAT"].value)
        self.assertEqual(sample.fields["TATStatus"].value, "")
        self.assertTrue(sample.reindexed)

    def test_actual_tat_is_published_only_and_supports_existing_samples(self):
        original = tat.api.get_workflow_status_of
        try:
            sample = Sample()
            sample.published = sample.received + 0.5
            tat.api.get_workflow_status_of = lambda obj: "published"
            self.assertEqual(tat.actual_tat(sample), 12)
            sample.fields["TAT"].value = 0.0
            self.assertEqual(tat.actual_tat(sample), 0)
            tat.api.get_workflow_status_of = lambda obj: "verified"
            self.assertIsNone(tat.actual_tat(sample))
        finally:
            tat.api.get_workflow_status_of = original

    def test_listing_columns_are_added_once_to_every_state(self):
        original = samples.is_installed
        try:
            samples.is_installed = lambda: True
            listing = type("Listing", (), {})()
            listing.columns = {}
            listing.review_states = [{"columns": ["Title"]},
                                     {"columns": ["Title"]}]
            adapter = samples.SamplesListingViewAdapter(listing, None)
            adapter.before_render()
            adapter.before_render()
            for state in listing.review_states:
                self.assertEqual(state["columns"], ["Title", "TargetTAT", "TAT"])
        finally:
            samples.is_installed = original

    def test_upgrade_backfills_published_samples_and_refreshes_deadlines(self):
        search = tat.api.search
        get_object = tat.api.get_object
        status = tat.api.get_workflow_status_of
        try:
            published, pending = Sample(), Sample()
            published.published = published.received + 0.5
            tat.api.search = lambda query: [published, pending]
            tat.api.get_object = lambda obj: obj
            tat.api.get_workflow_status_of = lambda obj: (
                "published" if obj is published else "sample_received")
            setuphandlers.upgrade_sample_tat(None)
            self.assertEqual(published.fields["TAT"].value, 12)
            self.assertEqual(published.fields["TATStatus"].value, "Late")
            self.assertIsNone(pending.fields["TAT"].value)
            self.assertTrue(published.reindexed)
            self.assertTrue(pending.reindexed)
        finally:
            tat.api.search = search
            tat.api.get_object = get_object
            tat.api.get_workflow_status_of = status
