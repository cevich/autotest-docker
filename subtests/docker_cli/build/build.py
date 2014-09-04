"""
Test run of docker build command

1. Copy source files + static busybox to srcdir if necessary
2. Verify timeout isn't too short
3. Start build in srcdir
4. Check build exit code, make sure image exists
5. Optionally remove built image
"""

import os.path
import shutil
import time
from urllib2 import urlopen
from dockertest import subtest
from dockertest.images import DockerImages
from dockertest.containers import DockerContainers
from dockertest.output import OutputGood
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.dockercmd import DockerCmd
from dockertest.dockercmd import NoFailDockerCmd
from dockertest.xceptions import DockerTestNAError


class NotSeenString(object):

    """
    Represent the next line of a string not already returned previously
    """

    #: Callable returning string
    source = None

    #: Passed through to source if callable
    args = None

    #: Passed through to source if callable
    dargs = None

    #: Current End line & Start line next time
    end = 0

    #: Private cache of next available string
    _cache = None

    def __init__(self, source, *args, **dargs):
        r"""
        Initialize new instance checking on source property or callable

        :param source: Callable returning a string
        :param \*args: Passed through to source if callable
        :param \*\*dargs: Passed through to source if callable
        """
        self.source = source
        self.args = args
        self.dargs = dargs
        self._cache = None

    def __str__(self):
        """
        Return next unseen line or empty-string
        """
        if self._cache is None:
            self.has_new_line()
        # Above could update _cache
        if self._cache is not None:
            result = self._cache
            self._cache = None
            return result
        else:
            return ''

    def has_new_line(self):
        """
        Return True if an unseen line is available
        """
        if self._cache is not None:
            return True
        if callable(self.source):
            newvalue = self.source(*self.args, **self.dargs)
        else:
            newvalue = self.source
        lines = newvalue.splitlines()
        if len(lines) > self.end:
            del lines[0:self.end]
            self.end += 1
        else:
            return None  # no new lines
        result = lines[0]
        stripped = result.strip()
        if len(stripped) > 0:
            self._cache = result.rstrip()  # only remove trailing whitespace
            return True
        else:
            return False  # skip blank line


class build(subtest.SubSubtestCaller):

    """ Subtest caller """

    def setup(self):
        super(build, self).setup()
        for filename in self.config['source_files'].split(','):
            # bindir is location of this module
            src = os.path.join(self.bindir, filename)
            # srcdir is recreated if doesn't exist or if test version changes
            dst = os.path.join(self.srcdir, filename)
            shutil.copy(src, dst)
        # Must exist w/in directory holding Dockerfile
        urlstr = self.config['busybox_url'].strip()
        self.logdebug("Downloading busybox from %s", urlstr)
        resp = urlopen(urlstr, timeout=30)
        data = resp.read()
        busybox = os.open(os.path.join(self.srcdir, 'busybox'),
                          os.O_WRONLY | os.O_CREAT, 0755)
        os.write(busybox, data)
        os.close(busybox)


class build_base(subtest.SubSubtest):

    """
    Base of build test
    1. Import empty_base_image (widely used in this test)
    2. Run docker build ... $dockerfile_path (by default self.srcdir)
    3. Verify the image was built successfully
    """

    def initialize(self):
        super(build_base, self).initialize()
        condition = self.config['build_timeout_seconds'] >= 10
        self.failif(not condition, "Config option build_timeout_seconds "
                                   "is probably too short")
        self.sub_stuff['di'] = dimg = DockerImages(self)
        img_name_tag = dimg.get_unique_name(self.config['image_name_prefix'],
                                            self.config['image_name_postfix'])
        image_name, image_tag = img_name_tag.split(':', 1)
        self.sub_stuff['image_name_tag'] = img_name_tag
        self.sub_stuff['image_name'] = image_name
        self.sub_stuff['image_tag'] = image_tag
        srcdir = self.parent_subtest.srcdir
        self.sub_stuff['dockerfile_path'] = self.config.get('dockerfile_path',
                                                            srcdir)
        dockerfile_path = self.sub_stuff['dockerfile_path']
        if len(dockerfile_path) < 3:
            raise DockerTestNAError('Invalid dockerfile_path "%s"'
                                    % dockerfile_path)
        # Must build from a base-image, import an empty one
        tarball = open(os.path.join(self.parent_subtest.bindir,
                                    'empty_base_image.tar'), 'rb')
        dkrcmd = NoFailDockerCmd(self, 'import', ["-", "empty_base_image"])
        dkrcmd.execute(stdin=tarball)

    def run_once(self):
        super(build_base, self).run_once()
        subargs = [self.config['docker_build_options'],
                   "-t", self.sub_stuff['image_name_tag'],
                   self.sub_stuff['dockerfile_path']]
        # Don't really need async here, just exercizing class
        dkrcmd = AsyncDockerCmd(self, 'build', subargs,
                                self.config['build_timeout_seconds'],
                                verbose=True)
        dkrcmd.execute()
        nss = NotSeenString(getattr, dkrcmd, 'stdout')
        while not dkrcmd.done:
            if nss.has_new_line():
                self.loginfo("Building: %s" % nss)
            else:
                time.sleep(3)
        self.sub_stuff["cmdresult"] = dkrcmd.wait()

    def postprocess(self):
        super(build_base, self).postprocess()
        # Raise exception if problems found
        OutputGood(self.sub_stuff['cmdresult'])
        self.failif(self.sub_stuff['cmdresult'].exit_status != 0,
                    "Non-zero build exit status: %s"
                    % self.sub_stuff['cmdresult'])
        image_name = self.sub_stuff['image_name']
        image_tag = self.sub_stuff['image_tag']
        dimg = self.sub_stuff['di']
        imgs = dimg.list_imgs_with_full_name_components(repo=image_name,
                                                        tag=image_tag)
        self.failif(len(imgs) < 1, "Test image build result was not found")
        self.sub_stuff['image_id'] = imgs[0].long_id  # use the first one
        self.failif(self.sub_stuff['image_id'] is None,
                    "Failed to look up image ID from build")
        self.loginfo("Found image: %s", imgs[0].full_name)

    def cleanup(self):
        super(build_base, self).cleanup()
        # Auto-converts "yes/no" to a boolean
        if self.config['try_remove_after_test']:
            for cid in DockerContainers(self).list_container_ids():
                dcmd = DockerCmd(self, 'rm', ['--force', '--volumes', cid])
                dcmd.execute()
            dimg = self.sub_stuff['di']
            if self.sub_stuff.get('image_id') is not None:
                dimg.remove_image_by_id(self.sub_stuff['image_id'])
            dimg.remove_image_by_full_name("empty_base_image")
            self.loginfo("Successfully removed test images")
        else:
            self.loginfo("NOT removing image")


class local_path(build_base):

    """
    Path to a local directory within the Dockerfile and other files are present
    """
    pass


class https_file(build_base):

    """ https path to a Dockerfile """
    pass


class git_path(build_base):

    """ path to a git reporistory which contains Dokerfile and othe files """
    pass
