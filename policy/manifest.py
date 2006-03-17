#
# Copyright (c) 2004-2006 rPath, Inc.
#
# This program is distributed under the terms of the Common Public License,
# version 1.0. A copy of this license should have been distributed with this
# source file in a file called LICENSE. If it is not present, the license
# is always available at http://www.opensource.org/licenses/cpl.php.
#
# This program is distributed in the hope that it will be useful, but
# without any waranty; without even the implied warranty of merchantability
# or fitness for a particular purpose. See the Common Public License for
# full details.
#

import os

from conary.lib import util
from conary.build import policy


class ParseManifest(policy.PackagePolicy):
    """
    NAME
    ====

    B{C{r.ParseManifest()}} - Parses a file containing a manifest intended for
    RPM

    SYNOPSIS
    ========

    C{r.ParseManifest([I{filterexp}] I{exceptions=filterexp}])}

    DESCRIPTION
    ===========

    The C{r.ParseManifest()} class is called from within a Conary recipe to
    parse a file containing a manifest intended for RPM

    In the manifest, C{r.r.ParseManifest()} finds the information that cannot
    be represented by pure filesystem status with non-root built device files,
    (C{%dev}) and permissions (C{%attr}).

    It ignores directory ownership (C{%dir}) because Conary handles
    directories very differently from RPM.

    The class C{r.ParseManifest) also ignores C{%defattr} because Conary's
    default ownership is C{root:root}, and because permissions
    (except for setuid and setgid files) are collected from the filesystem.

    C{r.ParseManifest} translates each parsed manifest line, into the related
    Conary construct.

    Warning: tested only with MAKEDEV output so far.


    EXAMPLES
    ========

    FIXME NEED EXAMPLE
    """

    requires = (
        ('setModes', policy.REQUIRED),
        ('MakeDevices', policy.REQUIRED),
        ('Ownership', policy.REQUIRED),
    )

    def __init__(self, *args, **keywords):
	self.paths = []
	policy.PackagePolicy.__init__(self, *args, **keywords)

    def updateArgs(self, *args, **keywords):
	"""
	ParseManifest(path(s)...)
	"""
	if args:
	    self.paths.extend(args)
	policy.PackagePolicy.updateArgs(self, **keywords)

    def do(self):
	for path in self.paths:
	    self.processPath(path)

    def processPath(self, path):
	if not path.startswith('/'):
	    path = self.macros['builddir'] + os.sep + path
        f = open(path)
        for line in f:
            line = line.strip()
            fields = line.split(')')

            attr = fields[0].lstrip('%attr(').split(',')
            perms = attr[0].strip()
            owner = attr[1].strip()
            group = attr[2].strip()

            fields[1] = fields[1].strip()
            if fields[1].startswith('%dev('):
                dev = fields[1][5:].split(',')
                devtype = dev[0]
                major = dev[1]
                minor = dev[2]
                target = fields[2].strip()
                self.recipe.MakeDevices(target, devtype, int(major), int(minor),
                                        owner, group, int(perms, 0))
            elif fields[1].startswith('%dir '):
		pass
		# ignore -- Conary directory handling is too different
		# to map
            else:
		# XXX is this right?
                target = fields[1].strip()
		if int(perms, 0) & 06000:
		    self.recipe.setModes(int(perms, 0),
                                         util.literalRegex(target))
		if owner != 'root' or group != 'root':
		    self.recipe.Ownership(owner, group,
                                          util.literalRegex(target))
