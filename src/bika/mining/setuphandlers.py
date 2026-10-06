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
    setup_matrixreferences(context)
    add_dexterity_items(api.get_setup(), [
        ("shifts", "Shifts", "Shifts"),
        ("classifications", "Classifications", "Classifications"),
        ("drumbatches", "Drum/Batch", "DrumBatches"),
    ])


def setup_matrixreferences(context):
    """Keep Matrix References in the new setup, preserving existing UIDs."""
    from bika.lims import api
    from senaite.core.setuphandlers import add_dexterity_items
    setup = api.get_senaite_setup()
    old_setup = api.get_setup()
    old_folder = old_setup.get("matrixreferences") if old_setup is not None else None
    folder = setup.get("matrixreferences")
    if old_folder is not None:
        if folder is None:
            api.move_object(old_folder, setup, check_constraints=False)
        else:
            collisions = set(old_folder.objectIds()).intersection(folder.objectIds())
            if collisions:
                raise ValueError("Matrix References migration has conflicting IDs: %s"
                                 % ", ".join(sorted(collisions)))
            for obj in list(old_folder.objectValues()):
                api.move_object(obj, folder, check_constraints=False)
            old_setup.manage_delObjects(["matrixreferences"])
    add_dexterity_items(setup, [
        ("matrixreferences", "Matrix References", "MatrixReferences"),
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
