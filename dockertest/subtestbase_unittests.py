#!/usr/bin/env python

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import os
import sys
from tempfile import mkstemp, TemporaryFile
import types
from unittest2 import TestCase, main


###############################################################################
# BEGIN boilerplate crap needed for subtests, which should be refactored

# DO NOT allow this function to get loose in the wild!
def mock(mod_path):
    """
    Recursivly inject tree of mocked modules from entire mod_path
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


class DockerTestFail(Exception):

    """ Fake class for errors """
    pass

# Mock module and exception class in one stroke
setattr(mock('xceptions'), 'DockerTestFail', DockerTestFail)
setattr(mock('xceptions'), 'DockerTestNAError', DockerTestFail)

# END   boilerplate crap needed for subtests, which should be refactored
###############################################################################


class SubtestBaseTestBase(TestCase):
    """Common setup/teardown base class for other fixtures here"""

    def setUp(self):
        super(SubtestBaseTestBase, self).setUp()
        import subtestbase
        self.subtestbase = subtestbase

        # Saves some typing
        self.stbsb = self.subtestbase.SubBase


class TestNotRedHat(SubtestBaseTestBase):

    def setUp(self):
        super(TestNotRedHat, self).setUp()
        pfx = 'subtestbase_unitest'
        (fd,
         self.stbsb.redhat_release_filepath) = mkstemp(prefix=pfx)
        os.close(fd)

    def tearDown(self):
        os.unlink(self.stbsb.redhat_release_filepath)

    def test_failif_not_redhat(self):
        with open(self.stbsb.redhat_release_filepath, 'wb') as rhrel:
            rhrel.write('this is not a red hat system')
        self.assertRaises(DockerTestFail, self.stbsb.failif_not_redhat,
                          DockerTestFail)

    def test_failif_redhat(self):
        with open(self.stbsb.redhat_release_filepath, 'wb') as rhrel:
            rhrel.write('Red Hat Enterprise Linux Atomic Host release 7.2')
        self.assertEqual(self.stbsb.failif_not_redhat(DockerTestFail), None)


class TestFailIfNotIn(SubtestBaseTestBase):
    """
    Tests for failif_not_in()
    """

    # In each of these, the left-hand string(s) will be present at right.
    expect_pass = [
        ['a',        'a'],
        ['a',        'aa'],
        ['a',        'abc'],
        ['a',        'cba'],
        ['a|a',      'a'],
        ['a | a',    'a'],
        ['string',   'ceci nest pas une string'],
        ['no|yes',   'googlyeyes'],
        ['no | yes', 'googlyeyes'],
        ['needle',   'needle in a haystack'],
        ['needle',   'haystack with a needle in the middle'],
        ['needle',   'haystack with, at end, a needle'],
    ]

    # The left-hand string(s) will NOT be in the right
    expect_fail = [
        ['a',         'b'],
        ['needle',    'haystack'],
        ['a|b|c',     'd'],
        ['a | b | c', 'd'],
        ['a | a | a', 'b'],
    ]

    def test_pass(self):
        for needle, haystack in self.expect_pass:
            # Automaticly shows needle & haystack in any failure message
            with self.subTest(needle=needle, haystack=haystack):
                result = self.stbsb.failif_not_in(needle, haystack)
                self.assertIsNone(result)

    def test_fail(self):
        for needle, haystack in self.expect_fail:
            with self.subTest(needle=needle, haystack=haystack):
                self.assertRaises(DockerTestFail,
                                  self.stbsb.failif_not_in,
                                  needle, haystack)


class TestKnownFailures(SubtestBaseTestBase):
    """Tests known_failures() and SubBase.is_known_failure()"""

    def setUp(self):
        super(TestKnownFailures, self).setUp()
        self.tmpfile = None
        self.fake_open = lambda *args, **dargs: self.tmpfile
        self.subtestbase.open = self.fake_open

        self.docker_rpm = 'docker'
        self.subtestbase.docker_rpm = lambda: self.docker_rpm

    def tearDown(self):
        # Don't let mocks or state leak anywhere
        del self.subtestbase.open
        del self.subtestbase.docker_rpm  
        del self.subtestbase
        super(SubtestBaseTestBase, self).tearDown()

    def reset_tmpfile(self, contents=None):
        self.tmpfile = TemporaryFile()
        if contents:
            self.tmpfile.write(contents)
            self.tmpfile.seek(0,0)

    def test_empty_known_failures(self):
        self.reset_tmpfile()
        known = self.subtestbase.known_failures()
        self.assertEqual(known, {})

    def test_known_failures(self):
        self.reset_tmpfile('"one","two","three"\n')
        known = self.subtestbase.known_failures()
        self.assertIn('two', known)
        self.assertEqual(known['two'], {'one': 'three'})


if __name__ == '__main__':
    main()
