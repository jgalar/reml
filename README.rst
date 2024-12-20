====
reml
====


.. image:: https://img.shields.io/pypi/v/reml.svg
        :target: https://pypi.python.org/pypi/reml

.. image:: https://img.shields.io/travis/jgalar/reml.svg
        :target: https://travis-ci.com/jgalar/reml

.. image:: https://readthedocs.org/projects/reml/badge/?version=latest
        :target: https://reml.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status




A release manager for LTTng and Babeltrace


* Free software: MIT license
* Documentation: https://reml.readthedocs.io.


Features
--------

* TODO

Usage
-----

Create a configuration file for the project(s) at `~/.config/reml/reml.conf`:

.. code-block:: ini

    [project_name]
      git_urls=...
      ci_url=...
      ci_user=...
      ci_token=...
      github_user=...
      github_token=...
      upload_location=...


To create a GitHub access token, please refer to `their documentation <https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens>`_.

Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
