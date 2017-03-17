#!/usr/bin/env python

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403
# There is magic requiring attributes defined outside the __init__
# pylint: disable=W0201

import os
import shutil
import sys
import tempfile
import types
from tempfile import TemporaryFile
import unittest2

# DO NOT allow this function to get loose in the wild!
def mock(mod_path):
    """
    Recursively inject tree of mocked modules from entire mod_path
    """
    name_list = mod_path.split('.')
    child_name = name_list.pop()
    child_mod = sys.modules.get(mod_path, types.ModuleType(child_name))
    if len(name_list) == 0:  # child_name is left-most basic module
        if child_name not in sys.modules:
            sys.modules[child_name] = child_mod
        return sys.modules[child_name]
    else:
        # New or existing child becomes parent
        recurse_path = ".".join(name_list)
        parent_mod = mock(recurse_path)
        if not hasattr(sys.modules[recurse_path], child_name):
            setattr(parent_mod, child_name, child_mod)
            # full-name also points at child module
            sys.modules[mod_path] = child_mod
        return sys.modules[mod_path]


def fake_check_output(args, *pargs, **dargs):
    del pargs  # not used/needed
    del dargs
    return ' '.join(args)


setattr(mock('subprocess'), 'check_output', fake_check_output)


class EnvironmentTests(unittest2.TestCase):

    def setUp(self):
        super(EnvironmentTests, self).setUp()
        import environment
        self.environment = environment
        self.tmpfile = None
        self.fake_open = lambda *args, **dargs: self.tmpfile
        self.environment.open = self.fake_open

    def tearDown(self):
        del self.environment  # Don't let fake_open leak anywhere else
        super(EnvironmentTests, self).tearDown()

    def test_which_docker_empty(self):
        expected = 'docker'
        self.tmpfile = TemporaryFile()
        actual = self.environment.which_docker()
        self.assertEqual(actual, expected)

    def test_which_docker_full(self):
        expected = "docker-latest"
        self.tmpfile = TemporaryFile()
        self.tmpfile.write(
                "\n"
                "#DOCKERBINARY=no\n"
                "     #     DOCKERBINARY=not it\n"
                "\n"
                "DOCKERBINARY = nor this\n"
                "\n\n\n"
                "DOCKERBINARY=overwritten\n"
                "DOCKERBINARY= by the next line\n"
                "DOCKERBINARY=%s" % expected)
        self.tmpfile.seek(0,0)
        actual = self.environment.which_docker()
        self.assertEqual(actual, expected)

    def test_docker_rpm(self):
        test_args = [('docker',''),
                     ('docker-latest','\n\n\nDOCKERBINARY=docker-latest')]
        for rpm_name, contents in test_args:
            with self.subTest(rpm_name=rpm_name,
                              contents=contents):
                self.tmpfile = TemporaryFile()
                self.tmpfile.write(contents)
                self.tmpfile.seek(0,0)
                self.assertIn(rpm_name, self.environment.docker_rpm())


if __name__ == '__main__':
    unittest2.main()
