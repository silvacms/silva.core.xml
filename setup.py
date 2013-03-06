# -*- coding: utf-8 -*-
# Copyright (c) 2002-2013 Infrae. All rights reserved.
# See also LICENSE.txt

from setuptools import setup, find_packages
import os

version = '3.0.1dev'

tests_require = [
    'Products.Silva [test]',
    ]


setup(name='silva.core.xml',
      version=version,
      description="Support to export Silva content into XML",
      long_description=open("README.txt").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.txt")).read(),
      classifiers=[
              "Framework :: Zope2",
              "License :: OSI Approved :: BSD License",
              "Programming Language :: Python",
              "Topic :: Software Development :: Libraries :: Python Modules",
              ],
      keywords='silva core xml export import',
      author='Infrae',
      author_email='info@infrae.com',
      license='BSD',
      package_dir={'': 'src'},
      packages=find_packages('src'),
      namespace_packages=['silva', 'silva.core'],
      url='http://infrae.com/products/silva',
      include_package_data=True,
      zip_safe=False,
      install_requires=[
        'five.grok',
        'setuptools',
        ],
      tests_require = tests_require,
      extras_require = {'test': tests_require},
      entry_points="""
      """,
      )
