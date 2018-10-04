#!/usr/bin/env python3
"""Manage dotfiles

This script is used to manage dotfiles.
"""

import os
import sys
import shlex
import shutil
import locale
import platform
import subprocess
import contextlib

try:
    import click
except Exception:
    click = None

if click is None or not click.__version__.startswith("6."):
    print(
        "Please run `pip install 'click>=6.0.0'` since this script depends on "
        "click for it's command line interface."
    )
    sys.exit(1)

try:
    import yaml
except Exception:
    print(
        "Please run `pip install pyyaml` since this script depends on it for "
        "the check command"
    )
    sys.exit(1)

from .config import HOME_DIR, ROOT_DIR, DEFAULT_SOURCE_DIR, ACTION_COLOR_DICT

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
class Logger(object):

    def __init__(self):
        super().__init__()
        self._indent = 0
        self._indent_size = 4

    def __enter__(self):
        self._indent += self._indent_size
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self._indent -= self._indent_size
        return True

    @staticmethod
    def style(msg, **kwargs):
        return click.style(msg, **kwargs)

    def _m(self, message, *args, **kwargs):
        # A shorthand for brevity
        if isinstance(message, str):
            return " " * self._indent + message.format(*args, **kwargs)
        else:
            assert not (args, kwargs)
            return " " * self._indent + repr(message)

    def info(self, message, *args, **kwargs):
        click.secho(self._m(message, *args, **kwargs))

    def error(self, message, *args, **kwargs):
        click.secho(self._m('ERROR: ' + message, *args, **kwargs), fg='red')

    def spaced_status(self, action, message, fit_width=10):
        colour = ACTION_COLOR_DICT.get(action, None)
        if colour is None:
            self.error(
                "Got unknown action for logger - {}; will continue though",
                action
            )

        s = click.style("[" + action.center(fit_width) + "]", fg=colour)
        self.info('{} {}', s, message)


@contextlib.contextmanager
def task(message):
    click.secho('# {}...'.format(message), fg='blue')
    try:
        yield
    except Exception:
        log.error('Aborting due to following error...')
        raise
    else:
        click.secho('# Completed', fg='blue')


def run(command, repo):
    if repo.verbose:
        log.info('> {}', command)
    if repo.dry_run:
        return 0
    return subprocess.call(shlex.split(command))


def run_output(command):
    try:
        return subprocess.check_output(
            shlex.split(command),
            stderr=subprocess.STDOUT,
        ).decode(
            locale.getpreferredencoding()
        )
    except subprocess.CalledProcessError:
        return None


