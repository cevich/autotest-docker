#!/usr/bin/env python

"""
Low-level/standalone host-environment handling/checking utilities/classes/data
"""

import warnings
import subprocess
import selinux


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
