# -*- coding: utf-8 -*-
import unittest
from bika.lims import api
from bika.mining import setuphandlers
from senaite.core import setuphandlers as core_setup


class Folder(dict):
    def objectValues(self):
        return list(self.values())

    def objectIds(self):
        return list(self.keys())

    def manage_delObjects(self, ids):
        for id in ids:
            del self[id]


class TestMatrixReferenceMigration(unittest.TestCase):
    def setUp(self):
        self.old = Folder()
        self.new = Folder()
        self.moves = []
        self.originals = (api.get_setup, api.get_senaite_setup,
                          api.move_object, core_setup.add_dexterity_items)
        api.get_setup = lambda: self.old
        api.get_senaite_setup = lambda: self.new

        def move(obj, destination, **kwargs):
            self.assertFalse(kwargs["check_constraints"])
            self.moves.append((obj, destination))
            origin = self.old if obj is self.old.get("matrixreferences") else self.old["matrixreferences"]
            id = next(key for key, value in origin.items() if value is obj)
            del origin[id]
            destination[id] = obj

        def add(container, items):
            self.assertIs(container, self.new)
            for id, title, portal_type in items:
                if id not in container:
                    container[id] = Folder()

        api.move_object = move
        core_setup.add_dexterity_items = add

    def tearDown(self):
        (api.get_setup, api.get_senaite_setup, api.move_object,
         core_setup.add_dexterity_items) = self.originals

    def test_fresh_install_and_repeat(self):
        setuphandlers.setup_matrixreferences(None)
        folder = self.new["matrixreferences"]
        setuphandlers.setup_matrixreferences(None)
        self.assertIs(self.new["matrixreferences"], folder)
        self.assertEqual(self.moves, [])

    def test_moves_existing_folder_without_copying_records(self):
        record = object()
        folder = Folder(reference=record)
        self.old["matrixreferences"] = folder
        setuphandlers.setup_matrixreferences(None)
        self.assertIs(self.new["matrixreferences"], folder)
        self.assertIs(folder["reference"], record)
        self.assertNotIn("matrixreferences", self.old)

    def test_merges_nonconflicting_folders(self):
        record = object()
        self.old["matrixreferences"] = Folder(old=record)
        self.new["matrixreferences"] = Folder(new=object())
        setuphandlers.setup_matrixreferences(None)
        self.assertIs(self.new["matrixreferences"]["old"], record)
        self.assertEqual(len(self.new["matrixreferences"]), 2)
        self.assertNotIn("matrixreferences", self.old)

    def test_conflicting_ids_preserve_both_records(self):
        self.old["matrixreferences"] = Folder(same=object())
        self.new["matrixreferences"] = Folder(same=object())
        with self.assertRaises(ValueError):
            setuphandlers.setup_matrixreferences(None)
        self.assertEqual(self.moves, [])
        self.assertEqual(len(self.old["matrixreferences"]), 1)
        self.assertEqual(len(self.new["matrixreferences"]), 1)
