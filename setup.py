#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from setuptools import setup
import re
import os
import sys


name = 'shareabouts'
package = 'shareabouts'
description = 'A Python library for interacting with a Shareabouts API server'
url = 'https://github.com/openplans/pyshareabouts'
author = 'OpenPlans'
author_email = 'mjumbewu@gmail.com'
license = 'BSD'
dependency_links = []
install_requires = ['requests>=1.2']


def rel_path(path):
    cur_dir = os.path.dirname(__file__)
    return os.path.join(cur_dir, path)


def get_version(package):
    """
    Return package version as listed in `__version__` in `init.py`.
    """
    module_path = rel_path('.'.join([package, 'py']))
    if not os.path.isfile(module_path):
        module_path = os.path.join(rel_path(package), '__init__.py')

    content = open(module_path).read()
    return re.search("^__version__ = ['\"]([^'\"]+)['\"]",
                     content, re.MULTILINE).group(1)


def get_packages(package):
    """
    Return root package and all sub-packages.
    """
    return [dirpath
            for dirpath, dirnames, filenames in os.walk(package)
            if os.path.exists(os.path.join(dirpath, '__init__.py'))]


def get_package_data(package):
    """
    Return all files under the root package, that are not in a
    package themselves.
    """
    walk = [(dirpath.replace(package + os.sep, '', 1), filenames)
            for dirpath, dirnames, filenames in os.walk(package)
            if not os.path.exists(os.path.join(dirpath, '__init__.py'))]

    filepaths = []
    for base, filenames in walk:
        filepaths.extend([os.path.join(base, filename)
                          for filename in filenames])
    return {package: filepaths}


if sys.argv[-1] == 'publish':
    os.system("python setup.py sdist upload")
    args = {'version': get_version(package)}
    print("You probably want to also tag the version now:")
    print("  git tag -a %(version)s -m 'version %(version)s'" % args)
    print("  git push --tags")
    sys.exit()


setup(
    name=name,
    version=get_version(package),
    url=url,
    license=license,
    description=description,
    author=author,
    author_email=author_email,
    packages=get_packages(package),
    package_data=get_package_data(package),
    dependency_links=dependency_links,
    install_requires=install_requires,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
    ],
)
