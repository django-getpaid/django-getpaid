Welcome to django-getpaid's documentation!
==========================================

**django-getpaid** is a multi-broker payment processor for Django. Main features include:

* support for multiple payment brokers at the same time
* very flexible architecture
* support for asynchronous status updates - both push and pull
* support for modern REST-based broker APIs
* support for multiple currencies (but one per payment)
* support for global and per-plugin validators
* easy customization with provided base abstract models and swappable mechanic (same as with Django's User model)

We would like to provide a :doc:`catalog<catalog>` of plugins for ``django-getpaid`` - if you create a plugin please let us know.

**Disclaimer:** this project has nothing in common with `getpaid <http://code.google.com/p/getpaid/>`_ plone project.

This project uses `semantic versioning <http://semver.org/>`_.

Contents:
=========

.. toctree::
   :maxdepth: 1

   installation
   catalog
   settings
   customization
   plugins
   registry
   roadmap
   changelog


Development team
================

Project leader:

* Dominik Kozaczko <https://github.com/dekoza>

Original author:

* Krzysztof Dorosz <https://github.com/cypreess>.

Contributors:

* Paweł Bielecki <https://github.com/pawciobiel>
* Bernardo Pires Carneiro <https://github.com/bcarneiro>

Sponsors:

* `Sunscrapers <https://sunscrapers.com/>`_

You are welcome to contribute to this project via `github <http://github.com>`_ fork & pull request.


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
