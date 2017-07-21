#!/usr/bin/env python

"""
Low-level/standalone host-environment handling/checking utilities/classes/data

:Note: This module must _NOT_ depend on anything in dockertest package or
       in autotest!
"""

import warnings
import subprocess
from collections import Mapping
from collections import namedtuple
# N/B: This module is automaticly generated from libselinux, so the
# python docs are terrible.  The C library man(3) pages provided by
# the 'libselinux-devel' RPM package (or equivilent) are much better.
import selinux
from dockertest.docker_daemon import which_docker


def set_selinux_context(path=None, context=None, recursive=True, pwd=None):
    """
    When selinux is enabled it sets the context by chcon -t ...
    :param path: Relative/absolute path to file/directory to modify
    :param context: desired context (svirt_sandbox_file_t by default)
    :param recursive: set context recursively (-R)
    :param pwd: target path (deprecated, was first argument name)
    :raise OSError: In case of failure
    """
    # This is here to catch any callers using pwd as a keyword argument.
    # Moving it to the end of the list is safe because there only ever
    # was a single positional argument in this function (preserves API)
    if pwd is not None:
        warnings.warn("Use of the pwd argument is deprecated,"
                      " use path (first positional) instead",
                      DeprecationWarning)
        path = pwd
    # Catch callers that only use ketword arguments but fail to pass
    # either ``pwd`` or ``path``.
    if path is None:
        raise TypeError("The path argument is required")
    if context is None:
        context = "svirt_sandbox_file_t"
    if recursive:
        flags = 'R'
    else:
        flags = ''
    # changes context in case selinux is supported and is enabled
    _cmd = ("type -P selinuxenabled || exit 0 ; "
            "selinuxenabled || exit 0 ; "
            "chcon -%st %s %s" % (flags, context, path))
    # FIXME: Should use selinux.setfilecon()
    cmd = subprocess.Popen(_cmd, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, shell=True)
    if cmd.wait() != 0:
        raise OSError("Fail to set selinux context by '%s' (%s):\nSTDOUT:\n%s"
                      "\nSTDERR:\n%s" % (_cmd, cmd.poll(), cmd.stdout.read(),
                                         cmd.stderr.read()))


def get_selinux_context(path):
    """
    When selinux is enabled, return the context of ``path``
    :param path: Full or relative path to a file or directory
    :return: SELinux context as a string
    :raises IOError: As per usual.  Documented here as it's
    a behavior difference from ``set_selinux_context()``.
    """
    # First list item is null-terminated string length
    return selinux.getfilecon(path)[1]


def selinux_is_enforcing():
    """
    Return True if selinux is currently in enforcing mode.

    :raise ValueError: If there was an error from libselinux
    :rtype: bool
    """
    mode = selinux.security_getenforce()
    if mode not in [selinux.ENFORCING, selinux.PERMISSIVE]:
        raise ValueError("Unexpected value from"
                         " security_getenforce(): %s" % mode)
    return mode == selinux.ENFORCING


def docker_rpm():
    """
    Returns the full NVRA of the currently-installed docker or docker-latest.

    FIXME: this won't work for container-engine. That's tricky, and
    not high priority, so let's save it for a subsequent PR.
    """
    cmd = "rpm -q %s" % which_docker()
    return subprocess.check_output(cmd, shell=True).strip()


class RPMS(Mapping):
    """
    Read-only mapping of rpm names to ``nvra_type`` instances

    :param args: Same as standard ``dict()`` positional arguments.
    :param dargs: Same as standard ``dict()`` keyword arguments.
    """

    #: Class to use for representing nvra values, the first index
    #: must be the package name.
    nvra_type = namedtuple('nvra_type',
                           ('name', 'version', 'release', 'arch'))
    nvra_len = len(nvra_type._fields)

    #: Query command to use for looking up a package NVRA must
    #: return line-delimited items of hash-delimited fields
    #: suitable for initializing ``nvra_type``.
    rpmcmd = ("/usr/bin/rpm", "-q", "--qf", '%{N}#%{V}#%{R}#%{ARCH}\n')

    #: Callable to use for executing rpmcmd
    execute = staticmethod(subprocess.check_output)

    #: Private, do not use
    _cache = None
    _alldone = None

    def __new__(cls, *args, **dargs):
        del args, dargs  # not used
        if cls._cache is None:
            cls.flush()
        return object.__new__(cls)

    def __init__(self, *args, **dargs):
        # Support dict API
        if not self._cache and (args or dargs):
            argtest = dict(*args, **dargs)
            for key, value in argtest.iteritems():
                try:
                    self._cache[key] = self.nvra_type(*value)
                except TypeError:
                    raise TypeError("Initializer key %s's value %s"
                                    " incompatible with %s"
                                    % (key, value, self.nvra_type))

    @classmethod
    def _store(cls, name):
        cmd = list(cls.rpmcmd) + [name]
        xcept_fmt = ("%s did not return expected line-delimited"
                     " items of hash-delimited fields as"
                     " output: %s")
        output = cls.execute(cmd)
        for value in output.strip().splitlines():
            # Use a field-delimiter incompatible with any field value
            new_nvra = cls.nvra_type(*value.strip().split('#'))
            if len(new_nvra) != cls.nvra_len:
                raise ValueError(xcept_fmt % (' '.join(cmd), output))
            new_name = new_nvra[0]  # documented in class attr. defs. above
            cls._cache[new_name] = new_nvra

    @classmethod
    def __getitem__(cls, key):
        # Don't allow passing arguments to query directly
        if not key.startswith('-') and key not in cls._cache:
            cls._store(key)
        return cls._cache[key]

    @classmethod
    def fill(cls, method_name=None):
        """
        Query and cache details from all packages

        :param method_name: Optional, return cache method with this name
        """
        if not cls._alldone:
            cls._store('-a')  # This is going to take a long while
            cls._alldone = True
        if method_name:
            return getattr(cls._cache, method_name)

    # All of these require a full query
    __iter__ = classmethod(lambda cls: cls.fill('__iter__')())
    __len__ = classmethod(lambda cls: cls.fill('__len__')())
    __contains__ = classmethod(lambda cls, item:
                               cls.fill('__contains__')(item))

    @classmethod
    def flush(cls):
        """Flush cache of RPM NVRAs to force fresh queries on access"""
        cls._cache = dict()
        cls._alldone = False