# ------------------------------------------------------------------------------
# Handling Symlinks
# ------------------------------------------------------------------------------
class DotFilesRepo(object):

    def __init__(self, source_dir, target_dir, walk_depth, verbose, dry_run):
        super().__init__()
        self.global_action = None
        self.source_dir = os.path.abspath(source_dir)
        self.target_dir = os.path.abspath(target_dir)
        self.walk_depth = walk_depth
        self.verbose = verbose
        self.dry_run = dry_run

    def link_source_to_target(self, source, target):
        run('mkdir -p "{}"'.format(os.path.dirname(target)), self)
        run('ln -s "{}" "{}"'.format(source, target), self)

    def get_action(self, target):
        if self.global_action is not None:
            return self.global_action

        # Mapping of options to return values
        mapping = {
            's': 'skip',
            'b': 'backup',
            'u': 'update (overwrite)',
        }

        # Prepare Prompt
        options = []
        for val in mapping.values():
            options.append('[{}]{}'.format(val[0], val[1:]))
            options.append('[{}]{} all'.format(val[0].upper(), val[1:]))

        prompt_text = (
            'File already exists: {}\n'
            'What do you want to do?\n'
            '{}'
        ).format(target, ', '.join(options))

        # Show Prompt
        click.echo(prompt_text)

        # Get and validate input
        action = ' '
        while action.lower() not in mapping:
            action = click.getchar()
            click.echo(action)

        # Set the action
        val = mapping[action.lower()].split()[0]

        if action.isupper():
            self.global_action = val

        return val

    def find_files_to_symlink(self, topics):
        walk_dir = self.source_dir.rstrip(os.path.sep)
        base_depth = walk_dir.count(os.path.sep)
        # assert os.path.isdir(walk_dir)
        # if topics and 'base' not in topics:
        #     log.info('Adding topic {!r}', 'base')

        for root, dirs, files in os.walk(walk_dir):
            current_depth = root.count(os.path.sep)

            # Filter topics
            # if current_depth == 0 and topics:
            #     for item in dirs[:]:
            #         if item not in topics:
            #             dirs.remove(item)
            #             log.info('Skipping topic: {}'.format(item))

            # Skip .git folders
            if '.git' in dirs:
                dirs.remove('.git')

            # yield things to be symlinked
            for item in dirs + files:
                if item.endswith('.symlink'):
                    yield os.path.join(os.path.relpath(root, walk_dir), item)

            # Ensure we don't recurse more than the allowed limit
            if current_depth >= base_depth + self.walk_depth:
                del dirs[:]

    def compute_target(self, rel_path):
        topic, *parts = rel_path.split(os.sep)
        # Prefix a '.'
        parts[0] = '.' + parts[0]
        # Remove the '.symlink' portion
        parts[-1] = parts[-1][:-len('.symlink')]
        return os.path.join(self.target_dir, *parts)

    def backup_file(self, fname):
        run('mv "{0}" "{0}.backup"'.format(fname), self)

    def remove_file(self, fname):
        run('rm "{}"'.format(fname), self)

    def sync(self, topics):
        """Symlinks the dotfiles in the source_dir with target_dir

        Structure of dotfiles:
          - topic-1/
            - content-file-1.shrc
            - content-file-2.symlink
            - content-file-3.zsh
          - topic-2/
            - content-file-1.shrc
            - content-file-2.symlink
            - content-file-3.zsh
        """
        if not self.dry_run:
            # Write the location of the dotfiles repository in a file
            path = os.path.join(self.target_dir, '.dotfiles-dir')
            with open(path, 'w') as f:
                f.write(self.source_dir)

        for rel_path in self.find_files_to_symlink(topics):
            source = os.path.join(self.source_dir, rel_path)

            target = self.compute_target(rel_path)

            # Determine what to do with target
            if os.path.islink(target):
                if os.readlink(target) == source:  # link is up to date
                    action = 'up to date'
                else:  # link needs updating
                    action = 'update'
            elif not os.path.exists(target):
                action = 'create'
            else:
                action = self.get_action(target)

            if target.startswith(HOME_DIR + os.sep):
                status_target = "~" + target[len(HOME_DIR):]
            else:
                status_target = target
            log.spaced_status(action, status_target)

            # Take the required action
            if action in ['skip', 'up to date']:
                continue  # no action needed.
            elif action == 'backup':
                self.backup_file(target)
            elif action == 'update':
                self.remove_file(target)

            self.link_source_to_target(source, target)

        self.clean()

    def is_broken_symlink(self, path):
        return os.path.islink(path) and not os.path.exists(path)

    def clean(self):
        """Removes stale symlinks from target_dir
        """
        for item in os.listdir(self.target_dir):
            path = os.path.join(self.target_dir, item)
            # If symlink is broken
            if self.is_broken_symlink(path):
                if not self.dry_run:
                    run('rm "{}"'.format(path), self)
                log.spaced_status('remove', path)


