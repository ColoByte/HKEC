import sys
import random
import time
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg


# ======================
# 数据采集线程（模拟）
# ======================
class DataWorker(QtCore.QThread):
    data_signal = QtCore.pyqtSignal(int, float)  # (channel_id, value)

    def __init__(self, channel_id):
        super().__init__()
        self.channel_id = channel_id
        self.running = True

    def run(self):
        while self.running:
            value = random.uniform(0, 1)  # 模拟电化学信号
            self.data_signal.emit(self.channel_id, value)
            time.sleep(0.1)

    def stop(self):
        self.running = False
        self.quit()
        self.wait()


# ======================
# 主界面
# ======================
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("ECDAQ Multi-Channel Monitor")
        self.resize(900, 600)

        self.channel_count = 1
        self.workers = {}
        self.data_buffer = {}

        self.init_ui()

    def init_ui(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        layout = QtWidgets.QVBoxLayout(central_widget)

        # 控制按钮
        btn_layout = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("Start")
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.add_channel_btn = QtWidgets.QPushButton("Add Channel")

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.add_channel_btn)

        layout.addLayout(btn_layout)

        # 绘图区域
        self.plot_widget = pg.PlotWidget(title="Real-time Data")
        self.plot_widget.addLegend()
        layout.addWidget(self.plot_widget)

        self.curves = {}

        # 绑定事件
        self.start_btn.clicked.connect(self.start_acquisition)
        self.stop_btn.clicked.connect(self.stop_acquisition)
        self.add_channel_btn.clicked.connect(self.add_channel)

    # ======================
    # 通道管理
    # ======================
    def add_channel(self):
        ch_id = self.channel_count
        self.channel_count += 1

        self.data_buffer[ch_id] = []
        curve = self.plot_widget.plot(pen=pg.intColor(ch_id), name=f"CH{ch_id}")
        self.curves[ch_id] = curve

        worker = DataWorker(ch_id)
        worker.data_signal.connect(self.update_data)
        self.workers[ch_id] = worker

    # ======================
    # 控制采集
    # ======================
    def start_acquisition(self):
        if not self.workers:
            self.add_channel()  # 默认至少一个通道

        for worker in self.workers.values():
            if not worker.isRunning():
                worker.start()

    def stop_acquisition(self):
        for worker in self.workers.values():
            worker.stop()

    # ======================
    # 数据更新
    # ======================
    def update_data(self, ch_id, value):
        buffer = self.data_buffer[ch_id]
        buffer.append(value)

        if len(buffer) > 100:
            buffer.pop(0)

        self.curves[ch_id].setData(buffer)


# ======================
# 主入口
# ======================
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())