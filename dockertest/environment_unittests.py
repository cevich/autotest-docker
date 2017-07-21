#!/usr/bin/env python

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import unittest

class FakeCheckOutput(object):

    exception = None
    callcount = 0
    command = None
    name = None
    version = '1.0'
    release = 'a'
    arch = '8088'
    output_fmt = '%s#%s#%s#%s\n'
    allnvras = (('one', 2, 3, 4),
                ('five', '6', '7', '8'),
                ('a', 'b', 'c', 'd'))

    def __call__(self, command, *args, **dargs):
        del args  # don't care
        del dargs  # also don't care
        self.callcount += 1
        self.command = command
        # Don't modify the input container value
        self.name = list(command).pop()
        if self.exception:
            was = self.exception
            self.exception = None
            raise was("Raised by FakeCheckOutput")
        if self.name in ['-a', '--all']:
            return ''.join([self.output_fmt % nvra for nvra in self.allnvras])
        return self.output_fmt % (self.name, self.version,
                                  self.release, self.arch)

    def reset(self):
        self.exception = None
        self.callcount = 0
        self.command = None
        self.name = None


class TestRPMS(unittest.TestCase):

    def setUp(self):
        from dockertest import environment
        self.environment = environment
        self.fakecheckoutput = FakeCheckOutput()
        self.fakecheckoutput.reset()
        self.environment.RPMS.flush()
        self.original_execute = self.environment.RPMS.execute
        self.environment.RPMS.execute = staticmethod(self.fakecheckoutput)

    def teardown(self):
        self.fakecheckoutput.reset()
        self.environment.RPMS.flush()
        self.environment.RPMS.execute = self.original_execute

    def test_init(self):
        self.environment.RPMS()
        self.assertEqual(self.fakecheckoutput.callcount, 0)

    def test_existing(self):
        original_type = self.environment.RPMS.nvra_type
        try:
            self.environment.RPMS.nvra_type = staticmethod(str)
            initializer = dict(foo=('bar',), baz=('foo',))
            expected = dict(foo=str(*initializer['foo']), baz=str(*initializer['baz']))
            actual = self.environment.RPMS(**initializer)
            for key in ('foo', 'baz'):
                self.assertEqual(expected[key], actual[key])
            self.assertEqual(self.fakecheckoutput.callcount, 0)
        finally:
            self.environment.RPMS.nvra_type = original_type

    def test_callout(self):
        original_type = self.environment.RPMS.nvra_type
        try:
            self.environment.RPMS.nvra_type = staticmethod(lambda *args: tuple(args))
            rpms = self.environment.RPMS()
            sfco = self.fakecheckoutput
            self.assertEqual(rpms['foobar'], (sfco.name, sfco.version, sfco.release, sfco.arch))
            self.assertEqual(sfco.callcount, 1)
            # Make sure cache is utilized
            self.assertEqual(rpms['foobar'], (sfco.name, sfco.version, sfco.release, sfco.arch))
            self.assertEqual(sfco.callcount, 1)
        finally:
            self.environment.RPMS.nvra_type = original_type

    def test_callout_badfmt(self):
        original_type = self.environment.RPMS.nvra_type
        self.fakecheckoutput.output_fmt = '%s,%s,%s,%s\n'
        try:
            self.environment.RPMS.nvra_type = staticmethod(lambda *args: tuple(args))
            rpms = self.environment.RPMS()
            sfco = self.fakecheckoutput
            self.assertEqual(sfco.callcount, 0)
            self.assertRaises(ValueError, rpms.__getitem__, 'foobar')
        finally:
            self.environment.RPMS.nvra_type = original_type

    def test_all(self):
        original_type = self.environment.RPMS.nvra_type
        try:
            self.environment.RPMS.nvra_type = staticmethod(lambda *args: tuple(args))
            expected = dict([(str(nvra[0]),
                              tuple([str(x) for x in nvra]))
                             for nvra in self.fakecheckoutput.allnvras])
            rpms = self.environment.RPMS()
            self.assertEqual(len(rpms), 3)
            for key in expected.keys():
                self.assertTrue(key in rpms)
                self.assertEqual(expected[key], rpms[key])
            self.assertEqual(self.fakecheckoutput.callcount, 1)
            self.assertEqual(rpms['foobar'], ('foobar', '1.0', 'a', '8088'))
        finally:
            self.environment.RPMS.nvra_type = original_type


if __name__ == '__main__':
    unittest.main()
