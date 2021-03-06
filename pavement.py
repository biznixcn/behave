# ============================================================================
# PAVER MAKEFILE (pavement.py) -- behave
# ============================================================================
# REQUIRES: paver >= 1.2
# DESCRIPTION:
#   Provides platform-neutral "Makefile" for simple, project-specific tasks.
#   AVOID: setup support, because it is currently handled elsewhere.
#
# USAGE:
#   paver TASK [OPTIONS...]
#   paver help           -- Show all supported commands/tasks.
#   paver clean          -- Cleanup project workspace.
#   paver test           -- Run all tests (unittests, examples).
#
# SEE ALSO:
#  * http://pypi.python.org/pypi/Paver/
#  * http://www.blueskyonmars.com/projects/paver/
# ============================================================================

from paver.easy import *
import os
sys.path.insert(0, ".")

# -- USE PAVER EXTENSIONS: tasks, utility functions
# from   paver.setuputils import setup, install_distutils_tasks
# import paver.doctools
from paver_ext.pip_download import download_deps, localpi
from paver_ext.python_checker import pychecker, pylint
from paver_ext.paver_consume_args import Cmdline
from paver_ext import paver_require, paver_patch

paver_require.min_version("1.2")
paver_patch.ensure_path_with_pmethods(path)
paver_patch.ensure_path_with_smethods(path)

# -- REQUIRED-FOR: setup, sdist, ...
# NOTE: Adds a lot more python-project related tasks.
# install_distutils_tasks()

# ----------------------------------------------------------------------------
# TASK CONFIGURATION:
# ----------------------------------------------------------------------------
NAME = "behave"
options(
    sphinx=Bunch(
        docroot="docs",
        sourcedir=".",
        builddir="../build/docs"
    ),
    minilib=Bunch(
        extra_files=[ 'doctools', 'virtual' ]
    ),
    behave_test=Bunch(
        default_args=[
            "features/",
            "tools/test-features/",
            "selftest.features/",
            "issue.features/",
        ]
    ),
    pychecker = Bunch(
        default_args=NAME
    ),
    pylint = Bunch(
        default_args=NAME
    ),
    clean = Bunch(
        dirs  = [
            ".cache",
            ".tox",             #< tox build subtree.
            "__WORKDIR__",      #< behave_test tempdir.
            "build", "dist",    #< python setup temporary build dir.
            "tmp",
            "reports",          #< JUnit TESTS-*.xml (default directory).
            "test_results",
        ],
        files = [
            ".coverage",
            "paver-minilib.zip",
        ],
        walkdirs_patterns = [
            "*.egg-info",
            "__pycache__",
        ],
        walkfiles_patterns = [
            "*.pyc", "*.pyo", "*$py.class",
            "*.bak", "*.log", "*.tmp",
            ".coverage", ".coverage.*",
            "pylint_*.txt", "pychecker_*.txt",
            "xxx*.*", "testrun*.json",
            ".DS_Store", "*.~*~",   #< MACOSX
        ],
    ),
    pip = Bunch(
        requirements_files=[
            "requirements.txt",
            "requirements-develop.txt",
        ],
        # download_dir="downloads",
        download_dir= path("$HOME/.pip/downloads").expandvars(),
    ),
)

# ----------------------------------------------------------------------------
# TASKS:
# ----------------------------------------------------------------------------
@task
@consume_args
def docs(args):
    """
    USAGE: paver docs [BUILDER]
    Generate the documentation with sphinx (via sphinx-build).
    Available builder: html, pdf, ... (default: html)
    """
    # -- PREPROCESS: Separate builders/args and options
    cmdline = Cmdline.consume(args, default_args=["html"])
    cmdopts = cmdline.join_options()

    # -- STEP: Build the docs.
    for builder in cmdline.args:
        sphinx_build(builder, cmdopts=cmdopts)

@task
def linkcheck():
    """Check hyperlinks in documentation."""
    sphinx_build("linkcheck")


# ----------------------------------------------------------------------------
# TASK: test
# ----------------------------------------------------------------------------
@task
@consume_args
def test(args):
    """Execute all tests (unittests, feature tests)."""
    call_task("unittest")
    call_task("behave_test")

