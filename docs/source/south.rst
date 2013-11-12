South migrations
================

django-getpaid does not provide south migrations by itself, because it's models depend on your main project models. It means that some of getpaid models are generated on the fly and unique through each application. Therefore creating one common set of migrations is not possible.

However database migrations can be easily managed using a great feature of South module, accesible via `SOUTH_MIGRATION_MODULES <http://south.readthedocs.org/en/latest/settings.html#south-migration-modules>`_ setting.

This option allows you to overwrite default South migrations search path and create your own project dependent migrations in scope of your own project files. To setup custom migrations for your project follow these simple steps.

Step 1. Add ``SOUTH_MIGRATION_MODULES`` setting
-----------------------------------------------

You should put your custom migrations somewhere. The good place seems to be path ``PROJECT_ROOT/migrations/getpaid`` directory.

.. note::

    Remember that ``PROJECT_ROOT/migrations/getpaid`` path should be a python module, i.e. it needs to be importable from python.

Then put the following into ``settings.py``::


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

From now on, everything works like standard South migrations, with the only difference that migrations are kept in scope of your project files - not getpaid module files.

::

    $ python migrate.py schemamigration --initial getpaid


Step 3. Migrate changes on deploy
---------------------------------

Make sure to run migrate for your app containing your order model before running the getpaid migrate.

::

    $ python migrate.py schemamigration --initial orders
    $ python migrate.py migrate orders
    $ python migrate.py migrate getpaid


Step 4. Upgrading to new a version of getpaid
---------------------------------------------

When there is a new version of getpaid, you can upgrade your module by simply using South to generate custom migration::

    $ python migrate schemamigration --auto getpaid

and then::

    $ python migrate.py migrate getpaid
