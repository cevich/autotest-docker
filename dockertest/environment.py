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


class CanonicalDistro(str):

    """
    Represents a canonical/standardized name for the OS distribution

    :param object: Optional, same as ``str()`` built in.  If non-empty,
                   take ``str(object`` as the definitive distro. name,
                   bypassing automatic detection.
    """

    #: Ordered list of class-method names to use for distro-detection.
    #: Each takes a dictionary representing the current detection state
    #: (See as ``matches`` below), and is expected to return
    #: a string representing the detected distro. name, None, or ''.
    distros = ("fedora", "rhel", "centos")

    #: Mapping of distro names to lower-case distro-method result strings
    #: if auto-detection was used (i.e. no initialization arguments passed)
    matches = None

    def __new__(cls, *args, **dargs):
        _object = cls._handle_object(*args, **dargs)
        if _object:
            return super(CanonicalDistro, cls).__new__(cls, str(_object).lower())
        else:
            _matches = cls.investigate()
            distro_matches = set(_matches.values())
            if len(distro_matches) > 1:
                raise ValueError("Multiple distros detected: %s" % _matches)
            elif len(distro_matches) != 1:
                raise ValueError("No distros detected: %s" % _matches)

            # immutables can't rely on __init__(), it must be done here
            new_cd = super(CanonicalDistro, cls).__new__(cls, distro_matches.pop())
            new_cd.matches = _matches  # __init__ can't handle this
            return new_cd

    @classmethod
    def _handle_object(cls, *args, **dargs):
        # Sigh, the str() builtin really does use a parameter named 'object' :_(
        # Deal with this here, so __new__ only needs to worry about
        # an optional string initialization parameter.
        if len(args) > 1 or len(dargs) > 1:
            raise TypeError("__init__() takes at most 1 argument (%d given)"
                            % (len(args) + len(dargs)))
        elif len(dargs) == 1:
            if 'object' in dargs:
                _object = dargs['object']
            else:
                raise TypeError("__init__() got unexpected keyword argument %s"
                                % dargs.popitem()[0])
        elif len(args) == 1:
            _object = args[0]
        else:
            _object = ''  # default
        return _object

    @classmethod
    def investigate(cls):
        """
        Return mapping of distro names to distro class-method results.
        """
        _matches = {}
        for distro in cls.distros:
            distro_match = getattr(cls, distro)
            match = str(distro_match(_matches.copy())).lower()
            if match in ('', 'none'):
                continue
            _matches[distro] = match
        return _matches

    # Method names must exactly match the cls.distros list.
    # Called in order defined by cls.distros list.
    # Use/Modification of ``matches`` argument is optional.
    # Each must return a string, that will update ``matches`` for that distro.

    @staticmethod
    def fedora(matches):
        del matches  # Optional, not used here
        return None

    @staticmethod
    def rhel(matches):
        del matches  # Optional, not used here
        return None

    @staticmethod
    def centos(matches):
        del matches  # Optional, not used here
        return None

    # General instance helper/convenience methods

    def is_atomic(self):
        """STUB"""
        return 'atomic' in self

    def is_enterprise(self):
        """STUB"""
        return 'rhel' in self or 'centos' in self


class RDFilter(Mapping):

    """
    Filter-map storage type for RPM NVRAs and CanonicalDistro strings

    :param args: Same meaning as for ``dict()``
    :param dargs: Same meaning as for ``dict()``
    """

    # Internal storage, do not use
    _mapping = None

    #: Class required for nvra keys, expected to be compatible
    #: with the RPM class.  If all fields are "", only
    #: a distro. match will be considered.
    nvra_type = RPMs.nvra_type

    #: Set of acceptable distro-list values.  Where
    #: ``None`` value matches the nvra key on any distro.
    acceptable_distros = set(CanonicalDistro.distros) + set([None])

    def __new__(cls, *args, **dargs):
        if args or dargs:
            argtest = dict(*args, **dargs)
            for nvra, distros in argtest.iteritems():
                if not isinstance(nvra, cls.nvra_type)
                    raise ValueError("Initializer key '%s' is not a"
                                     " '%s' or subclass." % (nvra, cls.nvra_type))
                for distro in distros:
                    if distro not in cls.acceptable_distros:
                        raise ValueError("Initializer key '%s' value '%s', is"
                                         " not in '%s'."
                                         % (nvra, distro, cls.acceptable_values))
        return super(Mapping, cls).__new__(*args, **dargs)

    def __init__(self, *args, **dargs):
        # N/B: Instances are immutable!
        self._mapping = dict(*args, **dargs)

    # Simply query internal storage to fill out ABC requirements
    __getitem__ = lambda self, key: self._mapping.__getitem__(key)
    __iter__ = lambda self: self._mapping.__iter__()
    __len__ = lambda self: self._mapping.__len__()
    __contains__ = lambda self, key: self._mapping.__contains__(key)

    @classmethod
    def from_csv(cls, nvra_distro_csv, nvra_delim=';', sub_delim='#'):
        """
        Return a new instance produced by parsing rpm_distro_csv.

        :param nvra_distro_csv: A CSV list of ``delimiter`` separated key/value
                                pairs.  Keys must be acceptable ``cls.nvra_type``
                                initializers.  Values must be in
                                ``cls.acceptable_values``.
        # FIXME: More docs  (delims must never be valid distro or rpm names)
        """
        # count ; in "name;version;release;arch" the most complicated way possible
        n_nvra_delim = len(cls.nvra_type._fields) -1
        # Prune empty values and values w/o required delimiters
        is_valid = lambda val: (val.strip() and
                                val.find(nvra_delim) == n_nvra_delim and
                                val.find(sub_delim) == 1)
        # Dict-like's can be initialized from lists of key,value tuples
        nvra_distros = [sub_val.split(delimiter, 1)
                        for sub_val in [val.strip()
                                        for val in rpm_distro_csv.split(',')
                                        if is_valid(val)]]
        # Catch eval() exceptions here instead of in __new__
        try:
            # Given nt = cls.nvra_type
            #
            # from_csv("foobar;42;;#fedora,baz;;;#rhel,;;;i386")
            #
            # returns
            #
            # [(nt('foobar', '42', '', ''), 'fedora'),
            #  (nt('baz', '', '', ''), 'rhel'),
            #  (nt('','','',''), 'i386')]
            #
            args = [(eval('cls.nvra_type(*%s)' % k.split(nvra_delim, n_nvra_delim)), str(v))
                    for k, v in nvra_distros]
        except TypeError:
            raise TypeError("Error instantiating %s(%s): %s"
                            % (cls.nvra_type))  # FIXME: finish this
        # __new__ does final value validation
        return cls(*args)

    def fail_if_nvra_or_distro(self, extra_msg='', exception=RuntimeError):
        """
        Raise exception on distro and/or rpm nvra match w/ details + extra_msg
        """
        # Walk self.iteritems(), toss exception if match found
        pass # STUB
