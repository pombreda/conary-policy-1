#
# Copyright (c) 2005-2006 rPath, Inc.
#
# This program is distributed under the terms of the Common Public License,
# version 1.0. A copy of this license should have been distributed with this
# source file in a file called LICENSE. If it is not present, the license
# is always available at http://www.opensource.org/licenses/cpl.php.
#
# This program is distributed in the hope that it will be useful, but
# without any warranty; without even the implied warranty of merchantability
# or fitness for a particular purpose. See the Common Public License for
# full details.
#

import os
import re
import stat

from conary.deps import deps
from conary.lib import util, magic
from conary.local import database
from conary.build import policy
from conary.build.use import Use


class _enforceBuildRequirements(policy.EnforcementPolicy):
    """
    Pure virtual base class from which classes are derived that
    enforce buildRequires population from runtime dependencies.
    """
    def preProcess(self):
        self.compExceptions = set()
        self.compReExceptions = set()
        compRe = re.compile('[a-zA-Z0-9]+:[a-zA-Z0-9]+')
        if self.exceptions:
            for exception in self.exceptions:
                exception = exception % self.recipe.macros
                if compRe.match(exception):
                    self.compExceptions.add(exception)
                else:
                    self.compReExceptions.add(re.compile(exception))
        self.exceptions = None

        # right now we do not enforce branches.  This could be
        # done with more work.  There is no way I know of to
        # enforce flavors, so we just remove them from the spec.
        self.truncatedBuildRequires = set(
            self.recipe.buildReqMap[spec].getName()
            for spec in self.recipe.buildRequires
            if spec in self.recipe.buildReqMap)

	components = self.recipe.autopkg.components
        reqDepSet = deps.DependencySet()
        provDepSet = deps.DependencySet()
        for pkg in components.values():
            reqDepSet.union(pkg.requires)
            provDepSet.union(pkg.provides)
        self.depSet = deps.DependencySet()
        self.depSet.union(reqDepSet - provDepSet)

        self.setTalk()

    def test(self):
        localDeps = self.depSet.getDepClasses().get(self.depClassType, None)
        if not localDeps:
            return False

        depSetList = [ ]
        for dep in localDeps.getDeps():
            depSet = deps.DependencySet()
            depSet.addDep(self.depClass, dep)
            depSetList.append(depSet)

        cfg = self.recipe.cfg
        self.db = database.Database(cfg.root, cfg.dbPath)
        self.localProvides = self.db.getTrovesWithProvides(depSetList)
        self.unprovided = [x for x in depSetList if x not in self.localProvides]

        return True

    def postProcess(self):
        del self.db

    def setTalk(self):
        # FIXME: remove "True or " when we are ready for errors
        if (True or 'local@local' in self.recipe.macros.buildlabel
            or Use.bootstrap._get()):
            self.talk = self.warn
        else:
            self.talk = self.error

    def do(self):
        missingBuildRequires = set()
        missingBuildRequiresChoices = []

	components = self.recipe.autopkg.components
        pathMap = self.recipe.autopkg.pathMap
        pathReqMap = {}
        interpreterSet = set()

        for dep in self.localProvides:
            provideNameList = [x[0] for x in self.localProvides[dep]]
            # normally, there is only one name in provideNameList

            foundCandidates = set()
            for name in provideNameList:
                for candidate in self.providesNames(name):
                    if self.db.hasTroveByName(candidate):
                        foundCandidates.add(candidate)
                        break
            foundCandidates -= self.compExceptions
            for compRe in self.compReExceptions:
                foundCandidates -= set(x for x in foundCandidates
                                       if compRe.match(x))

            missingCandidates = foundCandidates - self.truncatedBuildRequires
            if foundCandidates and missingCandidates == foundCandidates:
                # None of the troves that provides this requirement is
                # reflected in the buildRequires list.  Add candidates
                # to proper list to print at the end:
                if len(foundCandidates) > 1:
                    found = False
                    for candidateSet in missingBuildRequiresChoices:
                        if candidateSet == foundCandidates:
                            found = True
                    if found == False:
                        missingBuildRequiresChoices.append(foundCandidates)
                else:
                    missingBuildRequires.update(foundCandidates)

                # Now give lots of specific information to help the packager
                # in case things do not look so obvious...
                pathList = []
                for path in pathMap:
                    pkgfile = pathMap[path]
                    if pkgfile.hasContents and (pkgfile.requires() & dep):
                        pathList.append(path)
                        l = pathReqMap.setdefault(path, [])
                        l.append(dep)
                if pathList:
                    self.warn('buildRequires %s needed to satisfy "%s"'
                              ' for files: %s',
                              str(sorted(list(foundCandidates))),
                              str(dep),
                              ', '.join(sorted(pathList)))

            # look for interpreters
            for path in pathMap:
                pkgfile = pathMap[path]
                if pkgfile.hasContents and (pkgfile.requires() & dep):
                    m = self.recipe.magic[path]
                    if isinstance(m, magic.script):
                        interpreter = m.contents['interpreter']
                        if interpreter:
                            interpreterSet.add(interpreter)

        if interpreterSet:
            # find their components and add them to the list
            for interpreter in interpreterSet:
                for trove in self.db.iterTrovesByPath(interpreter):
                    interpreterTroveName = trove.getName()
                    if interpreterTroveName not in self.truncatedBuildRequires:
                        self.talk('interpreter %s missing build requirement %s',
                                  interpreter, interpreterTroveName)
                        missingBuildRequires.add(interpreterTroveName)

        if pathReqMap:
            for path in pathReqMap:
                self.warn('file %s has unsatisfied build requirements "%s"',
                          path, '", "'.join([
                             str(x) for x in
                               sorted(list(set(pathReqMap[path])))]))

        if missingBuildRequires:
            self.talk('add to buildRequires: %s',
                       str(sorted(list(set(missingBuildRequires)))))
            try:
                self.recipe.reportMissingBuildRequires(missingBuildRequires)
            except AttributeError:
                # it is OK if we are running with an earlier Conary that
                # does not have reportMissingBuildRequires
                pass
        if missingBuildRequiresChoices:
            for candidateSet in missingBuildRequiresChoices:
                self.talk('add to buildRequires one of: %s',
                           str(sorted(list(candidateSet))))
            # These are too unclear to pass to reportMissingBuildRequires
        if self.unprovided:
            self.talk('The following dependencies are not resolved'
                      ' within the package or in the system database: %s',
                      str(sorted([str(x) for x in self.unprovided])))

    def providesNames(self, libname):
        return [libname]


