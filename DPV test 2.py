import sys
import os
from ctypes import *
import numpy as np
import time
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QLabel, QPushButton, QHBoxLayout, QMessageBox)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
import pyqtgraph as pg

# ====================== DLL 加载 ======================
dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Usb_Daq_V6505.dll")
DAQdll = WinDLL(dll_path)

dev = 0
ADC_RATE = 1000
V_MIN, V_MAX = -10.0, 10.0


# ====================== DPV 波形生成 ======================
def generate_dpv_waveform(E_init, E_final, E_incr, amplitude, pulse_width, pulse_period, quiet_time):
    if E_incr <= 0:
        raise ValueError("E_incr 必须 > 0")
    if pulse_width > pulse_period:
        raise ValueError("pulse_width 不能大于 pulse_period")

    N_period = 100
    fs = 100.0 / pulse_period
    if not (100 <= fs <= 10000):
        raise ValueError(f"DAC采样率 {fs:.1f} Hz 超出允许范围 [100, 10000] Hz")

    N_pulse = int(round(pulse_width / pulse_period * N_period))
    N_base = N_period - N_pulse

    # 生成阶梯电位
    steps = []
    E = E_init
    while E <= E_final + 1e-6:  # 包含终点
        steps.append(E)
        E += E_incr
    steps = np.array(steps)

    # Quiet Time
    N_quiet = int(round(quiet_time * fs))
    E_quiet = np.full(N_quiet, E_init, dtype=float)

    # DPV 主波形
    waveform = []
    for E_step in steps:
        base_part = np.full(N_base, E_step, dtype=float)
        pulse_part = np.full(N_pulse, E_step + amplitude, dtype=float)
        cycle = np.concatenate([base_part, pulse_part])
        waveform.append(cycle)

    E_main = np.concatenate(waveform)
    E_total = np.concatenate([E_quiet, E_main])
    t = np.arange(len(E_total)) * (1.0 / fs)

    return t, E_total, fs


def voltage_to_da(v):
    return int(((v - V_MIN) / (V_MAX - V_MIN)) * 65535 + 0.5)


# ====================== 采集线程 ======================
class AcquisitionThread(QThread):
    data_updated = pyqtSignal(list, list)  # time_list, voltage_list
    finished = pyqtSignal(str)  # 保存文件名

    def __init__(self, params):
        super().__init__()
        self.params = params
        self.running = True

    def run(self):
        try:
            t_dac, E_dac, da_fs = generate_dpv_waveform(**self.params)

            # 打开设备并启动 DA
            if DAQdll.OpenUSB() != 0:
                self.finished.emit("打开设备失败")
                return

            da_data = [(0 << 16) | voltage_to_da(v) for v in E_dac]
            da_array = (c_uint * len(da_data))(*da_data)

            DAQdll.Set_DA_Scan(dev, 0, int(da_fs), 1)
            DAQdll.Sent_DaData(dev, len(da_data), da_array)

            # 启动 ADC
            DAQdll.Ad_Continu_Conf(dev, 0, 0, 1, 0, ADC_RATE, 0, 0, 0, 0)

            collected = 0
            time_data = []
            voltage_data = []
            expected_data = []
            cycle_time = self.params['pulse_period']
            window = 5 * cycle_time

            while self.running:
                buf_size = DAQdll.Get_AdBuf_Size(dev)
                if buf_size >= 1000:
                    to_read = min(buf_size, 5000)
                    temp = (c_float * to_read)()
                    read_cnt = DAQdll.Read_AdBuf(dev, temp, to_read)

                    if read_cnt > 0:
                        # 当前时间
                        curr_time = np.arange(collected, collected + read_cnt) / ADC_RATE
                        curr_voltage = np.array(temp[:read_cnt])

                        time_data.extend(curr_time.tolist())
                        voltage_data.extend(curr_voltage.tolist())

                        # 期望电压（简单对齐）
                        idx = np.minimum((curr_time * da_fs).astype(int), len(E_dac) - 1)
                        expected_data.extend(E_dac[idx].tolist())

                        collected += read_cnt

                        # 发送最近5个周期数据用于实时显示
                        if time_data and time_data[-1] > window:
                            mask = np.array(time_data) > (time_data[-1] - window)
                            self.data_updated.emit(
                                [time_data[i] for i in range(len(time_data)) if mask[i]],
                                [voltage_data[i] for i in range(len(voltage_data)) if mask[i]]
                            )

                time.sleep(0.005)

            # ====================== 保存数据 ======================
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"DPV_data_{timestamp}.txt"

            save_data = np.column_stack((time_data, expected_data, voltage_data))
            np.savetxt(filename, save_data, delimiter=',',
                       header="time,expected_voltage,actual_voltage",
                       comments='', fmt='%.6f')

            self.finished.emit(filename)

        except Exception as e:
            self.finished.emit(f"错误: {str(e)}")
        finally:
            # 停止 DA 和 ADC
            try:
                DAQdll.Set_DA_Scan(dev, 0, 500, 0)
                DAQdll.AD_Continu_Stop(dev)
                DAQdll.CloseUSB()
            except:
                pass


# ====================== 主窗口 ======================
class DPVWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("恒凯 USB6115-D - DPV 电化学测试平台")
        self.resize(1100, 750)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.status_label = QLabel("就绪 - 点击开始进行 DPV 测试")
        self.status_label.setStyleSheet("font-size: 14px; padding: 8px;")
        layout.addWidget(self.status_label)

        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("开始 DPV 采集")
        self.btn_stop = QPushButton("停止采集")
        self.btn_stop.setEnabled(False)

        self.btn_start.setStyleSheet("padding: 8px; font-size: 14px;")
        self.btn_stop.setStyleSheet("padding: 8px; font-size: 14px;")

        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        layout.addLayout(btn_layout)

        # PyQtGraph 实时曲线
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setLabel('left', '电压 (V)', **{'font-size': '12pt'})
        self.plot_widget.setLabel('bottom', '时间 (s)', **{'font-size': '12pt'})
        self.plot_widget.showGrid(x=True, y=True)
        self.curve = self.plot_widget.plot(pen=pg.mkPen(color='b', width=2.5), name='AI01 采集电压')
        layout.addWidget(self.plot_widget, stretch=1)

        # 连接信号
        self.btn_start.clicked.connect(self.start_acquisition)
        self.btn_stop.clicked.connect(self.stop_acquisition)

        self.acq_thread = None

    def start_acquisition(self):
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.status_label.setText("采集中...")

        params = {
            'E_init': -0.2,
            'E_final': 0.6,
            'E_incr': 0.004,
            'amplitude': 0.05,
            'pulse_width': 0.05,
            'pulse_period': 0.2,
            'quiet_time': 2.0
        }

        self.acq_thread = AcquisitionThread(params)
        self.acq_thread.data_updated.connect(self.update_realtime_plot)
        self.acq_thread.finished.connect(self.on_finished)
        self.acq_thread.start()

    def update_realtime_plot(self, t_list, v_list):
        if len(t_list) > 10:
            self.curve.setData(t_list, v_list)

    def stop_acquisition(self):
        if self.acq_thread:
            self.acq_thread.running = False
            self.status_label.setText("正在停止...")

    def on_finished(self, message):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

        if message.startswith("DPV_data"):
            self.status_label.setText(f"采集完成！数据已保存：{message}")
            QMessageBox.information(self, "完成", f"DPV 采集完成！\n数据文件：{message}")
        else:
            self.status_label.setText(f"采集结束 - {message}")
            QMessageBox.warning(self, "提示", message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DPVWindow()
    window.show()
    sys.exit(app.exec_())