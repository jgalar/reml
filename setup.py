#!/usr/bin/env python3

import pkg_resources
import pathlib
from pip._internal.req import parse_requirements
from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

with pathlib.Path('requirements/prod.txt').open() as prod_reqs_txt:
    prod_requirements = [
        str(requirement)
        for requirement in pkg_resources.parse_requirements(prod_reqs_txt)
    ]

with pathlib.Path('requirements/dev.txt').open() as dev_reqs_txt:
    dev_requirements = prod_requirements + [
        str(requirement)
        for requirement in pkg_resources.parse_requirements(dev_reqs_txt)
    ]

with pathlib.Path('requirements/test.txt').open() as test_reqs_txt:
    test_requirements = prod_requirements + [
        str(requirement)
        for requirement in pkg_resources.parse_requirements(test_reqs_txt)
    ]


setup(
    author='Jérémie Galarneau',
    author_email='jeremie.galarneau@gmail.com',
    python_requires='>=3.5',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    description='A release manager for LTTng and Babeltrace',
    entry_points={'console_scripts': ['reml=reml.cli:main',],},
    install_requires=prod_requirements,
    license='MIT license',
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='reml',
    name='reml',
    packages=find_packages(include=['reml', 'reml.*']),
    setup_requires=dev_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/jgalar/reml',
    version='0.1.0',
    zip_safe=False,
)
