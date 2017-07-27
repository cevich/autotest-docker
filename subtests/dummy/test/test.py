r"""
Summary
---------

Textual description of *what* this subtest will exercize in general terms.
The next section describes the steps it will take.  The ``Operational Detail``
is optional, as is ``Prerequisites``.

Operational Summary
----------------------

#. Summary of step one
#. Summary of step two
#. Summary of step three

Operational Detail
--------------------

Example shell-based example test, nothing detailed about it.

Prerequisites
---------------

This shell-based example test does not require anything other than
Autotest, Docker autotest, this file and three shell-shell scripts.
"""

from dockertest.subtest import BashSubtest

class test(BashSubtest):
    """
    Call out to ``initialize.sh``, ``run.sh`` and ``cleanup.sh``.

    Any non-zero exit (except from cleanup) will result in test failure.
    The ``cleanup.sh`` script always runs, no matter what.
    """
