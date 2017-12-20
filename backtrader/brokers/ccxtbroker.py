#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2015, 2016, 2017 Daniel Rodriguez
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import collections
from copy import copy
from datetime import date, datetime, timedelta
import threading
import time
import uuid

import ccxt

from backtrader import BrokerBase, OrderBase, Order
from backtrader.utils.py3 import with_metaclass, queue, MAXFLOAT
from backtrader.metabase import MetaParams

class CCXTOrder(OrderBase):
    def __init__(self, owner, data, ccxt_order):
        self.owner = owner
        self.data = data
        self.ccxt_order = ccxt_order
        self.ordtype = self.Buy if ccxt_order['info']['side'] == 'buy' else self.Sell
        self.size = float(ccxt_order['info']['original_amount'])

        super(CCXTOrder, self).__init__()

class CCXTBroker(BrokerBase):
    '''Broker implementation for CCXT cryptocurrency trading library.

    This class maps the orders/positions from CCXT to the
    internal API of ``backtrader``.
    '''

    order_types = {Order.Market: 'market',
                   Order.Limit: 'limit',
                   Order.Stop: 'stop',
                   Order.StopLimit: 'stop limit'}

    def __init__(self, exchange, currency, config):
        super(CCXTBroker, self).__init__()

        self.exchange = getattr(ccxt, exchange)(config)
        self.currency = currency

        self.notifs = queue.Queue()  # holds orders which are notified
        self.startingcash = self.cash = 0.0
        self.startingvalue = self.value = 0.0

    def getcash(self):
        self.cash = self.exchange.fetch_balance()['free'][self.currency]
        return self.cash

    def getvalue(self):
        self.value = self.exchange.fetch_balance()['total'][self.currency]
        return self.value

    def get_notification(self):
        try:
            return self.notifs.get(False)
        except queue.Empty:
            return None

    def notify(self, order):
        self.notifs.put(order)

    def getposition(self, data):
        currency = data.symbol.split('/')[0]
        return self.exchange.fetch_balance()['total'][currency]

    def _submit(self, owner, data, exectype, side, amount, price, params):
        order_type = self.order_types.get(exectype)
        ccxt_order = self.exchange.create_order(symbol=data.symbol, type=order_type, side=side,
                                                amount=amount, price=price, params=params)
        order = CCXTOrder(owner, data, ccxt_order)
        self.notify(order)
        return order 

    def buy(self, owner, data, size, price=None, plimit=None,
            exectype=None, valid=None, tradeid=0, oco=None,
            trailamount=None, trailpercent=None,
            **kwargs):
        return self._submit(owner, data, exectype, 'buy', size, price, kwargs)

    def sell(self, owner, data, size, price=None, plimit=None,
             exectype=None, valid=None, tradeid=0, oco=None,
             trailamount=None, trailpercent=None,
             **kwargs):
        return self._submit(owner, data, exectype, 'sell', size, price, kwargs)

    def cancel(self, order):
        return self.exchange.cancel_order(self, order['id'])
