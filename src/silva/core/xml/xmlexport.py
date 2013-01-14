
import os

from Products.Silva.ExtensionRegistry import extensionRegistry
from sprout.saxext import xmlexport
from zope.cachedescriptors.property import Lazy

from silva.core.xml import NS_SILVA_URI
from silva.core.xml import NS_SILVA_EXTRA_URI, NS_SILVA_CONTENT_URI
from silva.core.xml import producers


class Exporter(object):

    def __init__(self, root, request, options=None):
        self.__root = root
        self.__request = request
        self.__string = None
        self.__stream = None
        self.__executed = False
        self.__executing = False
        self.options = options

        self._problems = []
        self._asset_paths = {}
        self._zexp_paths = {}
        self._last_asset_id = 0
        self._last_zexp_id = 0

    def getString(self):
        if not self.__executed:
            if self.__executing:
                raise AssertionError('Currently exporting')
            self.__executing = True
            self.__string = registry.exportToString(
                self, self.options, extra=self)
            self.__executed = True
        return self.__string

    def getStream(self):
        if not self.__executed:
            if self.__executing:
                raise AssertionError('Currently exporting')
            self.__stream = registry.exportToTemporary(
                self, self.options, extra=self)
            self.__executed = True
        return self.__stream

    def getVersion(self):
        return 'Silva %s' % extensionRegistry.get_extension('Silva').version

    @Lazy
    def root(self):
        return self.__root

    @Lazy
    def rootPath(self):
        return self.root.getPhysicalPath()

    @Lazy
    def request(self):
        return self.__request

    def addAssetPath(self, path):
        identifier = self._makeUniqueAssetId(path)
        self._asset_paths[path] = identifier
        return identifier

    def getAssetPathId(self, path):
        return self._asset_paths[path]

    def getAssetPaths(self):
        return self._asset_paths.items()

    def _makeUniqueAssetId(self, path):
        base, ext = os.path.splitext(path[-1])
        self._last_asset_id += 1
        return str(self._last_asset_id) + ext

    def addZexpPath(self, path):
        identifier = self._makeUniqueZexpId(path)
        self._zexp_paths[path] = identifier
        return identifier

    def getZexpPathId(self, path):
        return self._zexp_paths[path]

    def getZexpPaths(self):
        return self._zexp_paths.items()

    def _makeUniqueZexpId(self, path):
        self._last_zexp_id += 1
        return str(self._last_zexp_id) + '.zexp'

    def reportProblem(self, problem, content=None):
        self._problems.append((problem, content))

    def getProblems(self):
        return list(self._problems)


# Registry
registry = xmlexport.Exporter(NS_SILVA_URI)
registry.registerNamespace('silva-content', NS_SILVA_CONTENT_URI)
registry.registerNamespace('silva-extra', NS_SILVA_EXTRA_URI)
registry.registerProducer(Exporter, producers.ExporterProducer)
registry.registerFallbackProducer(producers.ZexpProducer)
# Generate URL instead of paths
registry.registerOption('external_rendering', False)
# Export sub publications
registry.registerOption('include_publications', True)
# Export other contents
registry.registerOption('other_contents', True)
# Export only viewable
registry.registerOption('only_viewable', False)
# Export only previewable
registry.registerOption('only_previewable', False)
# Export workflow information
registry.registerOption('include_workflow', True)
registry.registerOption('external_references', False)


# Shortcuts
registerOption = registry.registerOption
registerNamespace = registry.registerNamespace
