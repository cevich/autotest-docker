r"""
Summary
---------

Verify running systemd as ENTRYPOINT in container.

Operational Summary
----------------------

#. Execute bundled test.sh script to perform label checking operations.
#. Fail subtest if script returns non-zero.

Prerequisites
---------------

Commands contained w/in test script are available/functional on system.
Specifically docker 1.12 is needed for dockerd and containerd.
"""

from os.path import join
from autotest.client.utils import run
from dockertest.config import get_as_list
from dockertest import subtest
from dockertest.config import Config
from dockertest.images import DockerImages
from dockertest.output.validate import mustpass
from dockertest.output.dockerversion import DockerVersion


class systemd_in_container(subtest.Subtest):

    # Execute this many times, with #0 being the default test image
    iterations = 1

    def initialize(self):
        # See Prerequisites (above)
        DockerVersion().require_server("1.12")
        self.stuff['result'] = None
        self.stuff['di'] = DockerImages(self)
        self.stuff['fqins'] = [self.stuff['di'].default_image]
        if self.iterations > 1:
             self.stuff['fqins'] += get_as_list(config.get('fqins_to_test',''))
        super(systemd_in_container, self).initialize()

    def run_once(self):
        super(systemd_in_container, self).run_once()
        # First item is always the default test image, counting starts at 1
        fqin = self.stuff['fqins'][self.iteration - 1]

        # Assumes script exits non-zero on test-failure and
        # cleans up any/all containers/images it created
        result = run("%s %s"
                     % (join(self.bindir, 'test.sh'),
                        fqin),
                     ignore_status=True)
        self.logdebug(str(result))
        self.stuff['result'] = result

    def postprocess_iteration(self):
        super(systemd_in_container, self).postprocess_iteration()
        mustpass(self.stuff['result'])

# A little bit of magic to configure the class when fqins_to_test is set
config = Config()['docker_cli/systemd_in_container']
fqins_to_test = get_as_list(config.get('fqins_to_test',''))
if fqins_to_test:
    systemd_in_container.fqins_to_test
    systemd_in_container.iterations = len(fqins_to_test) + 1  # default image