@task
@consume_args
def unittest(args):
    """Execute all unittests w/ nosetest runner."""
    cmdline = Cmdline.consume(args)
    nosetests(cmdline.join_args(), cmdopts=cmdline.join_options())

@task
@consume_args
def behave_test(args, options):
    """Execute all feature tests w/ behave."""
    cmdline = Cmdline.consume(args, default_args=options.default_args)
    if not cmdline.options:
        excluded_tags = "--tags=-xfail --tags=-not_supported"
        cmdopts = "-f progress {0}".format(excluded_tags)
    else:
        cmdopts = cmdline.join_options()

    # -- STEP: Collect test groups.
    test_groups = []
    for prefix in options.default_args:
        test_group = []
        for arg in cmdline.args:
            if arg.startswith(prefix):
                test_group.append(arg)
        if test_group:
            test_groups.append(test_group)

    # -- RUN TESTS: All tests at once.
    for test_group in test_groups:
        args = " ".join(test_group)
        behave(args, cmdopts)

    # -- RUN TESTS: All tests at once.
    # for arg in cmdline.args:
    #    behave(arg, cmdopts)
    # arg = " ".join(args)
    # behave(arg, cmdopts)

# ----------------------------------------------------------------------------
# TASK: test coverage
# ----------------------------------------------------------------------------
@task
def coverage_report():
    """Generate coverage report from collected coverage data."""
    sh("coverage combine")
    sh("coverage report")
    sh("coverage html")
    info("WRITTEN TO: build/coverage.html/")
    # -- DISABLED: sh("coverage xml")

@task
@consume_args
def coverage(args):
    """Run unittests and collect coverage, then generate report."""
    cmdline = Cmdline.consume(args)
    unittests    = [ arg for arg in cmdline.args if arg.startswith("test") ]
    behave_tests = [ arg for arg in cmdline.args if not arg.startswith("test") ]

    # -- STEP: Check if all tests should be run (normally: no args provided).
    should_always_run = not unittests and not behave_tests
    if should_always_run:
        behave_tests = list(options.behave_test.default_args)

    # -- STEP: Run unittests.
    if unittests or should_always_run:
        nosetests_coverage_run(" ".join(unittests))

    # -- STEP: Run feature-tests.
    # behave  = path("bin/behave").normpath()
    if behave_tests or should_always_run:
        cmdopts = "-f progress --tags=-xfail "+ cmdline.join_options()
        for behave_test_ in behave_tests:
            behave_coverage_run(behave_test_, cmdopts=cmdopts)
            # -- ALTERNATIVE:
            # coverage_run("{behave} --format=progress {cmdopts} {args}".format(
            #            behave=behave, args=behave_test_, cmdopts=cmdopts))

    # -- FINALLY:
    call_task("coverage_report")

# ----------------------------------------------------------------------------
# TASK: bump_version
# ----------------------------------------------------------------------------
@task
def bump_version(info, error):
    """Update VERSION.txt"""
    try:
        from behave import __version__ as VERSION
        info("VERSION: %s" % VERSION)
        file_ = open("VERSION.txt", "w+")
        file_.write("%s\n" % VERSION)
        file_.close()
    except StandardError, e:
        error("Update VERSION.txt FAILED: %s" % e)


# ----------------------------------------------------------------------------
# TASK: clean
# ----------------------------------------------------------------------------
@task
def clean(options):
    """Cleanup the project workspace."""
    for dir_ in options.dirs:
        path(dir_).rmtree_s()

    for pattern in options.walkdirs_patterns:
        dirs = path(".").walkdirs(pattern, errors="ignore")
        for dir_ in dirs:
            dir_.rmtree()

    for file_ in options.files:
        path(file_).remove_s()

    for pattern in options.walkfiles_patterns:
        files = path(".").walkfiles(pattern)
        for file_ in files:
            file_.remove()


