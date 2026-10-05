# -*- coding: utf-8 -*-
from bika.lims import api
from bika.lims.interfaces import IAddSampleObjectInfo
from bika.mining.config import is_installed
from bika.mining.extenders.sampletemplate import IMiningSampleTemplate
from zope.interface import implementer


def reference_value(obj):
    """Format for the sample creation form's reference fields."""
    if obj is None:
        return {"value": "", "uid": ""}
    return {"value": api.get_title(obj), "uid": api.get_uid(obj)}


@implementer(IAddSampleObjectInfo)
class MatrixReferenceInfo(object):
    def __init__(self, context):
        self.context = context

    def get_object_info_with_record(self, record):
        if not is_installed():
            return {}
        return {"field_values": {
            "TargetTAT": {"value": self.context.target_tat},
        }}


@implementer(IAddSampleObjectInfo)
class SampleTemplateInfo(object):
    def __init__(self, context):
        self.context = context

    def get_object_info_with_record(self, record):
        if not is_installed():
            return {}
        field = IMiningSampleTemplate["matrix_reference"]
        matrix = field.get(IMiningSampleTemplate(self.context))
        target = getattr(self.context, "target_tat", None)
        if target is None and matrix is not None:
            target = matrix.target_tat
        return {"field_values": {
            "MatrixReference": reference_value(matrix),
            "TargetTAT": {"value": target},
        }}
