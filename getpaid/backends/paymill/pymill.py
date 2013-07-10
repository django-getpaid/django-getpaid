#! /usr/bin/env python
# -*- coding: utf-8 -*-
#pymill.py
# From https://github.com/kliment/pymill since it's not on PyPi

import requests


class Pymill():
    """
    These are the parameters each object type contains

    Payment:
    id: unique payment method ID
    type: creditcard or debit
    client: id of associatied client (optional)
    created_at: unixtime
    updated_at: unixtime
    (For credit cards only)
    card_type: visa, mastercard, (maybe one day american express)
    country: country the card was issued in
    expire_month: (2ch)
    expire_year: (4ch)
    card_holder: name of cardholder
    last4: last 4 digits of card
    (For debit accounts only)
    code: the sorting code of the bank
    account: a partially masked account number
    holder: name of the account holder

    Preauthorization:
    id: unique preauthorization ID
    amount: amount preauthorized in CENTS
    status: open, pending, closed, failed, deleted, or preauth
    livemode: true or false depending on whether the transaction is real or in test mode
    payment: a credit card payment method object (see above)
    client: if a preset client (see below) was used to make the transaction. Otherwise null
    created_at: unixtime
    updated_at: unixtime

    Transaction:
    id: unique transaction ID
    amount: amount charged in CENTS
    status: open, pending, closed, failed, partial_refunded, refunded, or preauthorize (closed means success)
    description: user-selected description of the transaction
    livemode: true or false depending on whether the transaction is real or in test mode
    payment: a payment method object (see above)
    preauthorization: the preauthorization associated with this transaction (optional)
    created_at: unixtime
    updated_at: unixtime

    Refund:
    id: unique refund ID
    transaction: The unique transaction ID of the transaction being refunded
    amount: amount refunded in CENTS
    status: open, pending or refunded
    description: user-selected description of the refund
    livemode: true or false depending on whether the transaction is real or in test mode
    created_at: unixtime
    updated_at: unixtime

    Client:
    id: unique id for this client
    email: client's email address (optional)
    description: description of this client (optional)
    created_at: unix timestamp identifying time of creation
    updated_at: unix timestamp identifying time of last change
    payment: list of cc or debit objects
    subscription: subscription object (optional)

    Offer:
    id: unique offer identifier
    name: freely controllable offer name
    amount: The amount, in CENTS, to be charged every time the offer period passes. Note that ODD values will NOT work in test mode.
    interval: "week", "month", or "year". The client will be charged every time the interval passes
    trial_period_days: Number of days before the first charge. (optional)

    Subscription:
    id: unique subscription identifier
    offer: unique offer identifier
    livemode: true or false depending on whether the transaction is real or in test mode
    cancel_at_period_end: true if subscription is to be cancelled at the end of current period, false if to be cancelled immediately
    created_at: unix timestamp identifying time of creation
    updated_at: unix timestamp identifying time of last change
    canceled_at: unix timestamp identifying time of cancellation(optional)
    interval: "week", "month", or "year". The client will be charged every time the interval passes
    clients: array of client objects


    """

    def __init__(self, privatekey):
        """
        Initialize a new paymill interface connection. Requires a private key.
        """
        self.s = requests.Session()
        self.s.auth = (privatekey, "")
        self.s.verify = False
        #self.s.cert="cacert.pem"

    def _apicall(self, url, params=(), cr="GET", ch=None):
        """
        Call an API endpoint.
        url: The URL of the entity to post to.
        params: a tuple of (name, value) tuples of parameters
        cr: The request type to be made. If parameters are passed, this will be ignored and treated as POST

        Returns a dictionary object populated with the json returned.
        """
        pars = dict(params)
        rf = None
        if(cr == "GET"):
            rf = self.s.get
        elif cr == "DELETE":
            rf = self.s.delete
        elif cr == "PUT":
            rf = self.s.put
        else:
            rf = self.s.post
        if params is not () and cr != "DELETE"and cr != "PUT":
            rf = self.s.post
        r = None
        if(ch):
            r = rf(url, params=pars, headers=ch)
        else:
            r = rf(url, params=pars)
        if ch is not None:
            return r.text
        return r.json()

    def newdebit(self, code, account, holder, client=None):
        """
        Create a debit card from account data.
        code: A bank sorting code
        account: The account number
        holder: The name of the account holder
        client: A client id number (optional)


        Returns: a dict with a member "data" containing a dict representing a debit card
        """
        p = []
        if code is not None and account is not None and holder is not None:
            p += [("code", code), (
                "account", account), ("holder", holder), ("type", "debit")]
        if client is not None:
            p += [("client", client)]
        return self._apicall("https://api.paymill.de/v2/payments/", tuple(p))

    def newcard(self, token, client=None):
        """
        Create a credit card from a given token.
        token: string Unique credit card token
        client: A client id number (optional)

        Returns: a dict with a member "data" containing a dict representing a CC
        """
        p = []
        if client is not None:
            p += [("client", client)]
        p += [("token", token)]
        return self._apicall("https://api.paymill.de/v2/payments", tuple(p))

    def getcarddetails(self, cardid):
        """
        Get the details of a credit card from its id.
        cardid: string Unique id for the credit card

        Returns: a dict with a member "data" containing a dict representing a CC
        """
        return self._apicall("https://api.paymill.de/v2/payments/" + str(cardid))

    def getcards(self):
        """
        List all stored cards.

        Returns: a dict with a member "data" which is an array of dicts, each representing a CC or debit card
        """
        return self._apicall("https://api.paymill.de/v2/payments/")

    def delcard(self, cardid):
        """
        Delete a stored CC
        cardid: Unique id for the CC to be deleted

        Returns: a dict with an member "data" containing an empty array
        """
        return self._apicall("https://api.paymill.de/v2/payments/%s" % (str(cardid),), cr="DELETE")

    def transact(self, amount=0, currency="eur", description=None, token=None, client=None, payment=None, preauth=None, code=None, account=None, holder=None):
        """
        Create a transaction (charge a card or account). You must provide an amount, and exactly one funding source.
        The amount is in cents, and the funding source can be a payment method id, a token, a preauthorization or a direct debit account.
        amount: The amount (in CENTS) to be charged. For example, 240 will charge 2 euros and 40 cents, NOT 240 euros.
        currency: ISO4217 currency code (optional)
        description: A short description of the transaction (optional)
        token: A token generated by the paymill bridge js library
        client: A client id number (optional)
        payment: A payment method id number (credit card id or debit account id)
        preauth: A preauthorization id number
        code: If paying by debit, the bank sorting code
        account: If paying by debit, the account number
        holder: If paying by debit, the name of the account holder

        Returns: None if one of the required parameters is missing. A dict with a member "data" containing a transaction dict otherwise.
        """
        p = []
        if client is not None:
            p += [("client", client)]
        if payment is None and code is not None and account is not None and holder is not None:
            try:
                payment = self.newdebit(
                    code, account, holder, client)["data"]["id"]
            except:
                return self.newdebit(code, account, holder, client)
        if payment is not None:
            p += [("payment", payment)]
        elif token is not None:
            p += [("token", token)]
        elif preauth is not None:
            p += [("preauthorization", preauth)]
        else:
            return None
        if amount == 0:
            return None
        if description is not None:
            p += [("description", description)]
        p += [("amount", str(amount))]
        p += [("currency", currency)]
        return self._apicall("https://api.paymill.de/v2/transactions/", tuple(p))

    def gettransdetails(self, tranid):
        """
        Get details on a transaction.
        tranid: string Unique id for the transaction

        Returns: a dict representing a transaction
        """
        return self._apicall("https://api.paymill.de/v2/transactions/" + str(tranid))

    def gettrans(self):
        """
        List all transactions.

        Returns: a dict with a member "data" which is an array of dicts, each representing a transaction
        """
        return self._apicall("https://api.paymill.de/v2/transactions/")

    def refund(self, tranid, amount, description=None):
        """
        Refunds an already performed transaction.
        tranid: string Unique transaction id
        amount: The amount in cents that are to be refunded
        description: A description of the refund (optional)

        Returns: a dict with a member "data" which is a dict representing a refund, or None if the amount is 0
        """
        if amount == 0:
            return None
        p = [("amount", str(amount))]
        if description is not None:
            p += [("description", description)]
        return self._apicall("https://api.paymill.de/v2/refunds/" + str(tranid), tuple(p))

    def getrefdetails(self, refid):
        """
        Get the details of a refund from its id.
        refid: string Unique id for the refund

        Returns: a dict with a member "data" which is a dict representing a refund
        """
        return self._apicall("https://api.paymill.de/v2/refunds/" + str(refid))

    def getrefs(self):
        """
        List all stored refunds.

        Returns: a dict with a member "data" which is an array of dicts, each representing a refund
        """
        return self._apicall("https://api.paymill.de/v2/refunds/")

    def preauth(self, amount=0, currency="eur", description=None, token=None, client=None, payment=None):
        """
        Preauthorize a transaction (reserve value a card). You must provide an amount, and exactly one funding source.
        The amount is in cents, and the funding source can be a token or a payment id.
        amount: The amount (in CENTS) to be charged. For example, 240 will charge 2 euros and 40 cents, NOT 240 euros.
        currency: ISO4217 (optional)
        token: A token generated by the paymill bridge js library
        payment: A payment method id number. Must represent a credit card, not a debit payment.

        Returns: None if one of the required parameters is missing. A dict with a member "data" containing a preauthorization dict otherwise.
        """
        p = []
        if payment is not None:
            p += [("payment", payment)]
        elif token is not None:
            p += [("token", token)]
        else:
            return None
        if amount == 0:
            return None
        p += [("amount", str(amount))]
        p += [("currency", currency)]
        return self._apicall("https://api.paymill.de/v2/preauthorizations/", tuple(p))

    def getpreauthdetails(self, preid):
        """
        Get details on a preauthorization.
        preid: string Unique id for the preauthorization

        Returns: a dict representing a preauthorization
        """
        return self._apicall("https://api.paymill.de/v2/preauthorizations/" + str(preid))

    def getpreauth(self):
        """
        List all preauthorizations.

        Returns: a dict with a member "data" which is an array of dicts, each representing a preauthorization
        """
        return self._apicall("https://api.paymill.de/v2/preauthorizations/")

    def newclient(self, email=None, description=None):
        """
        Creates a new client.
        email: client's email address
        description: description of this client (optional)

        Returns: a dict with a member "data" which is a dict representing a client.
        """
        p = []
        if description is not None:
            p += [("description", description)]
        if email is not None:
            p += [("email", str(email))]
        if p is []:
            return None
        return self._apicall("https://api.paymill.de/v2/clients", tuple(p))

    def getclientdetails(self, cid):
        """
        Get the details of a client from its id.
        cid: string Unique id for the client

        Returns: a dict with a member "data" which is a dict representing a client
        """
        return self._apicall("https://api.paymill.de/v2/clients/" + str(cid))

    def updateclient(self, cid, email, description=None):
        """
        Updates the details of a client.
        cid: string Unique client id
        email: The email of the client
        description: A description of the client (optional)

        Returns: a dict with a member "data" which is a dict representing a client
        """
        p = []
        if description is not None:
            p += [("description", description)]
        if email is not None:
            p += [("email", str(email))]
        if p is []:
            return None
        return self._apicall("https://api.paymill.de/v2/clients/" + str(cid), tuple(p), cr="PUT")

    def delclient(self, cid):
        """
        Delete a stored client
        cid: Unique id for the client to be deleted

        Returns: a dict with an member "data" containing an empty array
        """
        return self._apicall("https://api.paymill.de/v2/clients/%s" % (str(cid),), cr="DELETE")

    def getclients(self):
        """
        List all stored clients.

        Returns: a dict with a member "data" which is an array of dicts, each representing a client
        """
        return self._apicall("https://api.paymill.de/v2/clients/")

    def exportclients(self):
        """
        Export all stored clients in CSV form

        Returns: the contents of the CSV file
        """
        return self._apicall("https://api.paymill.de/v2/clients/", ch={"Accept": "text/csv"})

    def newoffer(self, amount, interval="month", currency="eur", name=None):
        """
        Creates a new offer
        amount: The amount in cents that are to be charged every interval
        interval: MUST be either "week", "month" or "year"
        currency: "eur" by default (optional)
        name: A name for this offer

        Returns: a dict with a member "data" which is a dict representing
            an offer, or None if the amount is 0 or the interval is invalid
        """
        if amount == 0:
            return None
        p = [("amount", str(amount))]
        if interval not in ["week", "month", "year"]:
            return None
        p += [("currency", str(currency))]
        p += [("interval", str(interval))]
        if name is not None:
            p += [("name", name)]
        return self._apicall("https://api.paymill.de/v2/offers", tuple(p))

    def getofferdetails(self, oid):
        """
        Get the details of an offer from its id.
        oid: string Unique id for the offer

        Returns: a dict with a member "data" which is a dict representing an offer
        """
        return self._apicall("https://api.paymill.de/v2/offers/" + str(oid))

    def updateoffer(self, oid, name):
        """
        Updates the details of an offer. Only the name may be changed
        oid: string Unique offer id
        name: The new name of the offer

        Returns: a dict with a member "data" which is a dict representing an offer
        """
        p = [("name", str(name))]
        return self._apicall("https://api.paymill.de/v2/offers/" + str(oid), tuple(p))

    def deloffer(self, oid):
        """
        Delete a stored offer. May only be done if no subscriptions to this offer are active.
        oid: Unique id for the offer to be deleted

        Returns: a dict with an member "data" containing an empty array
        """
        return self._apicall("https://api.paymill.de/v2/offers/%s" % (str(oid),), cr="DELETE")

    def getoffers(self):
        """
        List all stored offers.

        Returns: a dict with a member "data" which is an array of dicts, each representing an offer
        """
        return self._apicall("https://api.paymill.de/v2/offers/")

    def newsub(self, client, offer, payment):
        """
        Subscribes a client to an offer
        client: The id of the client
        offer: The id of the offer
        payment: The id of the payment instrument used for this offer

        Returns: a dict with a member "data" which is a dict representing a subscription
        """
        p = [("offer", str(offer)), ("client", str(client)), (
            "payment", str(payment))]
        return self._apicall("https://api.paymill.de/v2/subscriptions", tuple(p))

    def getsubdetails(self, sid):
        """
        Get the details of a subscription from its id.
        sid: string Unique id for the subscription

        Returns: a dict with a member "data" which is a dict representing a subscription
        """
        return self._apicall("https://api.paymill.de/v2/subscriptions/" + str(sid))

    def cancelsubafter(self, sid, cancel=True):
        """
        Cancels a subscription after its interval ends
        sid: string Unique subscription id
        cancel: If True, the subscription will be cancelled at the end of its interval. Set to False to undo.

        Returns: a dict with a member "data" which is a dict representing a subscription
        """
        if cancel:
            p = [("cancel_at_period_end", "true")]
        else:
            p = [("cancel_at_period_end", "false")]
        return self._apicall("https://api.paymill.de/v2/subscriptions/" + str(sid), tuple(p), cr="PUT")

    def cancelsubnow(self, sid):
        """
        Cancel a subscription immediately. Pending transactions will still be charged.
        sid: Unique subscription id

        Returns: a dict with an member "data"
        """
        return self._apicall("https://api.paymill.de/v2/subscriptions/%s" % (str(sid),), cr="DELETE")

    def getsubs(self):
        """
        List all stored subscriptions.

        Returns: a dict with a member "data" which is an array of dicts, each representing a subscription
        """
        return self._apicall("https://api.paymill.de/v2/subscriptions/")
        
    def response_code2text(self, response_code):
        texts = {
                10001:    'General undefined response.',
                10002:    'Still waiting on something.',

                20000:    'General success response.',
                
                40000:    'General problem with data.',
                40100:    'Problem with creditcard data.',
                40101:    'Problem with cvv.',
                40102:    'Card expired or not yet valid.',
                40103:    'Limit exceeded.',
                40104:    'Card invalid.',
                40105:    'expiry date not valid',
                40200:    'Problem with bank account data.',
                40300:    'Problem with 3d secure data.',
                40301:    'currency / amount mismatch',
                40400:    'Problem with input data.',
                40401:    'Amount too low or zero.',
                40402:    'Usage field too long.',
                40403:    'Currency not allowed.',
                
                50000:    'General problem with backend.',
                50001:    'country blacklisted.',
                50100:    'Technical error with credit card.',
                50101:    'Error limit exceeded.',
                50102:    'Card declined by authorization system.',
                50103:    'Manipulation or stolen card.',
                50104:    'Card restricted.',
                50105:    'Invalid card configuration data.',
                50200:    'Technical error with bank account.',
                50201:    'Card blacklisted.',
                50300:    'Technical error with 3D secure.',
                50400:    'Decline because of risk issues.',      
        }
        
        try:
            return texts[response_code]
        except:
            return response_code
    

if __name__ == "__main__":
    p = Pymill("YOURPRIVATEKEYHERE")
    cc = (p.getcards())["data"][0]["id"]
    print p.getcarddetails(cc)
    #print p.transact(amount=300,code="86055500",account="1234512345",holder="Max Mustermann",description="debittest")
    #print p.transact(amount=300,payment=cc,description="pymilltest")