# ----------------------------------------------------------------------------
# XML TASKS:
# ----------------------------------------------------------------------------
@task
@consume_args
def junit_validate(args):
    """Validate JUnit report *.xml files with xmllint."""
    if not args:
        args = [ "reports" ]

    # -- PREPROCESS ARGS:
    files = []
    for arg in args:
        path_ = path(arg)
        if "*" in arg:
            files.extend(path(".").glob(arg))
        elif path_.isdir():
            files.extend(path_.glob("*.xml"))
        else:
            files.append(arg)

    # -- VALIDATE XML FILES:
    xml_schema = "etc/junit.xml/behave_junit.xsd"
    problematic = []
    for arg in files:
        try:
            xmllint(arg, schema=xml_schema, options="")
        except BuildFailure:
            # -- KEEP-GOING: Collect failure and continue. Report errors later.
            problematic.append(arg)

    # -- SUMMARY:
    if problematic:
        message  = "{0} file(s) with XML validation errors.\n".format(len(problematic))
        message += "PROBLEMATIC FILES:\n  {0}".format("\n  ".join(problematic))
        raise BuildFailure(message)
    else:
        info("SUMMARY: {0} XML file(s) validated.".format(len(files)))

# ----------------------------------------------------------------------------
# PLATFORM-SPECIFIC TASKS: win32
# ----------------------------------------------------------------------------
#if sys.platform == "win32":
#    @task
#    @consume_args
#    def py2exe(args):
#        """Run py2exe to build a win32 executable."""
#        cmdline = " ".join(args)
#        python("setup_py2exe.py py2exe %s" % cmdline)
#
# ----------------------------------------------------------------------------
# UTILS:
# ----------------------------------------------------------------------------
BEHAVE   = path("bin/behave").normpath()
XMLLINT  = "xmllint"

def python(cmdline, cwd="."):
    """Execute a python script by using the current python interpreter."""
    return sh("{python} {cmd}".format(python=sys.executable, cmd=cmdline),
                cwd=cwd)

def coverage_run(cmdline):
    return sh("coverage run {cmdline}".format(cmdline=cmdline))
        # ignore_error=True)   #< Show coverage-report even if tests fail.

def nosetests(cmdline, cmdopts=""):
    """Run nosetest command"""
    return sh("nosetests {options} {args}".format(options=cmdopts, args=cmdline))

def nosetests_coverage_run(cmdline, cmdopts=""):
    """Collect coverage w/ nose-builtin coverage plugin."""
    cmdopts += " --with-coverage --cover-package={package}".format(package=NAME)
    return nosetests(cmdline, cmdopts)

def nosetests_coverage_run2(cmdline, cmdopts=""):
    """Collect coverage w/ extra nose-cov plugin."""
    cmdopts += " --with-cov --cov={package}".format(package=NAME)
    return nosetests(cmdline, cmdopts)

def behave(cmdline, cmdopts=""):
    """Run behave command"""
    return sh("{behave} {options} {args}".format(
                behave=BEHAVE, options=cmdopts, args=cmdline))

def behave_coverage_run(cmdline, cmdopts=""):
    """Collect coverage w/ behave."""
    os.environ["COVERAGE_PROCESS_START"] = path(".coveragerc").abspath()
    return behave(cmdline, cmdopts)

def sphinx_build(builder="html", cmdopts=""):
    if builder.startswith("-"):
        cmdopts += " %s" % builder
        builder  = ""
    sourcedir = options.sphinx.sourcedir
    destdir   = options.sphinx.builddir
    cmd = "sphinx-build {opts} -b {builder} {sourcedir} {destdir}/{builder}"\
            .format(builder=builder, sourcedir=sourcedir,
                    destdir=destdir, opts=cmdopts)
    sh(cmd, cwd=options.sphinx.docroot)

def xmllint(cmdline, options=None, schema=None):
    if not options:
        options = ""
    if schema:
        options = " --schema {0} {1}".format(schema, options)
    cmd = "{xmllint} {options} {cmdline}".format(
            xmllint=XMLLINT, options=options, cmdline=cmdline)
    sh(cmd, capture=True) #< SILENT: Output only in case of BuildError

class Cmdline(object):
    def __init__(self, args=None, options=None):
        self.args = args or []
        self.options = options or []

    def join_args(self, separator=" "):
        return separator.join(self.args)

    def join_options(self, separator=" "):
        return separator.join(self.options)

    @classmethod
    def consume(cls, args, default_args=None, default_options=None):
        args_ = []
        options_ = []
        for arg in args:
            if arg.startswith("-"):
                options_.append(arg)
            else:
                args_.append(arg)
        if not args_:
            args_ = default_args
        if not options_:
            options_ = default_options
        return cls(args_, options_)
