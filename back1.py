from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime  # For datetime objects
import os.path  # To manage paths
import sys  # To find out the script name (in argv[0])

# Import the backtrader platform
import backtrader as bt


# Create a Stratey
class TestStrategy(bt.Strategy):
    params = (
        ('maperiod', 200),
    )

    def log(self, txt, dt=None):
        ''' Logging function fot this strategy'''
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))

    def __init__(self):
        # Keep a reference to the "close" line in the data[0] dataseries
        self.dataclose = self.datas[0].close

        # To keep track of pending orders and buy price/commission
        self.order = None
        self.buyprice = None
        self.buycomm = None

        self.POINT_DISTANCE_TO_CLOSE_TRADE = 0.015
        self.BET_SIZE_MULTIPLIER = 24

        self.startingBetSize = 50
        self.betSize = self.startingBetSize
        self.shouldLongAccordingTo200MA = False
        self.isLong = False

        # Add a MovingAverageSimple indicator
        self.sma = bt.indicators.SimpleMovingAverage(
            self.data1, period=self.params.maperiod)

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # Check if an order has been completed
        # Attention: broker could reject order if not enough cash
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    'BUY EXECUTED, Price: %.2f, Cost: %.2f, Comm %.2f' %
                    (order.executed.price,
                     order.executed.value,
                     order.executed.comm))

                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:  # Sell
                self.log('SELL EXECUTED, Price: %.2f, Cost: %.2f, Comm %.2f' %
                         (order.executed.price,
                          order.executed.value,
                          order.executed.comm))

            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

        # Write down: no pending order
        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' %
                 (trade.pnl, trade.pnlcomm))

    def next(self):
        # Simply log the closing price of the series from the reference
        # self.log('Close, %.2f' % self.dataclose[0])
        # print(self.dataclose[0])

        if self.sma[0] > self.sma[-1]:
            self.shouldLongAccordingTo200MA = True
        elif self.sma[0] < self.sma[-1]:
            self.shouldLongAccordingTo200MA = False

        # Check if an order is pending ... if yes, we cannot send a 2nd one
        if self.order:
            return

        # Check if we are in the market
        if not self.position:

            # # Not yet ... we MIGHT BUY if ...
            # if self.dataclose[0] > self.sma[0]:

            #     # BUY, BUY, BUY!!! (with all possible default parameters)
            #     self.log('BUY CREATE, %.2f' % self.dataclose[0])

            #     # Keep track of the created order to avoid a 2nd order
            #     self.order = self.buy()

            if not self.position:
                if self.shouldLongAccordingTo200MA:
                    self.log('BUY CREATE, %.2f' % self.dataclose[0])
                    self.buyprice = self.dataclose[0]
                    self.order = self.buy(price=self.betSize)
                    self.isLong = True
                else:
                    self.log('SELL CREATE, %.2f' % self.dataclose[0])
                    self.buyprice = self.dataclose[0]
                    self.order = self.sell(price=self.betSize)
                    self.isLong = False

        else:
            if self.isLong:
                if self.buyprice < self.dataclose[0] - self.POINT_DISTANCE_TO_CLOSE_TRADE:
                    #Good outcome
                    self.order = self.close()
                    self.betSize = self.startingBetSize
                    self.startingBetSize += self.BET_SIZE_MULTIPLIER
                elif self.buyprice > self.dataclose[0] + self.POINT_DISTANCE_TO_CLOSE_TRADE:
                    #Bad outcome
                    self.order = self.close()
                    self.betSize = self.betSize * 2
      
            else: 
                if self.buyprice > self.dataclose[0] + self.POINT_DISTANCE_TO_CLOSE_TRADE:
                    #Good outcome
                    self.order = self.close()
                    self.betSize = self.startingBetSize
                    self.startingBetSize += self.BET_SIZE_MULTIPLIER
                elif self.buyprice < self.dataclose[0] - self.POINT_DISTANCE_TO_CLOSE_TRADE:
                    #Bad outcome
                    self.order = self.close()
                    self.betSize = self.betSize * 2
                
            # if len(self) >= (self.bar_executed + 5000):
            #     self.log('SELL CREATE, %.2f' % self.dataclose[0])

            #     self.order = self.close()


if __name__ == '__main__':
    # Create a cerebro entity
    cerebro = bt.Cerebro()

    # Add a strategy
    cerebro.addstrategy(TestStrategy)

    # Datas are in a subfolder of the samples. Need to find where the script is
    # because it could have been called from anywhere
    modpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    datapath = os.path.join(modpath, 'EURUSD_H1.csv')

    # Create a Data Feed
    data = bt.feeds.GenericCSVData(
        dataname=datapath,
        dtformat=('%Y-%m-%d %H:%M'),
        fromdate=datetime.datetime(2007, 1, 1),
        todate=datetime.datetime(2007, 10, 20),
        # todate=datetime.datetime(2022, 8, 29),
        reverse=False,
        nullvalue=0.0,
        datetime=0,
        high=2,
        low=3,
        open=1,
        close=4,
        volume=5,
        openinterest=-1)

    # Add the Data Feed to Cerebro
    cerebro.adddata(data)

    cerebro.resampledata(data, timeframe = bt.TimeFrame.Days, compression = 24)

    # Set our desired cash start
    cerebro.broker.setcash(1000000000.0)

    # Add a FixedSize sizer according to the stake
    cerebro.addsizer(bt.sizers.FixedSize, stake=10)

    # Print out the starting conditions
    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())

    # Run over everything
    cerebro.run()

    # Print out the final result
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())

    # Plot the result
    cerebro.plot()