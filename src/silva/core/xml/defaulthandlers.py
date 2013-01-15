
from five import grok
from silva.core import conf as silvaconf
from silva.core.xml import NS_SILVA_URI, handlers


silvaconf.namespace(NS_SILVA_URI)


class ProblemHandler(handlers.BaseHandler):
    """Collect a problem that is given in the XML.
    """
    _path = None
    _message = None

    def startElementNS(self, name, qname, attrs):
        if name == (NS_SILVA_URI, 'problem'):
            self._path = attrs.get((None, 'path'), '')
            self._message = []

    def characters(self, chars):
        if self._message is not None:
            self._message.append(chars)

    def endElementNS(self, name, qname):
        if name == (NS_SILVA_URI, 'problem'):
            imported = self.getExtra()
            message = ''.join(self._message).strip()

            def report(content):
                imported.reportProblem(message, content)

            imported.resolveImportedPath(imported.root, report, self._path)


class SilvaExportRootHandler(handlers.SilvaHandler):
    """This handler is used for the main tag of an Silva-XML file.
    """
    grok.name('silva')

    def getOverrides(self):
        return {
            (NS_SILVA_URI, 'problem'): ProblemHandler
            }

    def getResultPhysicalPath(self):
        return []

    def getOriginalPhysicalPath(self):
        return []


class VersionHandler(handlers.SilvaHandler):
    """Collect version information.
    """
    grok.name('version')

    def getOverrides(self):
        return {
            (NS_SILVA_URI, 'status'):
                self.handlerFactories.contentHandler('status'),
            (NS_SILVA_URI, 'publication_datetime'):
                self.handlerFactories.contentHandler('publication_datetime'),
            (NS_SILVA_URI, 'expiration_datetime'):
                self.handlerFactories.contentHandler('expiration_datetime'),
            }

    def startElementNS(self, name, qname, attrs):
        if name == (NS_SILVA_URI, 'version'):
            self.setData('id', attrs[(None, 'id')])

    def endElementNS(self, name, qname):
        self.setWorkflowVersion(
            self.getData('id'),
            self.getData('publication_datetime'),
            self.getData('expiration_datetime'),
            self.getData('status'))


class MetadataSetHandler(handlers.SilvaHandler):
    grok.name('set')
    _value = None

    def startElementNS(self, name, qname, attrs):
        parent = self.parentHandler()
        if name == (NS_SILVA_URI, 'set'):
            parent.setMetadataSet(attrs[(None, 'id')])
        elif name != (NS_SILVA_URI, 'value'):
            parent.setMetadataKey(name[1])
        else:
            parent.setMetadataMultiValue(True)
        self.setResult(None)

    def characters(self, chars):
        if self.parentHandler().metadataKey() is not None:
            self._value = chars.strip()

    def endElementNS(self, name, qname):
        parent = self.parentHandler()
        if name != (NS_SILVA_URI, 'set'):
            if parent.metadataKey() is not None:
                parent.setMetadata(
                    parent.metadataSet(),
                    parent.metadataKey(),
                    self._value)
        if name != (NS_SILVA_URI, 'value'):
            parent.setMetadataKey(None)
            parent.setMetadataMultiValue(False)
        self._value = None
