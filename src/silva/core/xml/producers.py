# -*- coding: utf-8 -*-
# Copyright (c) 2013  Infrae. All rights reserved.
# See also LICENSE.txt


from Acquisition import aq_base
from DateTime import DateTime

from Products.Silva.ExtensionRegistry import meta_types_for_interface

from five import grok
from zope.component import getUtility
from zope.traversing.browser import absoluteURL

from silva.core.xml import NS_SILVA_CONTENT_URI, NS_SILVA_EXTRA_URI
from silva.core.interfaces import IPublication, IPublishable, INonPublishable
from silva.core.interfaces import IPublicationWorkflow
from silva.core.interfaces import ISilvaXMLExportable, ISilvaXMLProducer
from silva.core.interfaces.errors import ExternalReferenceError
from silva.core.references.interfaces import IReferenceService
from silva.core.references.reference import ReferenceSet
from silva.core.references.utils import canonical_path, relative_path
from silva.core.services.interfaces import IMetadataService
from silva.translations import translate as _
from sprout.saxext import xmlexport


class SilvaProducer(xmlexport.Producer):
    grok.baseclass()
    grok.implements(ISilvaXMLProducer)

    def get_relative_path_to(self, content):
        origin_path = self.getExported().root.get_root().getPhysicalPath()
        dest_path = content.getPhysicalPath()
        rel_path = "/".join(relative_path(origin_path, dest_path))
        return canonical_path(rel_path)

    def get_reference(self, name):
        """Return a path to refer an object in the export of a
        reference tagged name.
        """
        service = getUtility(IReferenceService)
        reference = service.get_reference(self.context, name=name)
        if reference is None:
            return None
        exported = self.getExported()
        options = self.getOptions()
        root = exported.root
        if not options.external_rendering:
            if not reference.target_id:
                # The reference is broken. Return an empty path.
                exported.reportProblem(
                    u'Content has a broken reference in the export.',
                    self.context)
                return ""
            if not reference.is_target_inside_container(root):
                if options.external_references:
                    # The reference is not inside the export, export
                    # anyway with a broken reference if the option is given.
                    exported.reportProblem(
                        u'Content refers to an another content outside of '
                        u'the export ({0}).'.format(
                            '/'.join(reference.relative_path_to(root))),
                        self.context)
                    return ""
                else:
                    raise ExternalReferenceError(
                        _(u"External references"),
                        self.context, reference.target, root)
            # Add root path id as it is always mentioned in exports
            return canonical_path('/'.join(
                    [root.getId()] + reference.relative_path_to(root)))
        # Return url to the target
        return absoluteURL(reference.target, exported.request)

    def get_references(self, name):
        ref_set = ReferenceSet(self.context, name)
        options = self.getOptions()
        exported = self.getExported()
        have_external = 0
        root = exported.root
        for reference in ref_set.get_references():
            if not options.external_rendering:
                if not reference.target_id:
                    # The reference is broken. Return an empty path.
                    yield ""
                if not reference.is_target_inside_container(root):
                    if options.external_references:
                        have_external += 1
                        continue
                    else:
                        raise ExternalReferenceError(
                            _(u"External references"),
                            self.context, reference.target, root)
                # Add root path id as it is always mentioned in exports
                path = [root.getId()] + reference.relative_path_to(root)
                yield canonical_path('/'.join(path))
            else:
                # Return url to the target
                yield absoluteURL(reference.target, exported.request)
        if have_external:
            # Report the collected problems.
            exported.reportProblem(
                (u'Content contains {0} reference(s) pointing outside ' +
                 u'of the export.').format(
                    have_external),
                self.context)

    def sax_metadata(self):
        """Export the metadata
        """
        binding = getUtility(IMetadataService).getMetadata(self.context)
        if binding is None:
            return
        # Don't acquire metadata only for the root of the xmlexport
        acquire_metadata = int(self.getExported().root is self.context)

        self.startElement('metadata')
        set_ids = binding.collection.keys()
        set_ids.sort()

        for set_id in set_ids:
            set_obj = binding.collection[set_id]
            prefix, namespace = set_obj.getNamespace()
            if (namespace != NS_SILVA_CONTENT_URI and
                namespace != NS_SILVA_EXTRA_URI):
                self.handler.startPrefixMapping(prefix, namespace)
            self.startElement('set', {'id': set_id})
            items = binding._getData(set_id, acquire=acquire_metadata).items()
            items.sort()
            for key, value in items:
                if not hasattr(aq_base(set_obj), key):
                    continue
                field = binding.getElement(set_id, key).field
                self.startElementNS(namespace, key)
                if value is not None:
                    field.validator.serializeValue(field, value, self)
                self.endElementNS(namespace, key)
            self.endElement('set')
        self.endElement('metadata')


