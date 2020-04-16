.. :changelog:

History
=======

Version 2.0.0 (in development)
------------------------------

* BREAKING: Complete redesign of internal APIs.
* Supports only Django 2.2+ and Python 3.6+
* Payment and Order became swappable models - like Django's User model
* Payment acts as customizable interface to PaymentProcessor instances (but be careful).
* Payment statuses guarded with django-fsm
* Broker plugins separated from main repo - easier updates.


See :doc:`prehistory <HISTORY_OLD>`
