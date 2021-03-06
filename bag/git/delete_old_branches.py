#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''Removes git branches that have been merged onto the current branch.

Don't forget to do a "git fetch --all --prune" on other machines
after deleting remote branches. Other machines may still have
obsolete tracking branches (see them with "git branch -a").
'''

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from datetime import date, timedelta
from nine.decorator import reify
from nine import nine
from argh import ArghParser, arg  # easy_install argh
from bag.command import checked_execute  # , CommandError
from bag.console import bool_input

IGNORE = ['develop', 'master']


def merged_branches(remote=None, ignore=IGNORE):
    '''Sequence of branches that have been merged onto the current branch.'''
    if remote:
        command = 'git branch -a --merged'
    else:
        command = 'git branch --merged'

    for name in checked_execute(command).split('\n'):
        # The command also lists the current branch, so we get rid of it
        if name.startswith('* ') or ' -> ' in name:
            continue
        name = name.strip()

        if remote and name.startswith('remotes/'):
            name = name[8:]
            if name.startswith(remote):
                branch = Branch(name=name[len(remote) + 1:], remote=remote)
            else:
                continue
        else:
            branch = Branch(name)

        if branch.name in ignore:
            continue
        yield branch


@nine
class Branch(object):
    def __init__(self, name, remote=''):
        self.name = name
        self.remote = remote

    def __repr__(self):
        return 'remotes/{}/{}'.format(
            self.remote, self.name) if self.remote else self.name

    @reify
    def merge_date(self):
        '''Returns the date when the specified branch was merged into the
        current git branch. On the console, you can try this command:

            git show --pretty=format:"%Cgreen%ci %Cblue%cr%Creset" BRANCH | head -n 1
        '''
        branch_spec = repr(self)
        line = checked_execute(
            'git show --pretty=format:"%ci" {} | head -n 1'
            .format(branch_spec))
        sdate = line[:10]
        year, month, day = [int(x) for x in sdate.split('-')]
        return date(year, month, day)

    def is_older_than_days(self, age):
        return timedelta(int(age)) < date.today() - self.merge_date

    def delete(self):
        if self.remote:
            checked_execute('git push {} :{}'.format(self.remote, self.name),
                            accept_codes=[0, 1])
        else:
            checked_execute('git branch -d {}'.format(self))


@arg('--dry', action='store_true', help='Dry run: only list the branches')
@arg('-i', '--ignore', action='append', default=IGNORE,
     help='Branches to leave untouched')
@arg('-l', '--locally', action='store_true',
     help='Delete the branches locally')
@arg('-r', '--remote', metavar='REMOTE',
     help='Delete the branches on the remote REMOTE')
@arg('-y', action='store_true',
     help='Do not interactively confirm before deleting branches')
@arg('days', type=int, help='Minimum age in days')
def delete_old_branches(days, dry=False, locally=False, remote=None, y=False,
                        ignore=IGNORE):
    if not locally and not remote:
        print('You must specify -l or -r or both.')
        import sys
        sys.exit(4242)

    for branch in merged_branches(remote=remote, ignore=ignore):
        if not remote and branch.remote:
            continue
        if not locally and not branch.remote:
            continue
        if days and not branch.is_older_than_days(days):
            continue

        if y:
            print('    ' + str(branch))
        else:
            if not bool_input('Delete the branch "{}"?'.format(branch),
                              default=False):
                continue

        if dry:
            continue
        branch.delete()


def command():
    # http://argh.readthedocs.org/en/latest/
    parser = ArghParser(description=__doc__)
    parser.set_default_command(delete_old_branches)
    # parser.add_commands([delete_old_branches])
    parser.dispatch()


if __name__ == '__main__':
    command()