class EnforceSonameBuildRequirements(_enforceBuildRequirements):
    """
    NAME
    ====

    B{C{r.EnforceSonameBuildRequirements()}} - Ensure package requires
    dependencies match elements in r.buildRequires list

    SYNOPSIS
    ========

    C{r.EnforceSonameBuildRequirements([I{filterexp}] || [I{exceptions='I{pkg}:I{comp}'}])}

    DESCRIPTION
    ===========

    The C{r.EnforceSonameBuildRequirements()} policy ensures that each
    requires dependency in the package is matched by a suitable element in
    the C{buildRequires} list.

    Any trove names wrongly suggested can be eliminated from the
    list with C{r.EnforceSonameBuildRequirements(exceptions='I{pkg}:I{comp}')}.

    EXAMPLES
    ========

    C{r.EnforceSonameBuildRequirements(exceptions='.*')}

    Useful when packaging pre-built executables which do not need to
    (and cannot) be linked at cook time to development libraries
    specified in C{buildRequires}.
    """

    depClassType = deps.DEP_CLASS_SONAME
    depClass = deps.SonameDependencies

    def providesNames(self, libname):
        # Instead of requiring the :lib component that satisfies
        # the dependency, our first choice, if possible, is to
        # require :devel, because that would include header files;
        # if it does not exist, then :devellib for a soname link;
        # finally if neither of those exists, then :lib (though
        # that is a degenerate case).
        return [libname.replace(':lib', ':devel'),
                libname.replace(':lib', ':devellib'),
                libname]


class EnforcePythonBuildRequirements(_enforceBuildRequirements):
    """
    NAME
    ====

    B{C{r.EnforcePythonBuildRequirements()}} - Ensure package meets Python
    runtime requirements

    SYNOPSIS
    ========

    C{r.EnforcePythonBuildRequirements([I{filterexp}] || [I{exceptions='I{pkg}:I{comp}'}])}

    DESCRIPTION
    ===========

    The C{r.EnforcePythonBuildRequirements()} policy ensures that Python
    runtime requirements are met by the package, or by components listed in
    the C{buildRequires} list.  In general, missing Python build
    requirements will translate into missing or incomplete Python
    runtime requirements.

    Any trove names wrongly suggested should be eliminated from consideration
    by using C{r.Requires(exceptDeps='python: ...')}
    """

    depClassType = deps.DEP_CLASS_PYTHON
    depClass = deps.PythonDependencies

    # FIXME: remove this when we are ready to enforce Python dependencies
    def setTalk(self):
        self.talk = self.warn


