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

   .. attribute:: amount_required

      Decimal value with 2 decimal places. Total value of the Order that needs to be paid.

   .. attribute:: currency

      Currency code in ISO 4217 format.

   .. attribute:: status

      Status of the Payment - one of ``PAYMENT_STATUS_CHOICES``. This field is managed using django-fsm.

   .. attribute:: backend

      Identifier of the backend processor used to handle this Payment.

   .. attribute:: created_on

      Datetime of Payment creation - automated.

   .. attribute:: last_payment_on

      Datetime the Payment has been completed. Defaults to NULL.

   .. attribute:: amount_paid

      Amount actually paid by the buyer. Should be equal amount_required if backend does not support partial payments.
      Will be smaller than that after partial refund is done.

   .. attribute:: amount_locked

      Amount that has been pre-authed by the buyer. Needs to be charged to finalize payment or released if the transaction cannot be fulfilled.

   .. attribute:: amount_refunded

      Amount that was refunded. Technically this should be equal to amount_required - amount_paid.

   .. attribute:: external_id

      ID of the payment on paywall's system. Optional.

   .. attribute:: description

      Payment description (max 128 chars).

   .. attribute:: fraud_status

      Field representing the result of fraud check (only on supported backends).

   .. attribute:: fraud_message

      Message provided along with the fraud status.
