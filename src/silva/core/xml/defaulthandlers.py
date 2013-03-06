# -*- coding: utf-8 -*-
# Copyright (c) 2013  Infrae. All rights reserved.
# See also LICENSE.txt

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

    def __init__(self, *args, **kwargs):
        super(MetadataSetHandler, self).__init__(*args, **kwargs)
        self._set = None
        self._key = None
        self._metadata = {}
        self._value = None
        self._multiple = False

    def startElementNS(self, name, qname, attrs):
        if name == (NS_SILVA_URI, 'set'):
            self._set = attrs[(None, 'id')]
        elif name != (NS_SILVA_URI, 'value'):
            self._key = name[1]
        else:
            self._multiple = True

    def characters(self, chars):
        if self._key is not None:
            self._value = chars.strip().encode('utf-8')

    def endElementNS(self, name, qname):
        if name == (NS_SILVA_URI, 'set'):
            assert self._set is not None
            if self._metadata:
                parent = self.parentHandler()
                parent.setMetadata(self._set, self._metadata)
        else:
            assert self._key is not None
            if name != (NS_SILVA_URI, 'value'):
                if not self._multiple:
                    # Single value, we have to set the value.
                    if self._value:
                        self._metadata[self._key] = self._value
                self._key = None
                self._multiple = False
            else:
                # Multi value, we append the value to existing ones.
                if self._value:
                    if self._key not in self._metadata:
                        self._metadata[self._key] = []
                    self._metadata[self._key].append(self._value)
            # Clear value
            self._value = None