class EnforceJavaBuildRequirements(_enforceBuildRequirements):
    """
    NAME
    ====

    B{C{r.EnforceJavaBuildRequirements()}} - Ensure package meets Java
    runtime requirements

    SYNOPSIS
    ========

    C{r.EnforceJavaBuildRequirements([I{filterexp}] || [I{exceptions='I{pkg}:I{comp}'}])}

    DESCRIPTION
    ===========

    The C{r.EnforceJavaBuildRequirements()} policy ensures that Java runtime
    requirements are met by the package, or by components listed in the
    C{buildRequires} list.

    Any trove names wrongly suggested can be eliminated from the
    list with C{r.EnforceJavaBuildRequirements(exceptions='I{pkg}:I{comp}')}.

    EXAMPLES
    ========

    C{r.EnforceJavaBuildRequirements(exceptions='.*')}

    This turns off all enforcement of Java build requirements, which is
    particularly useful when packaging pre-built Java applications.

    If you are packaging an application that includes Java files that
    are never executed on the system on which they are installed, but
    are only provided to other systems (likely via HTTP to a remote
    web browser), then you should instead remove the runtime requirements
    entirely with C{r.Requires(exceptions='.*\.(java|jar|zip)')} (the
    fastest approach) or C{r.Requires(exceptDeps='java:.*')} (slower
    but more accurate).
    """

    depClassType = deps.DEP_CLASS_JAVA
    depClass = deps.JavaDependencies

    # FIXME: remove this when we are ready to enforce Java dependencies
    def setTalk(self):
        self.talk = self.warn


class EnforceCILBuildRequirements(_enforceBuildRequirements):
    """
    NAME
    ====

    B{C{r.EnforceCILBuildRequirements()}} - Ensure package meets CIL
    runtime requirements

    SYNOPSIS
    ========

    C{r.EnforceCILBuildRequirements([I{filterexp}] || [I{exceptions='I{pkg}:I{comp}'}])}

    DESCRIPTION
    ===========

    The C{r.EnforceCILBuildRequirements()} policy ensures that CIL runtime
    requirements are met by the package, or by components listed in the
    C{buildRequires} list.

    Any trove names wrongly suggested can be eliminated from the
    list with C{r.EnforceCILBuildRequirements(exceptions='I{pkg}:I{comp}')}.

    EXAMPLES
    ========

    C{r.EnforceCILBuildRequirements(exceptions='.*')

    Useful when packaging pre-built CIL files.
    """

    depClassType = deps.DEP_CLASS_CIL
    depClass = deps.CILDependencies


class EnforcePerlBuildRequirements(_enforceBuildRequirements):
    """
    NAME
    ====

    B{C{r.EnforcePerlBuildRequirements()}} - Ensure package meets Perl
    runtime requirements

    SYNOPSIS
    ========

    C{r.EnforcePerlBuildRequirements([I{filterexp}] || [I{exceptions='I{pkg}:I{comp}'}])}

    DESCRIPTION
    ===========

    The C{r.EnforcePerlBuildRequirements()} policy ensures that Perl runtime
    requirements are met by the package, or by components listed in the
    C{buildRequires} list.  In general, missing Perl build
    requirements will translate into missing or incomplete Perl
    runtime requirements.

    Any trove names wrongly suggested should be eliminated from consideration
    by using C{r.Requires(exceptDeps='perl: ...')}
    """

    depClassType = deps.DEP_CLASS_PERL
    depClass = deps.PerlDependencies

    # FIXME: remove this when we are ready to enforce Perl dependencies
    def setTalk(self):
        self.talk = self.warn


