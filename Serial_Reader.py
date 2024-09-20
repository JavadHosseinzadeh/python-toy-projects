import sys
import serial
import serial.tools.list_ports
from PyQt5.QtWidgets import QApplication, QMainWindow, QTextEdit, QVBoxLayout, QWidget, QPushButton, QComboBox, QLabel, QHBoxLayout, QFileDialog
from PyQt5.QtCore import QThread, pyqtSignal

class SerialThread(QThread):
    data_received = pyqtSignal(bytes)  # Signal to emit raw binary data

    def __init__(self, serial_port):
        super().__init__()
        self.serial_port = serial_port
        self.is_running = True

    def run(self):
        while self.is_running:
            if self.serial_port.in_waiting > 0:
                data = self.serial_port.read(self.serial_port.in_waiting)
                self.data_received.emit(data)

    def stop(self):
        self.is_running = False
        self.quit()
        self.wait()

class SerialMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Serial Monitor")
        self.setGeometry(100, 100, 900, 600)

        # Serial Port Setup
        self.serial_port = serial.Serial()
        self.serial_port.timeout = 1

        # Layout and Widgets
        layout = QVBoxLayout()

        # COM Port and Baudrate Selection
        port_layout = QHBoxLayout()
        self.port_label = QLabel("Select COM Port:", self)
        self.port_combo = QComboBox(self)
        self.refresh_ports()

        self.baud_label = QLabel("Baudrate:", self)
        self.baud_combo = QComboBox(self)
        self.baud_combo.addItems(["9600", "115200", "57600", "38400", "19200", "4800", "2400", "1200","921600"])
        self.baud_combo.setCurrentText("9600")  # Set default baudrate

        port_layout.addWidget(self.port_label)
        port_layout.addWidget(self.port_combo)
        port_layout.addWidget(self.baud_label)
        port_layout.addWidget(self.baud_combo)

        # Data Display Boxes
        self.binary_display = QTextEdit(self)
        self.binary_display.setReadOnly(True)
        self.binary_display.setPlaceholderText("Binary Data")

        self.hex_display = QTextEdit(self)
        self.hex_display.setReadOnly(True)
        self.hex_display.setPlaceholderText("Hexadecimal Data")

        self.char_display = QTextEdit(self)
        self.char_display.setReadOnly(True)
        self.char_display.setPlaceholderText("Character Data")

        # Buttons
        self.start_button = QPushButton("Start Monitoring", self)
        self.start_button.clicked.connect(self.start_monitoring)

        self.stop_button = QPushButton("Stop Monitoring", self)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_monitoring)

        self.save_button = QPushButton("Save Data", self)
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_data)

        layout.addLayout(port_layout)
        layout.addWidget(QLabel("Binary Data", self))
        layout.addWidget(self.binary_display)
        layout.addWidget(QLabel("Hexadecimal Data", self))
        layout.addWidget(self.hex_display)
        layout.addWidget(QLabel("Character Data", self))
        layout.addWidget(self.char_display)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.save_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.serial_thread = None
        self.binary_data_list = []
        self.hex_data_list = []
        self.char_data_list = []

    def refresh_ports(self):
        # Detect and populate the available serial ports
        ports = serial.tools.list_ports.comports()
        self.port_combo.clear()
        for port in ports:
            self.port_combo.addItem(port.device)

    def start_monitoring(self):
        selected_port = self.port_combo.currentText()
        selected_baud = self.baud_combo.currentText()

        if selected_port:
            self.serial_port.port = selected_port
            self.serial_port.baudrate = int(selected_baud)
            self.serial_port.open()

            self.serial_thread = SerialThread(self.serial_port)
            self.serial_thread.data_received.connect(self.update_text)
            self.serial_thread.start()

            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.save_button.setEnabled(True)
        else:
            self.char_display.append("No serial port selected.")

    def stop_monitoring(self):
        if self.serial_thread:
            self.serial_thread.stop()
            self.serial_port.close()

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.save_button.setEnabled(False)

    def update_text(self, data):
        binary_data = ' '.join(f'{byte:08b}' for byte in data)
        hex_data = ' '.join(f'{byte:02X}' for byte in data)
        char_data = data.decode('utf-8', errors='replace')

        # Append to the displays
        self.binary_display.append(binary_data)
        self.hex_display.append(hex_data)
        self.char_display.append(char_data)

        # Save the data in lists for later saving
        self.binary_data_list.append(binary_data)
        self.hex_data_list.append(hex_data)
        self.char_data_list.append(char_data)

    def save_data(self):
        save_directory = QFileDialog.getExistingDirectory(self, "Select Directory to Save Files")

        if save_directory:
            binary_file_path = f"{save_directory}/binary_data.txt"
            hex_file_path = f"{save_directory}/hex_data.txt"
            char_file_path = f"{save_directory}/char_data.txt"

            # Save Binary Data
            with open(binary_file_path, 'w') as binary_file:
                binary_file.write('\n'.join(self.binary_data_list))

            # Save Hex Data
            with open(hex_file_path, 'w') as hex_file:
                hex_file.write('\n'.join(self.hex_data_list))

            # Save Character Data
            with open(char_file_path, 'w') as char_file:
                char_file.write('\n'.join(self.char_data_list))

            self.char_display.append(f"Data saved in {save_directory}")

    def closeEvent(self, event):
        self.stop_monitoring()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SerialMonitor()
    window.show()
    sys.exit(app.exec_())