# ------------------------------------------------------------------------------
# Checking the system setup
# ------------------------------------------------------------------------------
class SystemChecker(object):
    """A super-fancy helper for checking the system configuration
    """

    def __init__(self):
        super().__init__()
        self._logger = Logger()

    def _log_happy(self, msg):
        self._logger.spaced_status("pass", msg, fit_width=4)

    def _log_angry(self, msg, is_warning):
        if is_warning:
            self._logger.spaced_status("warn", msg, fit_width=4)
        else:
            self._logger.spaced_status("fail", msg, fit_width=4)

    def platform(self):
        return platform.system()

    def equal(self, expected, *, should_warn=False, **kwargs):
        """Check if a given value for something is equal to the expected value.

        checker.equal(value, name=from_system)
        """
        assert len(kwargs) == 1, "expected 1 keyword argument"

        name, value = next(iter(kwargs.items()))
        if value == expected:
            self._log_happy(name + " is correct")
        else:
            self._log_angry(
                "{} is not {!r}, it is {!r}".format(name, expected, value),
                is_warning=should_warn,
            )

    # The actual logic is below
    def run(self, fname):
        data = self._load_yaml(fname)

        self._check_username(data["identity"]["username"])
        self._check_ssh(data["identity"]["ssh-key"])
        self._check_gpg(data["identity"]["gpg-key"])

        for category, contents in data["things"].items():
            self._check_category(category, contents, data)

    def _load_yaml(self, fname):
        with open(fname) as f:
            try:
                return yaml.load(f)
            except Exception as e:
                click.secho("ERROR: Could not parse file.", fg="red")
                click.secho(str(e), fg="red")
                sys.exit(1)

    def _check_username(self, expected):
        self.equal(expected, Username=os.environ["USER"])

    def _check_ssh(self, expected):
        # FIXME: Is this fragile?
        output = run_output("ssh-keygen -E md5 -lf {}".format(
            os.path.expanduser("~/.ssh/id_rsa.pub")
        ))
        if output is None:
            ssh_key = "not found"
        else:
            ssh_key = output.split()[1]
            if ssh_key.startswith("MD5:"):
                ssh_key = ssh_key[4:]

        self.equal(expected, **{"SSH key": ssh_key})

    def _check_gpg(self, expected):
        # This checks that the GPG key exists in the dB
        output = run_output("gpg --list-keys {}".format(expected))
        if output is not None:
            self.equal(expected, **{"GPG key": expected})
        else:
            self.equal(expected, **{"GPG key": "not found"})

    def _check_category(self, category, contents, data):
        if "if" in contents:
            if list(contents["if"]) != ["platform"]:
                raise ValueError(
                    "Needed condition of category {} to be 'platform'"
                    .format(category)
                )
            if contents["if"]["platform"] != self.platform():
                log.spaced_status("skip", category)
                return

        log.spaced_status("topic", category, fit_width=5)
        with log:
            self._check_executables(category, contents.get("executables", None))
            self._check_run_items(category, contents.get("run_check", None), data)

    def _check_executables(self, category, executables):
        if not executables:
            return
        # Convert the string to a list.
        executables = list(map(lambda x: x.strip(), executables.split(",")))

        missing = set()
        for fname in executables:
            if shutil.which(fname) is None:
                missing.add(fname)

        verb = lambda x: "executable" if len(x) == 1 else "executables"
        if missing:
            desc = "missing {}: {}".format(
                verb(missing), ", ".join(map(repr, missing))
            )

            log.spaced_status("fail", desc, fit_width=4)
        else:
            log.spaced_status(
                "pass",
                "{} {} available".format(len(executables), verb(executables)),
                fit_width=4,
            )

    def _check_run_items(self, category, run_items, data):
        if not run_items:
            return

        for name, cmd_dict in run_items.items():
            if not isinstance(cmd_dict, dict) or "cmd" not in cmd_dict:
                log.spaced_status("warn", "!!! invalid !!! {}".format(category, name), fit_width=4)
                continue

            if "equal" in cmd_dict:
                # Matching output.
                expected = cmd_dict["equal"]
                # Perform substitution
                if expected.startswith("$"):
                    item = data
                    for part in expected[1:].split("."):
                        item = item[part]
                    expected = item

                got = run_output(cmd_dict["cmd"])
                if isinstance(got, str) and expected == got.strip():
                    log.spaced_status("pass", name, fit_width=4)
                else:
                    log.spaced_status("fail", name, fit_width=4)
            else:
                log.spaced_status("warn", name + " -- did not check.", fit_width=4)


# ------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------
@click.group()
@click.option(
    '--src-dir', type=click.Path(exists=True), default=DEFAULT_SOURCE_DIR,
    help="Location to use as dotfiles directory"
)
@click.option(
    '--dest-dir', type=click.Path(exists=True), default=HOME_DIR,
    help="Location to create symlinks"
)
@click.option(
    '-n', '--dry-run', default=False, is_flag=True,
    help='Enable debugging mode (implies --verbose)'
)
@click.option(
    '--depth', default=3, type=int,
    help='How deep to recurse looking for ".symlink" items'
)
@click.option(
    '-v', '--verbose', default=False, is_flag=True,
    help='Show what commands have been executed.'
)
@click.pass_context
def cli(ctx, src_dir, dest_dir, dry_run, depth, verbose):
    if dry_run:
        verbose = True

    ctx.obj['obj'] = DotFilesRepo(src_dir, dest_dir, depth, verbose, dry_run)
    ctx.obj['verbose'] = verbose


@cli.command()
@click.argument('topics', nargs=-1)
@click.pass_context
def sync(ctx, topics):
    """Update the symlinks
    """
    with task('Syncing dotfiles'):
        ctx.obj['obj'].sync(topics)


@cli.command()
@click.pass_context
def clean(ctx):
    """Removes stale/broken symlinks
    """
    with task('Cleaning broken symlinks'):
        ctx.obj['obj'].clean()


@cli.command()
@click.pass_context
def check(ctx):
    """Check whether a system is setup correctly.
    """
    checker = SystemChecker()
    checker.run("tools/checks.yaml")


def main():
    cli(obj={}, auto_envvar_prefix='DOTFILES')


# Some globals for nicer handling of the world
log = Logger()

if __name__ == '__main__':
    main()