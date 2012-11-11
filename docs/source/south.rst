South migrations
================

django-getpaid does not provide south migrations by itself, because its models depend on your main project models. It means that some of getpaid models are generated on the fly and unique through each application. Therefore creating one common set of migrations is not possible.

However database migrations can be easily managed using a great feature of South module, accesible via `SOUTH_MIGRATION_MODULES <http://south.readthedocs.org/en/latest/settings.html#south-migration-modules>`_ setting.

This option allows you to overwrite default South migrations search path and create your own project dependent migrations in scope of your own project files. To setup custom migrations for your project follow simple steps.

Step 1. Add ``SOUTH_MIGRATION_MODULES`` setting
-----------------------------------------------

You should put somewhere your custom migrations. The good place seems to be path ``PROJECT_ROOT/migrations/plans`` directory.

.. note::

    Remember that ``PROJECT_ROOT/migrations/plans`` path should be a python module, i.e. it needs to be importable from python.

Than put following into ``settings.py``::


    SOUTH_MIGRATION_MODULES = {
        'getpaid' : 'yourproject.migrations.getpaid',
    }


you can also track migrations for particular backends::

    SOUTH_MIGRATION_MODULES = {
        'getpaid' : 'yourproject.migrations.getpaid',
        'payu' : 'yourproject.migrations.getpaid_payu',
    }

Step 2. Create initial migration
--------------------------------

From here now, everything works like standard South migrations, with the only difference that migrations are kept in scope of your project files - not getpaid module files.

::

    $ python migrate.py schemamigration --initial getpaid


Step 3. Migrate changes on deploy
---------------------------------

::

    $ python migrate.py migrate getpaid



Step 4. Upgrading to new version of getpaid
-------------------------------------------

When there will be new versions of getpaid in future, you can upgrade your module and simply use South to generate custom migration::

    $ python migrate schemamigration --auto getpaid

and then::

    $ python migrate.py migrate getpaid