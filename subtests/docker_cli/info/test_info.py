# -*- python -*-
#
# Tests for the docker-autotest 'info' subtest
#
# As of 2016-02-12 this only includes verify_pool_name(); we'll try to
# extend coverage as needed.
#
# RUNNING: see run_unittests.sh in the top level of docker-autotest
#
from unittest2 import TestCase, main        # pylint: disable=unused-import
from mock import Mock, patch
import autotest  # pylint: disable=unused-import
import info


class TestVerifyPoolName(TestCase):
    # Standard docker pool name to expect
    docker_pool = 'rhel-docker--pool'

    # Typical output from 'dmsetup ls'. Note that order is arbitrary.
    dmsetup_ls = ['rhel-docker--pool	(253:4)',
                  'rhel-swap	(253:1)',
                  'rhel-root	(253:0)',
                  'rhel-docker--pool_tdata	(253:3)',
                  'rhel-docker--pool_tmeta	(253:2)']

    @staticmethod
    def failif(cond, msg):
        if cond:
            raise ValueError(msg)

    def _run_one_test(self, pool_name, dmsetup_output, expected_exception):
        """
        Helper for running an individual test. Creates a set of mocks
        that mimic the behavior we test for but are otherwise NOPs.
        """
        mockinfo = Mock(spec=info.info)
        mockinfo.failif = self.failif
        mockrun = Mock()
        mockrun.stdout = ''.join([line + "\n" for line in dmsetup_output])

        raised = False
        with patch('autotest.client.utils.run', Mock(return_value=mockrun)):
            try:
                info.info.verify_pool_name(mockinfo, pool_name)
            except Exception, e:          # pylint: disable=broad-except
                if expected_exception:
                    # exception message is a more specific check than type
                    self.assertEqual(e.message, expected_exception)
                    raised = True
                else:
                    self.fail("Unexpected exception %s" % e.message)
        if expected_exception and not raised:
            self.fail("Test did not raise expected exception")

    def test_standard_order(self):
        """Expected pool name is the first line of output"""
        self._run_one_test(self.docker_pool, self.dmsetup_ls, None)

    def test_reverse_order(self):
        """Expected pool name is the last line of output"""
        self._run_one_test(self.docker_pool,
                           reversed(self.dmsetup_ls), None)

    def test_empty_dmsetup(self):
        """dmsetup ls produces no output"""
        self._run_one_test(self.docker_pool, [],
                           "'dmsetup ls' reports no docker pools.")

    def test_dmsetup_with_no_pools(self):
        """dmsetup ls contains no lines with the string 'pool'."""
        incomplete = [x for x in self.dmsetup_ls if x.find("pool") < 0]
        self._run_one_test(self.docker_pool, incomplete,
                           "'dmsetup ls' reports no docker pools.")

    def test_pool_missing(self):
        """dmsetup ls contains many lines, but not our desired pool name."""
        incomplete = [x for x in self.dmsetup_ls
                      if not x.startswith(self.docker_pool + "\t")]
        self._run_one_test(self.docker_pool, incomplete,
                           "Docker info pool name 'rhel-docker--pool'"
                           " (from docker info) not found in dmsetup ls"
                           " list '['rhel-docker--pool_tdata',"
                           " 'rhel-docker--pool_tmeta']'")


class TestBuildTable(TestCase):

    def test_docker_info_parsing(self):
        # Typical output from docker info. The '%s' tests trailing whitespace
        docker_info = """Containers: 0
 Running: 0
 Paused: 0
 Stopped: 0
Images: 3
Server Version: 1.12.6
Storage Driver: devicemapper
 Pool Name: vg--docker-docker--pool
 Pool Blocksize: 524.3 kB
 Data file: %s
 Library Version: 1.02.135-RHEL7 (2016-11-16)
Logging Driver: journald
Plugins:
 Volume: local lvm
 Network: host null bridge overlay
ID: 5UCC:ANAG:4BIE:2KK6:VGP4:XKVO:5HB5:RPOA:PFLJ:HXRF:FCDV
Insecure Registries:
 127.0.0.0/8""" % ''
        actual = info.info._build_table(docker_info)  # pylint: disable=W0212

        # How we expect _build_table() to parse that.
        expect = {
            'Containers': '0',
            'Containers...': {
                'Running': '0',
                'Paused': '0',
                'Stopped': '0',
            },
            'Images': '3',
            'Server Version': '1.12.6',
            'Storage Driver': 'devicemapper',
            'Storage Driver...': {
                'Pool Name': 'vg--docker-docker--pool',
                'Pool Blocksize': '524.3 kB',
                'Data file': '',
                'Library Version': '1.02.135-RHEL7 (2016-11-16)',
            },
            'Logging Driver': 'journald',
            'Plugins': '',
            'Plugins...': {
                'Volume': 'local lvm',
                'Network': 'host null bridge overlay',
            },
            'ID': '5UCC:ANAG:4BIE:2KK6:VGP4:XKVO:5HB5:RPOA:PFLJ:HXRF:FCDV',
            'Insecure Registries': '',
            'Insecure Registries...': {
                '127.0.0.0/8': '',
            }
        }

        self.maxDiff = None
        self.assertEqual(actual, expect, "parsed output from docker info")

if __name__ == '__main__':
    main()
