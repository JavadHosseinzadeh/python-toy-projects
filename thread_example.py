import sys
import time
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton

class CounterThread1(QThread):
    update_count = pyqtSignal(int)
    finished_count = pyqtSignal(int)

    def __init__(self, count=0):
        super().__init__()
        self.count = count
        self.running = True

    def run(self):
        try:
            while self.running:
                self.count += 1
                self.update_count.emit(self.count)
                time.sleep(0.1)
                # self.wait()
        finally:
            self.finished_count.emit(self.count)

    def stop(self):
        self.running = False

class CounterThread2(QThread):
    update_count = pyqtSignal(int)
    finished_count = pyqtSignal(int)

    def __init__(self, start_count):
        super().__init__()
        self.count = start_count
        self.running = True

    def run(self):
        try:
            while self.running:
                self.count += 1
                self.update_count.emit(self.count)
                time.sleep(0.1)
                # self.wait()
        finally:
            self.finished_count.emit(self.count)

    def stop(self):
        self.running = False

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):
        self.layout = QVBoxLayout()

        self.label1 = QLabel('Thread 1: 0', self)
        self.layout.addWidget(self.label1)

        self.label2 = QLabel('Thread 2: 0', self)
        self.layout.addWidget(self.label2)

        self.button = QPushButton('Start', self)
        self.button.clicked.connect(self.startThreads)
        self.layout.addWidget(self.button)

        self.stop_button = QPushButton('Stop', self)
        self.stop_button.clicked.connect(self.stopThreads)
        self.layout.addWidget(self.stop_button)

        self.setLayout(self.layout)

        self.counter1 = CounterThread1()
        self.counter1.update_count.connect(self.updateLabel1)
        self.counter1.finished_count.connect(self.startCounter2)

        self.counter2 = None

    def startThreads(self):
        if not self.counter1.isRunning():
            self.counter1.start()

    def stopThreads(self):
        if self.counter1.isRunning():
            self.counter1.stop()
        if self.counter2 is not None and self.counter2.isRunning():
            self.counter2.stop()

    def updateLabel1(self, count):
        self.label1.setText(f'Thread 1: {count}')

    def updateLabel2(self, count):
        self.label2.setText(f'Thread 2: {count}')

    def startCounter2(self, count):
        if self.counter2 is None or not self.counter2.isRunning():
            self.counter2 = CounterThread2(count)
            self.counter2.update_count.connect(self.updateLabel2)
            self.counter2.finished_count.connect(self.restartCounter1)
            self.counter2.start()

    def restartCounter1(self, count):
        if not self.counter1.isRunning():
            self.counter1 = CounterThread1(count)
            self.counter1.update_count.connect(self.updateLabel1)
            self.counter1.finished_count.connect(self.startCounter2)
            self.counter1.start()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())