class EnforceConfigLogBuildRequirements(policy.EnforcementPolicy):
    """
    NAME
    ====

    B{C{r.EnforceConfigLogBuildRequirements()}} - Ensures that components
    mentioned in config.log files are listed as build requirements

    SYNOPSIS
    ========

    C{r.EnforceConfigLogBuildRequirements([I{filterexp}] || [I{/path/to/file/found}] || [I{exceptions='I{pkg}:I{comp}'}])}

    DESCRIPTION
    ===========

    The C{r.EnforceConfigLogBuildRequirements()} policy ensures that components
    containing files mentioned in C{config.log} files are listed as build
    requirements.

    EXAMPLES
    ========

    C{r.EnforceConfigLogBuildRequirements(exceptions='flex:runtime')

    This disables a requirement for flex:runtime; this would normally
    be because the C{configure} program checked for flex, but does not
    actually need to run it because the program is shipped with a
    prebuilt lexical analyzer.
    """
    filetree = policy.BUILDDIR
    invariantinclusions = [ (r'.*/config\.log', 0400, stat.S_IFDIR), ]
    # list of regular expressions (using macros) that cause an
    # entry to be ignored unless a related strings is found in
    # another named file (empty tuple is unconditional blacklist)
    greylist = [
        # config.log string, ((filename, regexp), ...)
        ('%(prefix)s/X11R6/bin/makedepend', ()),
        ('%(bindir)s/g77',
            (('configure.ac', r'\s*AC_PROG_F77'),
             ('configure.in', r'\s*AC_PROG_F77'))),
        ('%(bindir)s/bison',
            (('configure.ac', r'\s*AC_PROC_YACC'),
             ('configure.in', r'\s*(AC_PROG_YACC|YACC=)'))),
    ]

    def test(self):
        return not self.recipe.ignoreDeps

    def preProcess(self):
        self.foundRe = re.compile('^[^ ]+: found (/([^ ]+)?bin/[^ ]+)\n$')
        self.foundPaths = set()
        self.greydict = {}
        # turn list into dictionary, interpolate macros, and compile regexps
        for greyTup in self.greylist:
            self.greydict[greyTup[0] % self.macros] = (
                (x, re.compile(y % self.macros)) for x, y in greyTup[1])
        # process exceptions differently; user can specify either the
        # source (found path) or destination (found component) to ignore
        self.pathExceptions = set()
        self.compExceptions = set()
        if self.exceptions:
            for exception in self.exceptions:
                exception = exception % self.recipe.macros
                if '/' in exception:
                    self.pathExceptions.add(exception)
                else:
                    self.compExceptions.add(exception)
        # never suggest a recursive buildRequires
        self.compExceptions.update(set(self.recipe.autopkg.components.keys()))
        self.exceptions = None

    def foundPath(self, line):
        match = self.foundRe.match(line)
        if match:
            return match.group(1)
        return False

    def doFile(self, path):
        fullpath = self.macros.builddir + path
        # iterator to avoid reading in the whole file at once;
        # nested iterators to avoid matching regexp twice
        foundPaths = set(path for path in
           (self.foundPath(line) for line in file(fullpath))
           if path and path not in self.pathExceptions)

        # now remove false positives using the greylist
        # copy() for copy because modified
        for foundPath in foundPaths.copy():
            if foundPath in self.greydict:
                foundMatch = False
                for otherFile, testRe in self.greydict[foundPath]:
                    otherFile = fullpath.replace('config.log', otherFile)
                    if not foundMatch and os.path.exists(otherFile):
                        otherFile = file(otherFile)
                        if [line for line in otherFile if testRe.match(line)]:
                            foundMatch = True
                if not foundMatch:
                    # greylist entry has no match, so this is a false
                    # positive and needs to be removed from the set
                    foundPaths.remove(foundPath)
        self.foundPaths.update(foundPaths)

    def postProcess(self):
        if not self.foundPaths:
            return
        # first, get all the trove names in the transitive buildRequires
        # runtime dependency closure
        db = database.Database(self.recipe.cfg.root, self.recipe.cfg.dbPath)
        transitiveBuildRequires = set(
            self.recipe.buildReqMap[spec].getName()
            for spec in self.recipe.buildRequires)
        depSetList = [ self.recipe.buildReqMap[spec].getRequires()
                       for spec in self.recipe.buildRequires ]
        d = db.getTransitiveProvidesClosure(depSetList)
        for depSet in d:
            transitiveBuildRequires.update(set(tup[0] for tup in d[depSet]))

        # next, for each file found, report if it is not in the
        # transitive closure of runtime requirements of buildRequires
        fileReqs = set()
        for path in sorted(self.foundPaths):
            thisFileReqs = set(trove.getName()
                               for trove in db.iterTrovesByPath(path))
            thisFileReqs -= self.compExceptions
            missingReqs = thisFileReqs - transitiveBuildRequires
            if missingReqs:
                self.warn('path %s suggests buildRequires: %s',
                          path, ', '.join((sorted(list(missingReqs)))))
            fileReqs.update(thisFileReqs)

        # finally, give the coalesced suggestion for cut and paste
        # into the recipe if all the individual messages make sense
        missingReqs = fileReqs - transitiveBuildRequires
        if missingReqs:
            self.warn('Probably add to buildRequires: %s',
                      str(sorted(list(missingReqs))))
            try:
                self.recipe.reportMissingBuildRequires(missingReqs)
            except AttributeError:
                # it is OK if we are running with an earlier Conary that
                # does not have reportMissingBuildRequires
                pass
