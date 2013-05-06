# -*- coding: utf-8 -*-
# Copyright (c) 2013  Infrae. All rights reserved.
# See also LICENSE.txt

import logging

from five import grok
from sprout.saxext.xmlimport import BaseHandler
from zope.event import notify

from DateTime import DateTime

from silva.core.xml import NS_SILVA_URI
from silva.core.interfaces import ISilvaXMLHandler, ContentImported
from silva.core.interfaces import ISilvaObject, IVersion


logger = logging.getLogger('silva.core.xml')


def parse_date(date):
    if date:
        return DateTime(date)
    return None


class DynamicHandlers(object):

    def __init__(factory, handler):
        factory._handler = handler

    def tagHandler(factory, tag, namespace=NS_SILVA_URI):

        class IdentifierHandler(SilvaHandler):

            def startElementNS(self, name, qname, attrs):
                if name == (namespace, tag):
                    factory._handler.setData(tag, attrs[(None, 'id')])

        return IdentifierHandler

    def contentHandler(factory, name):

        class CharacterHandler(SilvaHandler):

            def characters(self, chars):
                return factory._handler.setData(name, chars.strip())

        return CharacterHandler


class RegisteredHandler(BaseHandler):
    """Base class to define an XML importer for a generic tag.
    """
    grok.baseclass()

    def __init__(self, parent, parent_handler, options=None, extra=None):
        super(RegisteredHandler, self).__init__(parent, parent_handler, options, extra)
        self.handlerFactories = DynamicHandlers(self)


class Handler(RegisteredHandler):
    """Base class to defined an XML importer for a Silva content. It
    provides helpers to set Silva properties and metadatas.
    """
    grok.baseclass()
    grok.implements(ISilvaXMLHandler)

    def __init__(self, parent, parent_handler, options=None, extra=None):
        super(Handler, self).__init__(parent, parent_handler, options, extra)
        self._metadata = {}
        self._workflow = {}
        self.__id_result = None
        self.__id_original = None

    # MANIPULATORS

    def notifyImport(self):
        """Notify the event system that the content have been
        imported. This must be the last item done.
        """
        if not self.resultIsImported():
            # The result was not created here.
            return
        importer = self.getExtra()
        importer.addAction(notify, [ContentImported(self.result())])
        importer.addImportedPath(
            self.getOriginalPhysicalPath(),
            self.getResultPhysicalPath())

    def resultIsImported(self):
        return self.__id_result is not None

    def setResultId(self, identifier):
        self.__id_result = identifier
        return self.setResult(self.parent()._getOb(identifier))

    def setOriginalId(self, identifier):
        self.__id_original = identifier

    def getResultPhysicalPath(self):
        parent = self.parentHandler()
        if parent is None:
            return []
        path = parent.getResultPhysicalPath()
        trail = self.__id_result
        if trail is not None:
            path.append(trail)
        return path

    def getOriginalPhysicalPath(self):
        parent = self.parentHandler()
        if parent is None:
            return []
        path = parent.getOriginalPhysicalPath()
        trail = self.__id_original or self.__id_result
        if trail is not None:
            path.append(trail)
        return path

    def isTopLevelHandler(self):
        return False

    # Metadata helpers
    def setMetadata(self, key, values):
        assert isinstance(values, dict)
        self._metadata[key] = values

    def getMetadata(self, set, key):
        return self._metadata[set].get(key)

    def storeMetadata(self):
        if not self.resultIsImported():
            return
        content = self.result()
        metadata_service = content.service_metadata
        binding = metadata_service.getMetadata(content)
        if binding is not None and not binding.read_only:
            set_names = binding.getSetNames()
            for set_id, elements in self._metadata.items():
                if set_id not in set_names:
                    logger.warn(
                        u"Unknown metadata set %s present in import file.",
                        set_id)
                    continue
                element_names = binding.getElementNames(set_id, mode='write')
                values = {}
                for element_id, element in elements.iteritems():
                    if element_id not in element_names:
                        logger.warn(
                            u"Unknown metadata element %s in set %s present "
                            u"in import file.",
                            element_id, set_id)
                        continue
                    field = binding.getElement(set_id, element_id).field
                    values[element_id] = field.validator.deserializeValue(
                        field, elements[element_id], self)

                if values:
                    errors = binding.setValues(set_id, values, reindex=0)
                    if errors:
                        logger.warn(u"Error saving metadata for set %s "
                                    u"from import file.", set_id)

    # Workflow helpers
    def setWorkflowVersion(
        self, version_id, publication_time, expiration_time, status):
        self._workflow[version_id.strip()] = (
            parse_date(publication_time),
            parse_date(expiration_time),
            status)

    def getWorkflowVersion(self, version_id):
        info = self._workflow.get(version_id)
        if info is None:
            # The information is missing, create a problem and return
            # a closed information.
            importer = self.getExtra()
            importer.reportProblem(
                u'Missing workflow information for version {0}.'.format(
                    version_id),
                self.result())
            return (DateTime() - 1, None, 'closed')
        return info


