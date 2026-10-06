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
    setup_mining_folders(context)


def setup_matrixreferences(context):
    """Keep Matrix References in the new setup, preserving existing UIDs."""
    migrate_setup_folders([
        ("matrixreferences", "Matrix References", "MatrixReferences"),
    ])


def setup_mining_folders(context):
    """Move all mining lookup folders to the new setup without copying."""
    migrate_setup_folders([
        ("matrixreferences", "Matrix References", "MatrixReferences"),
        ("shifts", "Shifts", "Shifts"),
        ("classifications", "Classifications", "Classifications"),
        ("drumbatches", "Drum/Batch", "DrumBatches"),
    ])


def migrate_setup_folders(items):
    """Preflight merges, then move folders or their existing records."""
    from bika.lims import api
    from senaite.core.setuphandlers import add_dexterity_items
    setup = api.get_senaite_setup()
    old_setup = api.get_setup()
    folders = []
    for id, title, portal_type in items:
        old_folder = old_setup.get(id) if old_setup is not None else None
        folder = setup.get(id)
        if old_folder is not None and folder is not None:
            collisions = set(old_folder.objectIds()).intersection(folder.objectIds())
            if collisions:
                raise ValueError("%s migration has conflicting IDs: %s"
                                 % (title, ", ".join(sorted(collisions))))
        folders.append((id, old_folder, folder))
    for id, old_folder, folder in folders:
        if old_folder is None:
            continue
        if folder is None:
            api.move_object(old_folder, setup, check_constraints=False)
        else:
            for obj in list(old_folder.objectValues()):
                api.move_object(obj, folder, check_constraints=False)
            old_setup.manage_delObjects([id])
    add_dexterity_items(setup, items)


def upgrade(context):
    """Apply new definitions without purging existing setup records."""
    context.runImportStepFromProfile("profile-bika.mining:default", "rolemap")
    context.runImportStepFromProfile("profile-bika.mining:default", "typeinfo")
    context.runImportStepFromProfile("profile-bika.mining:default", "workflow")
    post_install(context)


def uninstall(context):
    """Uninstall script"""
    # Do something at the end of the uninstallation of this package.
