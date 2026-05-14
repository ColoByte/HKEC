import sys
import os
import time
from ctypes import *
import numpy as np
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel, QGraphicsScene, QGraphicsView, QGraphicsLineItem
from PyQt5.QtCore import QThread, pyqtSignal

# ====================== 配置 ======================
dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Usb_Daq_V6505.dll")
DAQdll = WinDLL(dll_path)

dev = 0
DA_RATE = 200  # DA输出波形的频率
ADC_RATE = 1000  # ADC采样率
V_SILENT = 0.1  # 静默电压
V_HIGH = 0.2  # 高电压
V_LOW = 0.0  # 低电压

SILENT_TIME = 2.0  # 静默时间
WAVE_TIME = 2.0  # 波形时间
TOTAL_TIME = SILENT_TIME + WAVE_TIME + 0.8  # 总时间

# ====================== DA 波形生成 ======================
def voltage_to_da(v):
    return int((v + 10.0) / 20.0 * 65535 + 0.5)  # 四舍五入

da_silent = voltage_to_da(V_SILENT)
da_high = voltage_to_da(V_HIGH)
da_low = voltage_to_da(V_LOW)

period_samples = int(DA_RATE / 10)
high_samples = int(period_samples * 0.4 + 0.5)
low_samples = period_samples - high_samples

# 生成一个周期数据 (DA0通道)
one_period = [(0 << 16) | da_high] * high_samples + [(0 << 16) | da_low] * low_samples

# 生成完整波形
wave_data = []
wave_data.extend([(0 << 16) | da_silent] * int(SILENT_TIME * DA_RATE))
wave_data.extend(one_period * int((WAVE_TIME * DA_RATE) / period_samples + 1))
wave_data = wave_data[:int((SILENT_TIME + WAVE_TIME) * DA_RATE)]  # 精确截取

# ====================== 打开设备 ======================
erro = DAQdll.OpenUSB()
print(f"OpenUSB 返回: {erro}")
if erro != 0:
    print("打开设备失败！")
    exit(1)

# ====================== DA 输出 ======================
erro = DAQdll.Set_DA_Scan(dev, 0, DA_RATE, 1)
print(f"Set_DA_Scan 返回: {erro}")

data_array = (c_uint * len(wave_data))(*wave_data)
erro = DAQdll.Sent_DaData(dev, len(wave_data), data_array)
print(f"Sent_DaData 返回: {erro}")

# ====================== ADC 连续采集 ======================
def collect_adc_data(total_samples):
    adc_buffer = (c_float * total_samples)()
    print(f"开始ADC采集 {total_samples} 个点 (理论 {TOTAL_TIME:.1f}s)...")
    t0 = time.time()

    # 配置并启动连续采集
    erro = DAQdll.Ad_Continu_Conf(dev, 0, 0, 1, 0, ADC_RATE, 0, 0, 0, 0)
    if erro != 0:
        print("ADC配置失败！")
        return None

    collected = 0
    while collected < total_samples:
        buf_size = DAQdll.Get_AdBuf_Size(dev)
        if buf_size > 0:
            to_read = min(buf_size, total_samples - collected)
            temp_buf = (c_float * to_read)()
            read_cnt = DAQdll.Read_AdBuf(dev, temp_buf, to_read)
            if read_cnt > 0:
                adc_buffer[collected:collected + read_cnt] = temp_buf[:read_cnt]
                collected += read_cnt
        time.sleep(0.001)  # 避免CPU占用过高

    DAQdll.AD_Continu_Stop(dev)
    print(f"实际采集耗时: {time.time() - t0:.2f} 秒，采集到 {collected} 个点")
    return np.array(adc_buffer[:collected])

# ====================== 保存波形 ======================
def save_waveform(t, E):
    timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    file_path = f"dpv_waveform_{timestamp}.txt"
    data = np.column_stack((t, E))
    np.savetxt(file_path, data, delimiter=",", header="time,voltage", comments="", fmt="%.6f")
    print(f"数据已保存: {file_path}")

