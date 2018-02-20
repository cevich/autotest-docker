"""
Handlers for docker version parsing
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import re
import subprocess
from autotest.client import utils
from dockertest.xceptions import DockerOutputError, DockerTestNAError
from dockertest.version import LooseVersion


class DockerVersion(object):

    """
    Parser of docker-cli version command output as client/server properties

    :**N/B**: Neither class nor instances are thread-safe.
    :param version_string: Raw, possibly empty or multi-line output
                           from docker version command.
    """

    #: Raw, possibly empty or multi-line output from docker version command.
    #: Read-only, set in __init__
    version_string = None

    #: Various cache's for properties (private)
    _cache = None

    def __new__(cls, version_string=None, docker_path=None):
        del version_string  # not used
        del docker_path
        if not cls._cache:
            cls._cache = dict(
                client=None,
                server=None,
                client_lines=None,
                server_lines=None,
                client_info=None,
                server_info=None,
                has_distinct_exit_codes=None)
        return super(cls, DockerVersion).__new__(cls)

    def __init__(self, version_string=None, docker_path=None):
        # If called without an explicit version string, run docker to find out
        if version_string is None:
            if docker_path is None:
                docker_path = 'docker'
            version_string = subprocess.check_output(docker_path + ' version',
                                                     shell=True,
                                                     close_fds=True)
        self.version_string = version_string
        super(DockerVersion, self).__init__()

    @classmethod
    def flush_cache(cls):
        """
        Wipe out any existing cached data for all instances
        """
        cls._cache = None

    def _oops(self, what):
        raise DockerOutputError("Couldn't parse %s from %s" %
                                (what, self.version_string))

    # This is old code, not updating to preserve old behavior
    def _old_client(self):
        if self._cache['client'] is None:
            regex = re.compile(r'Client\s+version:\s+(\d+\.\d+\.\d+\S*)',
                               re.IGNORECASE)
            mobj = None
            for line in self.version_lines:
                mobj = regex.search(line.strip())
                if bool(mobj):
                    self._cache['client'] = mobj.group(1)
        if self._cache['client'] is None:
            self._oops('client version')
        return self._cache['client']

    # This is old code, not updating to preserve old behavior
    def _old_server(self):
        if self._cache['server'] is None:
            regex = re.compile(r'Server\s*version:\s*(\d+\.\d+\.\d+\S*)',
                               re.IGNORECASE)
            mobj = None
            for line in self.version_lines:
                mobj = regex.search(line.strip())
                if bool(mobj):
                    self._cache['server'] = mobj.group(1)
        if self._cache['server'] is None:
            self._oops('server version')
        return self._cache['server']

    def _split_client_server(self):
        # Split the raw string into client & server sections
        client_lines = []
        server_lines = []
        version_lines = list(self.version_lines)  # work on a copy
        version_lines.reverse()  # start at beginning
        while version_lines:
            version_line = version_lines.pop().strip()
            if version_line == '':
                continue
            elif version_line.find('Client:') > -1:
                # Don't assume which section came first
                while version_lines and version_lines[-1].find('Server:') < 0:
                    version_line = version_lines.pop().strip()
                    if version_line == '':
                        continue
                    client_lines.append(version_line)
                continue
            elif version_line.find('Server:') > -1:
                # Don't assume which section came first
                while version_lines and version_lines[-1].find('Client:') < 0:
                    version_line = version_lines.pop().strip()
                    if version_line == '':
                        continue
                    server_lines.append(version_line)
                continue
            else:
                msg = ("Unexpected line '%s' in version string: '%s'"
                       % (version_line, self.version_string))
                raise DockerOutputError(msg)
        return (client_lines, server_lines)

    # This is to preserve API behavior for old tests
    @property
    def version_lines(self):
        """Read-only property that returns all lines in version table"""
        return self.version_string.splitlines()

    def _lines(self, which):
        if not self._cache[which]:
            (self._cache['client_lines'],
             self._cache['server_lines']) = self._split_client_server()
        return self._cache[which]

    @property
    def client_lines(self):
        """
        Read-only property of split/stripped client section of version string
        """
        return self._lines('client_lines')

    @property
    def server_lines(self):
        """
        Read-only property of split/stripped server section of version string
        """
        return self._lines('server_lines')

    def _info(self, is_client, key):
        key = key.strip()
        if is_client:
            infodict = self._cache['client_info']
            infolines = self.client_lines
        else:
            infodict = self._cache['server_info']
            infolines = self.server_lines
        try:
            return infodict[key.strip().lower()]
        except TypeError:  # infodict == None
            if is_client:
                self._cache['client_info'] = {}
            else:
                self._cache['server_info'] = {}
            return self._info(is_client, key)
        except KeyError:  # infodict == empty
            if not infodict:
                for line in infolines:
                    try:
                        _key, value = line.strip().lower().split(':', 1)
                    except ValueError:
                        raise ValueError("Error splitting info line '%s'"
                                         % line)
                    infodict[_key.strip()] = value.strip()
                return self._info(is_client, key)
            else:  # avoid infinite recursion
                self._oops("key %s" % key)

    def client_info(self, key):
        """Return item named 'key' from client section of version info table"""
        return self._info(True, key)

    def server_info(self, key):
        """Return item named 'key' from server section of version info table"""
        return self._info(False, key)

    def _version(self, which):
        if self._cache[which] is None:
            try:
                meth = getattr(self, '_old_%s' % which)
                self._cache[which] = meth()
            except DockerOutputError:
                meth = getattr(self, "%s_info" % which)
                self._cache[which] = meth('version')
        if self._cache[which] is None:
            self._oops('%s version' % which)
        return self._cache[which]

    @property
    def client(self):
        """
        Read-only property representing version-number string of docker client
        """
        return self._version('client')

    @property
    def server(self):
        """
        Read-only property representing version-number string of docker server
        """
        return self._version('server')

    @staticmethod
    def _require(wanted, name, other_version):
        required_version = LooseVersion(wanted)
        if other_version < required_version:
            msg = ("Test requires docker %s version >= %s; %s found"
                   % (name, required_version, other_version))
            raise DockerTestNAError(msg)
        # In case it's useful to caller
        return other_version

    def require_server(self, wanted):
        """
        Run 'docker version', parse server version, compare to wanted.

        :param wanted: required docker (possibly remote) server version
        :raises DockerTestNAError: installed docker < wanted
        """
        return self._require(wanted, 'server', self.server)

    def require_client(self, wanted):
        """
        Run 'docker version', parse client version, compare to wanted.

        :param wanted: required docker client version
        :raises DockerTestNAError: installed docker < wanted
        """
        return self._require(wanted, 'client', self.client)

    @property
    def has_distinct_exit_codes(self):
        """
        2016-03-23 **TEMPORARY** - for transition from docker-1.9 to 1.10

        docker-1.10 will introduce distinct exit codes to allow differentiating
        between container status and errors from docker run itself; see
        bz1097344 and docker PR14012. If we see an exit code of 125 here,
        assume we're using the new docker.
        """
        if self._cache['has_distinct_exit_codes'] is None:
            try:
                # docker-1.10 *must* support distinct exit codes
                self.require_client('1.10')
                has = True
            except DockerTestNAError:
                # some builds of 1.9 might support it. (FIXME: really?)
                d_run = utils.run('docker run --invalid-opt invalid-image',
                                  ignore_status=True)
                has = (d_run.exit_status > 120)
            self._cache['has_distinct_exit_codes'] = has
        return self._cache['has_distinct_exit_codes']
