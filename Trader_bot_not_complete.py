import sys
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QComboBox, QLineEdit, QPushButton, QProgressBar)
from PyQt5.QtCore import pyqtSignal, QObject, Qt, QThread, QTimer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from tensorflow import keras
from tensorflow.keras import layers
from datetime import datetime
import os
import logging

# Configure logging
logging.basicConfig(filename='trading_bot.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Signal class to handle updates between threads and UI
class SignalEmitter(QObject):
    update_status = pyqtSignal(str)
    update_account_info = pyqtSignal(str, str)
    update_trade_info = pyqtSignal(str, str, str, str)
    loading_screen = pyqtSignal(bool)

# TradingBotThread moved to QThread for better integration with PyQt
class TradingBotThread(QThread):
    def __init__(self, signal_emitter, symbol, timeframe, login=None, password=None, server=None, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.timeframe = timeframe
        self.tax_rate = 0.20
        self.open_trade = None
        self.data = None
        self.login = login
        self.password = password
        self.server = server
        self.model = None
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.trade_log = []
        self.equity_log = []
        self.predicted_price = None
        self.current_price = None
        self.signal_emitter = signal_emitter
        self.running = True

    def run(self):
        self.signal_emitter.loading_screen.emit(True)
        try:
            self.initialize_mt5()
            self.fetch_historical_data()
            self.train_lstm()
            self.signal_emitter.loading_screen.emit(False)
            while self.running:
                self.update_data()
                self.make_trading_decision()
                QThread.sleep(1)
        except Exception as e:
            logging.error(f"Error in trading bot: {str(e)}")
            self.signal_emitter.update_status.emit(f"Error in trading bot: {str(e)}")

    def initialize_mt5(self):
        if not self.login or not self.password or not self.server:
            raise ValueError("MT5 login credentials are missing")
        
        if not mt5.initialize(login=self.login, password=self.password, server=self.server):
            raise RuntimeError("MetaTrader 5 initialization failed")
        
        self.signal_emitter.update_status.emit("MetaTrader 5 initialized")
        logging.info("MetaTrader 5 initialized")

    def fetch_historical_data(self):
        try:
            rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, 5000)
            if rates is None or len(rates) == 0:
                raise ValueError("Failed to fetch historical data")

            data = pd.DataFrame(rates)
            data['time'] = pd.to_datetime(data['time'], unit='s')
            self.data = data
            self.signal_emitter.update_status.emit("Historical data fetched")
            logging.info("Historical data fetched successfully")
        except Exception as e:
            logging.error(f"Error fetching historical data: {str(e)}")
            self.signal_emitter.update_status.emit(f"Error fetching historical data: {str(e)}")

    def update_data(self):
        try:
            rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, 1)
            if rates is None or len(rates) == 0:
                raise ValueError("Failed to update data")

            new_data = pd.DataFrame(rates)
            new_data['time'] = pd.to_datetime(new_data['time'], unit='s')
            self.data = pd.concat([self.data, new_data], ignore_index=True).drop_duplicates(subset=['time'])
            self.data = self.data.iloc[-1000:]

            self.update_predictions()
            self.log_equity()
            self.save_to_excel()
        except Exception as e:
            logging.error(f"Error updating data: {str(e)}")
            self.signal_emitter.update_status.emit(f"Error updating data: {str(e)}")

    def get_account_info(self):
        try:
            account_info = mt5.account_info()
            if not account_info:
                raise ValueError("Could not retrieve account info")

            balance_str = f"Balance: {account_info.balance}"
            equity_str = f"Equity: {account_info.equity}"
            self.signal_emitter.update_account_info.emit(balance_str, equity_str)
            return account_info
        except Exception as e:
            logging.error(f"Error getting account info: {str(e)}")
            self.signal_emitter.update_status.emit(f"Error getting account info: {str(e)}")
            return None

    def place_order(self, order_type):
        try:
            account_info = self.get_account_info()
            if not account_info or account_info.balance < 40:
                self.signal_emitter.update_status.emit("Account balance too low")
                return

            if self.open_trade:
                self.close_active_trade()

            symbol_info = mt5.symbol_info(self.symbol)
            if not symbol_info:
                raise ValueError(f"Symbol {self.symbol} not found")

            min_volume = symbol_info.volume_min
            volume_step = symbol_info.volume_step
            order_volume = max(min_volume, volume_step)

            current_price = self.data['close'].iloc[-1]
            request = {
                'action': mt5.TRADE_ACTION_DEAL,
                'symbol': self.symbol,
                'volume': order_volume,
                'type': order_type,
                'price': current_price,
                'deviation': 20,
                'magic': 234000,
                'comment': 'Automated order',
                'type_time': mt5.ORDER_TIME_GTC,
                'type_filling': mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                self.open_trade = (result.order, order_type, current_price)
                self.trade_log.append({
                    'time': datetime.now(),
                    'symbol': self.symbol,
                    'type': 'buy' if order_type == mt5.ORDER_TYPE_BUY else 'sell',
                    'price': current_price,
                    'volume': order_volume
                })
                self.signal_emitter.update_trade_info.emit(
                    f"Open Price: {current_price}", "N/A", "N/A", "N/A"
                )
                self.signal_emitter.update_status.emit(f"Order executed, ticket: {result.order}")
                logging.info(f"Order executed: {result.order}")
            else:
                raise RuntimeError(f"Order failed, retcode: {result.retcode}")
        except Exception as e:
            logging.error(f"Error placing order: {str(e)}")
            self.signal_emitter.update_status.emit(f"Error placing order: {str(e)}")

    def close_active_trade(self):
        if self.open_trade:
            try:
                order_ticket, order_type, buy_price = self.open_trade
                current_price = self.data['close'].iloc[-1]
                profit_loss = (current_price - buy_price) * (1 - self.tax_rate)
                close_order_type = mt5.ORDER_TYPE_SELL if order_type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
                close_request = {
                    'action': mt5.TRADE_ACTION_DEAL,
                    'symbol': self.symbol,
                    'volume': self.open_trade[2],
                    'type': close_order_type,
                    'position': order_ticket,
                    'price': current_price,
                    'deviation': 20,
                    'magic': 234000,
                    'comment': 'Automated close order',
                }
                result = mt5.order_send(close_request)
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    self.open_trade = None
                    self.trade_log.append({
                        'time': datetime.now(),
                        'symbol': self.symbol,
                        'type': 'close',
                        'price': current_price,
                        'profit_loss': profit_loss
                    })
                    self.signal_emitter.update_trade_info.emit(
                        f"Open Price: {buy_price}", f"Current Value: {current_price}",
                        f"Profit/Loss: {profit_loss:.2f}%", "N/A"
                    )
                    self.signal_emitter.update_status.emit(f"Trade closed, profit/loss: {profit_loss:.2f}")
                    logging.info(f"Trade closed, profit/loss: {profit_loss:.2f}")
                else:
                    raise RuntimeError(f"Failed to close the trade, retcode: {result.retcode}")
            except Exception as e:
                logging.error(f"Error closing trade: {str(e)}")
                self.signal_emitter.update_status.emit(f"Error closing trade: {str(e)}")

    def prepare_features(self):
        try:
            features = []
            for i in range(20, len(self.data)):
                features.append(
                    self.data[['open', 'high', 'low', 'close', 'tick_volume']].iloc[i - 20:i].values
                )
            return np.array(features)
        except Exception as e:
            logging.error(f"Error preparing features: {str(e)}")
            self.signal_emitter.update_status.emit(f"Error preparing features: {str(e)}")
            return np.array([])

    def train_lstm(self):
        try:
            if self.data is None or self.data.empty:
                raise ValueError("No data available for training")

            self.data['scaled_close'] = self.scaler.fit_transform(self.data[['close']])

            features = self.prepare_features()
            labels = self.data['scaled_close'].iloc[20:].values

            X_train, X_test, y_train, y_test = train_test_split(features, labels, test_size=0.2)

            model = keras.Sequential([
                layers.LSTM(50, activation='relu', input_shape=(20, 5)),
                layers.Dropout(0.2),
                layers.Dense(32, activation='relu'),
                layers.Dropout(0.2),
                layers.Dense(1)
            ])

            model.compile(optimizer='adam', loss='mse')
            model.fit(X_train, y_train, epochs=20, batch_size=32)

            self.model = model
            self.signal_emitter.update_status.emit("LSTM model trained")
            logging.info("LSTM model trained")
        except Exception as e:
            logging.error(f"Error training LSTM: {str(e)}")
            self.signal_emitter.update_status.emit(f"Error training LSTM: {str(e)}")

    def update_predictions(self):
        try:
            features = self.prepare_features()
            if features.size == 0:
                return

            prediction = self.model.predict(features[-1].reshape(1, 20, 5))
            predicted_scaled_price = prediction.flatten()[0]
            predicted_price = self.scaler.inverse_transform([[predicted_scaled_price]])[0][0]
            current_price = self.data['close'].iloc[-1]

            self.predicted_price = predicted_price
            self.current_price = current_price

            self.signal_emitter.update_trade_info.emit(
                f"Open Price: N/A", f"Current Value: {current_price}",
                f"Profit/Loss: N/A", f"Predicted Price: {predicted_price}"
            )
            logging.info(f"Predicted Price: {predicted_price}, Current Price: {current_price}")
        except Exception as e:
            logging.error(f"Error updating predictions: {str(e)}")
            self.signal_emitter.update_status.emit(f"Error updating predictions: {str(e)}")

    def make_trading_decision(self):
        try:
            if self.predicted_price is None or self.current_price is None:
                return

            if self.predicted_price > self.current_price and not self.open_trade:
                self.place_order(mt5.ORDER_TYPE_BUY)
            elif self.predicted_price < self.current_price and self.open_trade:
                self.close_active_trade()
        except Exception as e:
            logging.error(f"Error making trading decision: {str(e)}")
            self.signal_emitter.update_status.emit(f"Error making trading decision: {str(e)}")

    def log_equity(self):
        try:
            account_info = self.get_account_info()
            if account_info:
                self.equity_log.append({
                    'time': datetime.now(),
                    'balance': account_info.balance,
                    'equity': account_info.equity
                })
        except Exception as e:
            logging.error(f"Error logging equity: {str(e)}")
            self.signal_emitter.update_status.emit(f"Error logging equity: {str(e)}")

    def save_to_excel(self):
        try:
            timestamp = datetime.now().strftime('%y_%m_%d_%H_%M_%S')
            filename = f'trading_log_{timestamp}.xlsx'
            with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                pd.DataFrame(self.trade_log).to_excel(writer, sheet_name='Trades')
                pd.DataFrame(self.equity_log).to_excel(writer, sheet_name='Equity')
            self.signal_emitter.update_status.emit("Data saved to Excel")
            logging.info("Data saved to Excel")
        except Exception as e:
            logging.error(f"Error saving to Excel: {str(e)}")
            self.signal_emitter.update_status.emit(f"Error saving to Excel: {str(e)}")

    def stop(self):
        self.running = False
        self.quit()
        self.wait()

class TradingBotUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Trading Bot")
        self.setGeometry(100, 100, 800, 400)

        self.signal_emitter = SignalEmitter()

        # Connect signals
        self.signal_emitter.update_status.connect(self.update_status)
        self.signal_emitter.update_account_info.connect(self.update_account_info)
        self.signal_emitter.update_trade_info.connect(self.update_trade_info)
        self.signal_emitter.loading_screen.connect(self.toggle_loading_screen)

        # Central widget
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        # Layout
        main_layout = QVBoxLayout()

        # Account Login
        login_layout = QHBoxLayout()
        login_layout.addWidget(QLabel("Account ID:"))
        self.account_id_combo = QComboBox()
        self.account_id_combo.addItems(["Account1", "Account2", "Account3"])
        login_layout.addWidget(self.account_id_combo)

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_to_account)
        login_layout.addWidget(self.connect_button)

        self.connection_status = QLineEdit()
        self.connection_status.setReadOnly(True)
        login_layout.addWidget(QLabel("Status:"))
        login_layout.addWidget(self.connection_status)

        main_layout.addLayout(login_layout)

        # Timeframe Selection
        timeframe_layout = QHBoxLayout()
        timeframe_layout.addWidget(QLabel("Timeframe:"))
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems([
            "M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"
        ])
        timeframe_layout.addWidget(self.timeframe_combo)
        main_layout.addLayout(timeframe_layout)

        # Symbol Selection
        symbol_layout = QHBoxLayout()
        symbol_layout.addWidget(QLabel("Symbol:"))
        self.symbol_combo = QComboBox()
        symbol_layout.addWidget(self.symbol_combo)
        main_layout.addLayout(symbol_layout)

        # Account Information
        account_info_layout = QHBoxLayout()
        self.balance_edit = QLineEdit()
        self.balance_edit.setReadOnly(True)
        self.equity_edit = QLineEdit()
        self.equity_edit.setReadOnly(True)

        account_info_layout.addWidget(QLabel("Balance:"))
        account_info_layout.addWidget(self.balance_edit)
        account_info_layout.addWidget(QLabel("Equity:"))
        account_info_layout.addWidget(self.equity_edit)

        main_layout.addLayout(account_info_layout)

        # Trade Details
        trade_details_layout = QHBoxLayout()
        self.opening_price_edit = QLineEdit()
        self.opening_price_edit.setReadOnly(True)
        self.current_value_edit = QLineEdit()
        self.current_value_edit.setReadOnly(True)
        self.profit_loss_edit = QLineEdit()
        self.profit_loss_edit.setReadOnly(True)
        self.predicted_price_edit = QLineEdit()
        self.predicted_price_edit.setReadOnly(True)

        trade_details_layout.addWidget(QLabel("Opening Price:"))
        trade_details_layout.addWidget(self.opening_price_edit)
        trade_details_layout.addWidget(QLabel("Current Value:"))
        trade_details_layout.addWidget(self.current_value_edit)
        trade_details_layout.addWidget(QLabel("Profit/Loss (%):"))
        trade_details_layout.addWidget(self.profit_loss_edit)
        trade_details_layout.addWidget(QLabel("Predicted Price:"))
        trade_details_layout.addWidget(self.predicted_price_edit)

        main_layout.addLayout(trade_details_layout)

        # Trading Controls
        trade_controls_layout = QHBoxLayout()

        self.single_trade_button = QPushButton("Single Trade")
        self.single_trade_button.clicked.connect(self.single_trade)
        trade_controls_layout.addWidget(self.single_trade_button)

        self.continuous_trade_button = QPushButton("Continuous Trade")
        self.continuous_trade_button.clicked.connect(self.continuous_trade)
        trade_controls_layout.addWidget(self.continuous_trade_button)

        main_layout.addLayout(trade_controls_layout)

        # Loading Screen
        self.loading_screen = QProgressBar(self)
        self.loading_screen.setRange(0, 0)
        self.loading_screen.setVisible(False)
        main_layout.addWidget(self.loading_screen)

        central_widget.setLayout(main_layout)

        self.trading_bot_thread = None

    def connect_to_account(self):
        account_id = self.account_id_combo.currentText()
        login = 5025375162  # Replace with your account login
        password = '2zUsEjV+'  # Replace with your account password
        server = 'MetaQuotes-Demo'  # Replace with your server name
        symbol = self.symbol_combo.currentText()
        timeframe = getattr(mt5, f'TIMEFRAME_{self.timeframe_combo.currentText()}')

        if self.trading_bot_thread:
            self.trading_bot_thread.stop()

        self.trading_bot_thread = TradingBotThread(
            self.signal_emitter, symbol, timeframe, login=login, password=password, server=server
        )
        self.trading_bot_thread.start()

    def update_status(self, status_message):
        self.connection_status.setText(status_message)

    def update_account_info(self, balance, equity):
        self.balance_edit.setText(balance)
        self.equity_edit.setText(equity)

    def update_trade_info(self, opening_price, current_value, profit_loss, predicted_price):
        self.opening_price_edit.setText(opening_price)
        self.current_value_edit.setText(current_value)
        self.profit_loss_edit.setText(profit_loss)
        self.predicted_price_edit.setText(predicted_price)

    def single_trade(self):
        if self.trading_bot_thread:
            self.trading_bot_thread.place_order(mt5.ORDER_TYPE_BUY)

    def continuous_trade(self):
        if self.trading_bot_thread:
            self.trading_bot_thread.running = True
            self.continuous_trading_loop()

    def continuous_trading_loop(self):
        if self.trading_bot_thread and self.trading_bot_thread.running:
            self.trading_bot_thread.make_trading_decision()
            QTimer.singleShot(60000, self.continuous_trading_loop)  # 1-minute interval between trades

    def toggle_loading_screen(self, show):
        self.loading_screen.setVisible(show)


def main():
    app = QApplication(sys.argv)
    window = TradingBotUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