class SilvaVersionedContentProducer(SilvaProducer):
    """Base Class for all versioned content
    """
    grok.baseclass()

    def sax_workflow(self):
        """Export the XML for the versioning workflow
        """
        options = self.getOptions()
        if not options.include_workflow:
            return

        def sax_workflow_all_versions():
            # Previewable versions.
            if not options.only_viewable:
                version = self.context.get_unapproved_version_data()
                if version[0]:
                    self.sax_workflow_version(version, 'unapproved')
                    if options.only_previewable:
                        return
                version = self.context.get_approved_version_data()
                if version[0]:
                    self.sax_workflow_version(version, 'approved')
                    if options.only_previewable:
                        return

            # Public versions
            version = self.context.get_public_version_data()
            if version[0]:
                self.sax_workflow_version(version, 'public')
                if options.only_previewable:
                    return

            # Old versions
            if not options.only_viewable:
                for version in self.context.get_previous_versions_data():
                    self.sax_workflow_version(version, 'closed')
                    if options.only_previewable:
                        return


        self.startElement('workflow')
        sax_workflow_all_versions()
        self.endElement('workflow')

    def sax_workflow_version(self, version, status):
        """Export the XML for the different workflow versions. (Right now:
        Published, Approved, Unapproved, and Closed, but to the XML these
        are arbitrary)
        """
        id, publication_datetime, expiration_datetime = version
        self.startElement('version', {'id':id})
        self.startElement('status')
        self.characters(status)
        self.endElement('status')
        self.startElement('publication_datetime')
        if publication_datetime:
            if isinstance(publication_datetime, DateTime):
                self.characters(str(publication_datetime.HTML4()))
            else:
                self.characters(unicode(str(publication_datetime)))
        self.endElement('publication_datetime')
        self.startElement('expiration_datetime')
        if expiration_datetime:
            if isinstance(expiration_datetime, DateTime):
                self.characters(str(expiration_datetime.HTML4()))
            else:
                self.characters(unicode(str(expiration_datetime)))
        self.endElement('expiration_datetime')
        self.endElement('version')

    def sax_versions(self):
        """Export the XML of the versions themselves.
        """
        options = self.getOptions()
        if options.only_viewable:
            versions = filter(None, [self.context.get_viewable()])
        elif options.only_previewable:
            versions = filter(None, [self.context.get_previewable()])
        else:
            versions = IPublicationWorkflow(self.context).get_versions()
        for version in versions:
            self.subsax(version)

    def sax_metadata(self):
        """Versioned Content has no metadata, the metadata is all on the
        versions themselves.
        """
        return


class SilvaContainerProducer(SilvaProducer):
    """Base to export a Silva container to XML.
    """
    grok.baseclass()

    def sax_contents(self):
        options = self.getOptions()
        self.startElement('content')
        if not options.only_container:
            default = self.context.get_default()
            if default is not None:
                self.startElement('default')
                self.subsax(default)
                self.endElement('default')
            for content in self.context.get_ordered_publishables():
                if (IPublication.providedBy(content) and
                    not options.include_publications):
                    continue
                self.subsax(content)
            for content in self.context.get_non_publishables():
                self.subsax(content)
            if options.other_contents:
                meta_types = meta_types_for_interface(
                    ISilvaXMLExportable,
                    excepts=[IPublishable, INonPublishable])
                for content in self.context.objectValues(meta_types):
                    self.subsax(content)
        self.endElement('content')


class ZexpProducer(SilvaProducer):
    """Export any unknown content type to a zexp in the zip-file.
    """
    grok.baseclass()

    def sax(self):
        exported = self.getExported()
        path = self.context.getPhysicalPath()
        id = self.context.getId()
        meta_type = getattr(aq_base(self.context), 'meta_type', '')
        self.startElement(
            'unknown_content',
            {'id': id, 'meta_type': meta_type})
        exported.addZexpPath(path)
        self.startElement('zexp', {'id': exported.getZexpPathId(path)})
        self.endElement('zexp')
        self.endElement('unknown_content')


class ExporterProducer(xmlexport.BaseProducer):

    def get_relative_path_to(self, content):
        return canonical_path(
            "/".join(
                [self.getExported().root.getId()] +
                relative_path(
                    self.getExported().rootPath,
                    content.getPhysicalPath())))

    def sax(self):
        self.startElement(
            'silva',
            {'silva_version': self.context.getVersion()})
        self.subsax(self.context.root)
        for problem, content in self.getExported().getProblems():
            self.startElement(
                'problem',
                {'path': self.get_relative_path_to(content)})
            self.characters(problem)
            self.endElement('problem')
        self.endElement('silva')
