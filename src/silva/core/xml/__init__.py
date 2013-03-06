# -*- coding: utf-8 -*-
# Copyright (c) 2013  Infrae. All rights reserved.
# See also LICENSE.txt
# This is a package.


NS_SILVA_URI = 'http://infrae.com/namespace/silva'
NS_SILVA_CONTENT_URI = 'http://infrae.com/namespace/metadata/silva-content'
NS_SILVA_EXTRA_URI = 'http://infrae.com/namespace/metadata/silva-extra'

from silva.core.xml.xmlexport import Exporter, registerOption, registerNamespace
from silva.core.xml.xmlimport import Importer, ZipImporter

__all__ = ['Exporter', 'Importer', 'ZipImporter',
           'registerOption', 'registerNamespace']
