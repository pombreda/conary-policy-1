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

"""
These policies are stubs to help convert old recipes that reference
obsolete policy.
"""

from conary.build import policy

class EtcConfig(policy.EnforcementPolicy):
    """
    NAME
    ====

    B{C{r.EtcConfig()}} - DEPRECATED CLASS

    SYNOPSIS
    ========

    Do not use

    DESCRIPTION
    ===========

    The C{r.EtcConfig()} class is a deprecated class, included only for
    backwards compatibility.  Use C{r.Config} instead.
    """
    def updateArgs(self, *args, **keywords):
        self.warn('EtcConfig deprecated, please use Config instead')
        self.recipe.Config(*args, **keywords)
    def do(self):
        pass


class InstallBucket(policy.EnforcementPolicy):
    """
    NAME
    ====

    B{C{r.InstallBucket()}} - STUB CLASS

    SYNOPSIS
    ========

    Do not use

    DESCRIPTION
    ===========

    The C{r.InstallBucket()} policy is a stub, included only for backwards
    compatibility, and should be removed from use in recipes.
    """
    def updateArgs(self, *args, **keywords):
        self.warn('Install buckets are deprecated')

    def test(self):
        return False


class User(policy.EnforcementPolicy):
    """
    NAME
    ====

    B{C{r.User()}} - STUB CLASS

    SYNOPSIS
    ========

    Used in info recipes, but not used in package recipes

    DESCRIPTION
    ===========

    The C{r.User()} policy is a stub in package recipe context, included
    only for backwards compatibility with older package recipes, and should
    be removed from use in package recipes. Use of C{r.User} in info recipes
    is valid, however.
    """
    def updateArgs(self, *args, **keywords):
        self.warn('User policy is deprecated, create a separate UserInfoRecipe instead')

    def test(self):
        return False


class SupplementalGroup(policy.EnforcementPolicy):
    """
    NAME
    ====

    B{C{r.SupplementalGroup()}} - STUB CLASS

    SYNOPSIS
    ========

    Used in info recipes, but not used in package recipes

    DESCRIPTION
    ===========

    The C{r.SupplementalGroup()} policy is a stub in package recipe context,
    included only for backwards compatibility with older package recipes,
    and should be removed from use in package recipes. Use of 
    C{r.SupplementalGroup} in info recipes is valid, however.
    """
    def updateArgs(self, *args, **keywords):
        self.warn('SupplementalGroup policy is deprecated, create a separate GroupInfoRecipe instead')

    def test(self):
        return False


class Group(policy.EnforcementPolicy):
    """
    NAME
    ====

    B{C{r.Group()}} - STUB CLASS

    SYNOPSIS
    ========

    Used in info recipes, but not used in package recipes

    DESCRIPTION
    ===========

    The C{r.Group()} policy is a stub in package recipe context, included
    only for backwards compatibility with older package recipes, and should
    be removed from use in package recipes. Use of C{r.Group} in info recipes
    is valid, however.
    """
    def updateArgs(self, *args, **keywords):
        self.warn('Group policy is deprecated, create a separate GroupInfoRecipe instead')

    def test(self):
        return False