# ====================== 数据采集线程 ======================
class DataAcquisitionThread(QThread):
    update_signal = pyqtSignal(np.ndarray, np.ndarray)

    def __init__(self, params):
        super().__init__()
        self.params = params
        self.stop_flag = False

    def run(self):
        # 设置采集参数
        E_init = self.params['E_init']
        E_final = self.params['E_final']
        E_incr = self.params['E_incr']
        pulse_width = self.params['pulse_width']
        pulse_period = self.params['pulse_period']
        quiet_time = self.params['quiet_time']

        # 生成DPV波形
        t, E_total = self.generate_dpv_waveform(E_init, E_final, E_incr, pulse_width, pulse_period, quiet_time)

        # 启动DA输出波形
        self.send_da_data(t, E_total)

        # 启动ADC采集
        total_samples = int(TOTAL_TIME * ADC_RATE)
        adc_data = collect_adc_data(total_samples)

        # 实时更新波形
        if adc_data is not None:
            self.update_signal.emit(np.arange(len(adc_data)) / ADC_RATE, adc_data)

    def send_da_data(self, t, E_total):
        """
        将生成的波形数据发送到DA设备
        """
        wave_data = [int((e + 10.0) / 20.0 * 65535 + 0.5) for e in E_total]  # 将电压转换为DA设备可接受的值
        data_array = (c_uint * len(wave_data))(*wave_data)
        erro = DAQdll.Sent_DaData(dev, len(wave_data), data_array)  # 发送DA数据
        if erro != 0:
            print("发送DA数据失败！")

    def generate_dpv_waveform(self, E_init, E_final, E_incr, pulse_width, pulse_period, quiet_time):
        N_period = 100
        fs = 100 / pulse_period
        dt = 1 / fs

        N_pulse = int(round(pulse_width / pulse_period * N_period))
        N_base = N_period - N_pulse

        steps = []
        E = E_init
        while True:
            steps.append(E)
            E += E_incr
            if E >= E_final:
                steps.append(E)
                break
        steps = np.array(steps)

        N_quiet = int(round(quiet_time * fs))
        E_quiet = np.full(N_quiet, E_init)

        waveform = []
        for E_step in steps:
            base_part = np.full(N_base, E_step)
            pulse_part = np.full(N_pulse, E_step + 0.05)
            cycle = np.concatenate([base_part, pulse_part])
            waveform.append(cycle)

        E_main = np.concatenate(waveform) if len(waveform) > 0 else np.array([])

        E_total = np.concatenate([E_quiet, E_main])
        t = np.arange(len(E_total)) * dt
        return t, E_total

# ====================== PyQt界面 ======================
class WaveformDisplay(QWidget):
    def __init__(self):
        super().__init__()

        # 默认参数
        self.params = {
            'E_init': -0.2,
            'E_final': 0.2,
            'E_incr': 0.004,
            'pulse_width': 0.05,
            'pulse_period': 0.5,
            'quiet_time': 2
        }

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # 参数输入框
        self.param_widgets = {}
        for param, default in self.params.items():
            h_layout = QHBoxLayout()
            label = QLabel(param)
            input_field = QLineEdit(str(default))
            h_layout.addWidget(label)
            h_layout.addWidget(input_field)
            layout.addLayout(h_layout)
            self.param_widgets[param] = input_field

        # 按钮
        start_button = QPushButton("开始采集")
        start_button.clicked.connect(self.start_acquisition)
        layout.addWidget(start_button)

        stop_button = QPushButton("紧急停止")
        stop_button.clicked.connect(self.stop_acquisition)
        layout.addWidget(stop_button)

        # QGraphicsView绘图区域
        self.graphics_view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.graphics_view.setScene(self.scene)
        layout.addWidget(self.graphics_view)

        self.setLayout(layout)

    def start_acquisition(self):
        params = {param: float(self.param_widgets[param].text()) for param in self.params}
        self.acquisition_thread = DataAcquisitionThread(params)
        self.acquisition_thread.update_signal.connect(self.update_waveform)
        self.acquisition_thread.start()

    def stop_acquisition(self):
        if hasattr(self, 'acquisition_thread'):
            self.acquisition_thread.stop()

    def update_waveform(self, t, E):
        self.scene.clear()  # 清空现有的图形

        # 绘制新的波形
        for i in range(len(t) - 1):
            line = QGraphicsLineItem(t[i] * 100, E[i] * 100, t[i+1] * 100, E[i+1] * 100)  # 绘制线段
            self.scene.addItem(line)

        save_waveform(t, E)

# ====================== 程序入口 ======================
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = WaveformDisplay()
    window.show()
    sys.exit(app.exec_())