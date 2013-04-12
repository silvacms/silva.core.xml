# -*- coding: utf-8 -*-
# Copyright (c) 2013  Infrae. All rights reserved.
# See also LICENSE.txt

# test
import io
import zipfile

from sprout.saxext import xmlimport
from sprout.saxext import collapser
from silva.core.references.utils import canonical_path


class Importer(object):
    """Manage information about the import.
    """

    def __init__(self, root, request, options=None):
        self.__actions = []
        self.__problems = []
        self.__root = root
        self.__paths = {}
        self.__request = request
        self.__executed = False
        self.__executing = False
        self.options = options or {}
        self.options.update({
                'ignore_not_allowed': True,
                'import_filter': collapser.CollapsingHandler})

    @property
    def request(self):
        return self.__request

    @property
    def root(self):
        return self.__root

    def getFile(self, filename):
        """Return content of a file
        """
        return None

    def reportProblem(self, reason, content):
        """Report a new problem that happened during the import.
        """
        self.__problems.append((reason, content))

    def getProblems(self):
        """Return the list of the currently known problems with the
        import.
        """
        return list(self.__problems)

    def importStream(self, source):
        """Import the XML provided by the file object source.
        """
        if not self.__executed:
            if self.__executing:
                raise AssertionError('Currently importing')
            self.__executing = True
            registry.importFromStream(
                source,
                result=self.__root,
                options=self.options,
                extra=self)
            # run post-processing actions
            self.runActions()
            self.__executed = True
        return self

    def addImportedPath(self, original, imported):
        """Remenber that the original imported path as been imported
        with the given new one.
        """
        self.__paths[u'/'.join(original)] = u'/'.join(imported)

    def getImportedPath(self, path):
        """Return an imported path for the given original one.
        """
        return self.__paths.get(path)

    def resolveImportedPath(self, content, setter, path):
        """Resolve an imported path for a given content.
        """
        if not path:
            self.reportProblem("Missing imported path.", content)
            return

        def action():
            if path[0:5] == 'root:':
                imported_path = path[5:]
            else:
                imported_path = self.getImportedPath(canonical_path(path))
            if not imported_path:
                self.reportProblem(
                    "Refering inexisting path {0} in the import.".format(path),
                    content)
                return
            try:
                target = self.root.unrestrictedTraverse(
                    map(str, imported_path.split('/')))
            except (KeyError, AttributeError):
                self.reportProblem(
                    "Refered path {0} is not found in the import.".format(
                        imported_path),
                    content)
            else:
                setter(target)

        self.addAction(action)

    def addAction(self, action, args=[]):
        """Add an action to be executed in a later stage.
        """
        self.__actions.append((action, args))

    def runActions(self, clear=True):
        """Run scheduled actions.
        """
        for action, args in self.__actions:
            action(*args)
        if clear is True:
            del self.__actions[:]


class ZipImporter(Importer):

    def __init__(self, root, request, options=None):
        super(ZipImporter, self).__init__(root, request, options)
        self.__archive = None

    def importStream(self, stream):
        if self.__archive is not None:
            raise ValueError('Already importing')
        self.__archive = zipfile.ZipFile(stream)
        super(ZipImporter, self).importStream(
            io.BytesIO(self.__archive.read('silva.xml')))

    def getFile(self, filename):
        """Return content of a file
        """
        if self.__archive is None:
            return None
        try:
            return io.BytesIO(self.__archive.read(filename))
        except KeyError:
            return None


registry = xmlimport.Importer()
# Replace content
registry.registerOption('replace_content', False)
registry.registerOption('update_content', False)
registry.registerOption('ignore_top_level_content', False)
