===========================
Customization - Payment API
===========================

.. py:currentmodule:: getpaid.models

Django-getpaid was designed to be very customizable. In this document you'll
read about the Payment API which lets you customize most of the mechanics
of ``django-getpaid``.

Since most Payment methods act as interface to PaymentProcessor, you can use
this to add extra layer between the Payment and the PaymentProcessor.

Basic Order API
===============


.. autoclass:: AbstractOrder
   :members:



Basic Payment API
=================


:class:`AbstractPayment` defines a minimal set of fields that are expected by
:class:`~getpaid.processor.BaseProcessor` API. If you want to have it completely your own way, make sure
to provide properties linking your fieldnames to expected names.

.. autoclass:: AbstractPayment
   :members:

   .. attribute:: id

      UUID to not disclose your volume.

   .. attribute:: order

      ForeignKey to (swappable) Order model.

   .. attribute:: amount

      Decimal value with 4 decimal places. Total value of the Order.

   .. attribute:: currency

      Currency code in ISO 4217 format.

   .. attribute:: status

      Status of the Payment - one of ``PAYMENT_STATUS_CHOICES``

   .. attribute:: backend

      Identifier of the backend processor used to handle this Payment.

   .. attribute:: created_on

      Datetime of Payment creation - automated.

   .. attribute:: paid_on

      Datetime the Payment has been completed. Defaults to NULL.

   .. attribute:: amount_paid

      Amount paid for backends supporting partial payments.

   .. attribute:: external_id

      ID of the payment on broker's system. Optional.

   .. attribute:: description

      Payment description (max 128 chars).

