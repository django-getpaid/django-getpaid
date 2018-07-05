=====
Usage
=====

To use django-getpaid in a project, add it to your `INSTALLED_APPS`:

.. code-block:: python

    INSTALLED_APPS = (
        ...
        'getpaid.apps.GetpaidConfig',
        ...
    )

Add django-getpaid's URL patterns:

.. code-block:: python

    from getpaid import urls as getpaid_urls


    urlpatterns = [
        ...
        url(r'^', include(getpaid_urls)),
        ...
    ]
