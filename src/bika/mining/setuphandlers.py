# -*- coding: utf-8 -*-
from Products.CMFPlone.interfaces import INonInstallable
from zope.interface import implementer


@implementer(INonInstallable)
class HiddenProfiles(object):

    def getNonInstallableProfiles(self):
        """Hide uninstall profile from site-creation and quickinstaller."""
        return [
            'bika.mining:uninstall',
        ]


def post_install(context):
    """Post install script"""
    from bika.lims import api
    from senaite.core.setuphandlers import add_dexterity_items
    add_dexterity_items(api.get_setup(), [
        ("matrixreferences", "Matrix References", "MatrixReferences"),
        ("shifts", "Shifts", "Shifts"),
        ("classifications", "Classifications", "Classifications"),
        ("drumbatches", "Drum/Batch", "DrumBatches"),
    ])


def upgrade(context):
    """Apply new definitions without purging existing setup records."""
    context.runImportStepFromProfile("profile-bika.mining:default", "rolemap")
    context.runImportStepFromProfile("profile-bika.mining:default", "typeinfo")
    context.runImportStepFromProfile("profile-bika.mining:default", "workflow")
    post_install(context)


def uninstall(context):
    """Uninstall script"""
    # Do something at the end of the uninstallation of this package.
