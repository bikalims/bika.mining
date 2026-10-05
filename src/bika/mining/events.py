# -*- coding: utf-8 -*-
from DateTime import DateTime
from bika.lims import api
from bika.mining.extenders.sampletemplate import IMiningSampleTemplate
from senaite.core.content.sampletemplate import ISampleTemplateSchema


def populate_sample_template(template, event):
    """Fill shared fields on save, keeping explicit template values."""
    if not getattr(template, "matrix_reference", None):
        return
    matrix = IMiningSampleTemplate["matrix_reference"].get(template)
    if matrix is None:
        return
    changed = False
    for template_name, matrix_name in (
        ("samplepoint", "plant_sample_id"),
        ("sampletype", "sample_type"),
    ):
        field = ISampleTemplateSchema[template_name]
        # Check stored UIDs so an existing reference is never overwritten.
        if field.get_raw(template):
            continue
        value = matrix.accessor(matrix_name)(matrix)
        if value is not None:
            field.set(template, value)
            changed = True
    if getattr(template, "target_tat", None) in (None, ""):
        target = getattr(matrix, "target_tat", None)
        if target is not None:
            template.target_tat = target
            changed = True
    if changed:
        template.reindexObject()


def get_field_value(sample, name):
    field = sample.Schema().getField(name)
    return field.get(sample) if field is not None else None


def initialize_sample(sample, event):
    """Resolve template defaults for both UI and programmatic creation."""
    fields = sample.Schema()
    matrix_field = fields.getField("MatrixReference")
    target_field = fields.getField("TargetTAT")
    if matrix_field is None or target_field is None:
        return
    matrix = matrix_field.get(sample)
    template = sample.getTemplate()
    if template is not None:
        if matrix is None:
            matrix = IMiningSampleTemplate["matrix_reference"].get(
                IMiningSampleTemplate(template))
            if matrix is not None:
                matrix_field.set(sample, api.get_uid(matrix))
        target = getattr(template, "target_tat", None)
        if target_field.get(sample) is None and target is not None:
            target_field.set(sample, target)
    if matrix is not None and target_field.get(sample) is None:
        if matrix.target_tat is not None:
            target_field.set(sample, matrix.target_tat)


def tat_status(hours, received, published):
    """Classify elapsed time from lab receipt, including the exact deadline."""
    if hours is None or received is None or published is None:
        return ""
    received = DateTime(received)
    published = DateTime(published)
    elapsed = (published.timeTime() - received.timeTime()) / 3600.0
    if elapsed < 0:
        return ""
    return "On Time" if elapsed <= hours else "Late"


def after_transition(sample, event):
    """Persist the sample's TAT outcome at results publication."""
    field = sample.Schema().getField("TATStatus")
    if field is None or event.transition is None:
        return
    if event.transition.id == "publish":
        published = sample.getDatePublished()
        if published is None:
            published = event.status.get("time")
        field.set(sample, tat_status(
            get_field_value(sample, "TargetTAT"),
            sample.getDateReceived(), published))
        sample.reindexObject()
    elif event.transition.new_state_id != "published":
        field.set(sample, "")
