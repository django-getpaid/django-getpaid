.. :changelog:

History
=======

(master branch - current development)
-------------------------------------



Version 1.8.0 (2018-07-04)
--------------------------

* Updated project structure thanks to cookiecutter-djangopackage
* Dropped support for Django < 1.11
* Provide support for Django 2.0


Version 1.7.5
-------------
* Fixed przelewy24 params (py3 support)

Version 1.7.4
-------------
* Added default apps config getpaid.apps.Config
* Fixed and refactoring for utils.get_domain, build_absolute_uri,
 settings.GETPAID_SITE_DOMAIN
* Refactored register_to_payment
* Refactored build_absolute_uri
* Refactored and fixes in transferuj backend
 - payment.paid_on uses local TIMEZONE now as opposed to UTC
 - changed params
 - add post method to SuccessView and FailureView
* Added test models factories
* Dropped support for Django <=1.6

Version 1.7.3
-------------
* Refactored Dotpay
* Moved all existing tests to test_project and added more/refactored
* Fixed utils.import_module
* Fixed Payu and tests (py3 support)
* Updated docs

Version 1.7.2
-------------
* Updated coveragerc and travis.yml
* Added missing mgiration for Payment.status

Version 1.7.1
-------------
* Added coveragerc
* Updated README
* Added settings.GETPAID_ORDER_MODEL
* Added epay.dk support
* Added initial django migration

Version 1.7.0
-------------
* Refactoring to support for py3 (3.4)
* Change imports to be relative - fixes #43
* Add USD to supported currencies in Paymill backend (thanks lauris)
* Fix a few typos

Version 1.6.0
-------------
* Adding paymill backend
* PEP 8 improvements
* Adding support for django 1.5 in test project (+ tests)
* Fixed issue on `utils.import_name` to allow packages without parents
* Adding dependency to pytz for przelewy24 backend
* Refactoring of PayU backend (xml->txt api, better logging) and adding support for non-auto payment accepting

Version 1.5.1
-------------
* Fixing packaging that causes errors with package installation

Version 1.5.0
-------------
* Adding new backend - Przelewy24.pl (thanks to IssueStand.com funding)
* Fixing packaging package data (now using only MANIFEST.in)

Version 1.4.0
-------------
* Cleaned version 1.3 from minor issues before implementing new backends
* Brazilian backend moip
* Updated PL translation
* Added brazilian portuguese translation
* Storing payment external id and description in the database (warning: database migration needed!)
* Transferuj backend can now predefine interface language when redirecting
* POST method supported on redirect to payment

Version 1.3.0
-------------
* Logotypes support in new payment form
* Fixing packaging

Version 1.2
-----------
* Dotpay backend added
* Hooks for backends to accept email and user name
* Refactoring


Version 1.1
-----------
* PayU backend added
* Lots of documentation
* Refactoring

Version 1.0
-----------
* First stable version
