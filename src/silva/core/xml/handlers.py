
import logging

from five import grok
from sprout.saxext import xmlimport
from zope.event import notify

from DateTime import DateTime

from silva.core.xml import NS_SILVA_URI
from silva.core.interfaces import ISilvaXMLHandler, ContentImported


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



class SilvaHandler(xmlimport.BaseHandler):
    """Base class to writer an XML importer for a Silva content. It
    provides helpers to set Silva properties and metadatas.
    """
    grok.baseclass()
    grok.implements(ISilvaXMLHandler)

    def __init__(self, parent, parent_handler, options=None, extra=None):
        super(SilvaHandler, self).__init__(parent, parent_handler, options, extra)
        self.handlerFactories = DynamicHandlers(self)
        self._metadata_set = None
        self._metadata_key = None
        self._metadata = {}
        self._metadata_multivalue = False
        self._workflow = {}
        self.__id_result = None
        self.__id_original = None

    # MANIPULATORS

    def notifyImport(self):
        """Notify the event system that the content have been
        imported. This must be the last item done.
        """
        importer = self.getExtra()
        importer.addAction(notify, [ContentImported(self.result())])
        importer.addImportedPath(
            self.getOriginalPhysicalPath(),
            self.getResultPhysicalPath())

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
        path.append(self.__id_result)
        return path

    def getOriginalPhysicalPath(self):
        parent = self.parentHandler()
        if parent is None:
            return []
        path = parent.getOriginalPhysicalPath()
        path.append(self.__id_original or self.__id_result)
        return path

    # Metadata helpers
    def setMetadataKey(self, key):
        self._metadata_key = key

    def setMetadata(self, set, key, value):
        if value is not None:
            value = value.encode('utf-8')
            if self.metadataMultiValue():
                if self._metadata[set].has_key(key):
                    self._metadata[set][key].append(value)
                else:
                    self._metadata[set][key] = [value]
            else:
                self._metadata[set][key] = value

    def setMetadataSet(self, set):
        self._metadata_set = set
        self._metadata[set] = {}

    def setMetadataMultiValue(self, trueOrFalse):
        self._metadata_multivalue = trueOrFalse

    def storeMetadata(self):
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

        self.parentHandler()._workflow[version_id.strip()] = (
            parse_date(publication_time),
            parse_date(expiration_time),
            status)

    def getWorkflowVersion(self, version_id):
        return self.parentHandler()._workflow[version_id]

    def storeWorkflow(self):
        content = self.result()
        version_id = content.id
        publicationtime, expirationtime, status = self.getWorkflowVersion(
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

    # ACCESSORS

    def metadataKey(self):
        return self._metadata_key

    def metadataSet(self):
        return self._metadata_set

    def getMetadata(self, set, key):
        return self._metadata[set].get(key)

    def metadataMultiValue(self):
        return self._metadata_multivalue

    def generateIdentifier(self, attrs, key='id', namespace=None):
        identifier = attrs.get((namespace, key), None)
        if identifier is None:
            raise ValueError
        identifier = identifier.encode('utf-8')
        parent = self.parent()
        existing = parent.objectIds()
        self.setOriginalId(identifier)
        if self.getOptions().replace:
            if identifier in existing:
                parent.manage_delObjects([identifier])
            return identifier
        # Find a new id
        test = 0
        original = identifier
        while identifier in existing:
            test += 1
            add = ''
            if test > 1:
                add = str(test)
            identifier = 'import%s_of_%s' % (add, original)
        return identifier


class SilvaVersionHandler(SilvaHandler):

    def updateVersionCount(self):
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
