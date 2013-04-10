# -*- coding: utf-8 -*-
# Copyright (c) 2002-2013 Infrae. All rights reserved.
# See also LICENSE.txt

import martian

from silva.core.xml import handlers
from silva.core.xml.xmlimport import registry
from silva.core import conf as silvaconf


class ImporterGrokker(martian.ClassGrokker):
    """Collect importer for contents.
    """
    martian.component(handlers.RegisteredHandler)
    martian.directive(silvaconf.namespace)
    martian.directive(silvaconf.name)
    martian.priority(200)

    def execute(self, importer, namespace, name=None, **kw):
        if not name:
            return False
        registry.registerHandler((namespace, name), importer)
        return True