class SilvaHandler(Handler):
    grok.baseclass()

    def _createContent(self, identifier, **options):
        raise NotImplementedError

    def _verifyContent(self, content):
        return ISilvaObject.providedBy(content)

    def _readOriginalIdentifier(self, attrs, key='id', namespace=None):
        identifier = attrs.get((namespace, key), None)
        if identifier is None:
            raise ValueError('Identifier is missing from the attributes')
        identifier = identifier.encode('utf-8')
        self.setOriginalId(identifier)
        return identifier

    def _generateIdentifier(self, attrs, key='id', namespace=None):
        options = self.getOptions()
        parent = self.parent()
        identifier = self._readOriginalIdentifier(attrs, key, namespace)
        existing = parent.objectIds()
        if options.replace_content:
            if identifier in existing:
                parent.manage_delObjects([identifier])
            return (identifier, False)
        if options.update_content:
            if identifier in existing:
                if self._verifyContent(parent._getOb(identifier)):
                    # Reuse the content only if it match or create a new one.
                    return (identifier, True)
        # Find a new id
        test = 0
        original = identifier
        while identifier in existing:
            test += 1
            add = ''
            if test > 1:
                add = str(test)
            identifier = 'import%s_of_%s' % (add, original)
        return (identifier, False)

    def createContent(self, attrs, key='id', namespace=None, options={}):
        identifier, exists = self._generateIdentifier(attrs, key, namespace)
        if not exists:
            self._createContent(identifier, **options)
        return self.setResultId(identifier)

    def generateIdentifier(self, attrs, key='id', namespace=None):
        identifier, exists = self._generateIdentifier(attrs, key, namespace)
        assert exists is False
        return identifier


class SilvaContainerHandler(SilvaHandler):

    def createContent(self, attrs, key='id', namespace=None, options={}):
        parent = self.parentHandler()
        is_top_level = parent.isTopLevelHandler()
        if self.getOptions().ignore_top_level_content and is_top_level:
            self._readOriginalIdentifier(attrs, key, namespace)
            return self.setResult(parent.result())
        return super(SilvaContainerHandler, self).createContent(
            attrs, key, namespace, options)


class SilvaVersionHandler(Handler):
    grok.baseclass()

    def _createVersion(self, identifier, **options):
        raise NotImplementedError

    def createVersion(self, attrs, key='version_id', namespace=None, **opts):
        options = self.getOptions()
        identifier = attrs.get((namespace, key), None)
        if identifier is None:
            raise ValueError('Version identifier is missing')
        identifier = identifier.encode('utf-8')
        create = True
        parent = self.parent()
        existing = parent.objectIds()
        self.setOriginalId(identifier)
        if options.replace_content:
            if identifier in existing:
                parent.manage_delObjects([identifier])
        if options.update_content:
            if identifier in existing:
                create = False
        if create:
            self._createVersion(identifier, **opts)
        version = self.setResultId(identifier)
        assert IVersion.providedBy(version)
        return version

    def storeWorkflow(self):
        if not self.resultIsImported():
            return
        content = self.result()
        parent = self.parentHandler()
        version_id = content.id
        publicationtime, expirationtime, status = parent.getWorkflowVersion(
            version_id)
        version = (version_id, publicationtime, expirationtime)
        if status == 'unapproved':
            self.parent()._unapproved_version = version
        elif status == 'approved':
            self.parent()._approved_version = version
        elif status == 'public':
            self.parent()._public_version = version
        else:
            previous_versions = self.parent()._previous_versions or []
            previous_versions.append(version)
            self.parent()._previous_versions = previous_versions

    def updateVersionCount(self):
        if not self.resultIsImported():
            return
        importer = self.getExtra()
        importer.addImportedPath(
            self.getOriginalPhysicalPath(),
            self.getResultPhysicalPath())
        # The parent of a version is a VersionedContent object. This VC object
        # has an _version_count attribute to keep track of the number of
        # existing version objects and is the used to determine the id for a
        # new version. However, after importing, this _version_count has the
        # default value (1) and thus should be updated to reflect the highest
        # id of imported versions (+1 of course :)
        parent = self.parent()
        version = self.result()
        id = version.id
        try:
            id = int(id)
        except ValueError:
            # I guess this is the only reasonable thing to do - apparently
            # this id does not have any numerical 'meaning'.
            return
        vc = max(parent._version_count, (id + 1))
        parent._version_count = vc

