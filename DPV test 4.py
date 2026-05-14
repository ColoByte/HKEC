import os
import time
from ctypes import *
import numpy as np
import matplotlib.pyplot as plt
from PyQt5 import QtWidgets, QtCore
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# 配置部分
dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Usb_Daq_V6505.dll")
DAQdll = WinDLL(dll_path)
dev = 0  # 默认设备号
DA_RATE = 200  # DAC输出频率
ADC_RATE = 1000  # ADC采样频率
BUFFER_SIZE = 1000  # 缓冲区大小


# DPV波形生成函数
def generate_dpv_waveform(
        E_init,
        E_final,
        E_incr,
        amplitude,
        pulse_width,
        pulse_period,
        quiet_time
):
    """
    生成DPV激励波形

    返回：
        t : 时间数组
        E : 电压数组
    """

    # ---------- 参数检查 ----------
    if E_incr <= 0:
        raise ValueError("E_incr 必须 > 0")

    if pulse_width > pulse_period:
        raise ValueError("pulse_width 不能大于 pulse_period")

    # ---------- 采样参数 ----------
    N_period = 100
    fs = 100 / pulse_period
    dt = 1 / fs

    # ---------- 周期内结构 ----------
    N_pulse = int(round(pulse_width / pulse_period * N_period))
    N_base = N_period - N_pulse

    # ---------- 阶梯序列（允许微偏）----------
    steps = []
    E = E_init

    while True:
        steps.append(E)
        E += E_incr
        if E >= E_final:
            steps.append(E)
            break

    steps = np.array(steps)

    # ---------- Quiet Time ----------
    N_quiet = int(round(quiet_time * fs))
    E_quiet = np.full(N_quiet, E_init)

    # ---------- DPV主体 ----------
    waveform = []

    for E_step in steps:
        base_part = np.full(N_base, E_step)
        pulse_part = np.full(N_pulse, E_step + amplitude)

        cycle = np.concatenate([base_part, pulse_part])
        waveform.append(cycle)

    E_main = np.concatenate(waveform) if len(waveform) > 0 else np.array([])

    # ---------- 合并 ----------
    E_total = np.concatenate([E_quiet, E_main])

    # ---------- 时间轴 ----------
    t = np.arange(len(E_total)) * dt

    return t, E_total


# DAC电压转换函数
def voltage_to_da(voltage):
    # 假设电压范围在 -10V 到 +10V 之间转换为 16 位无符号整数
    return int((voltage + 10) * 32767 / 10)


# PyQt5 界面初始化
class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.is_collecting = False  # 标志位，是否正在采集
        self.collect_data = []  # 存储采集的数据

    def initUI(self):
        self.setWindowTitle('电化学测试上位机')
        self.setGeometry(100, 100, 800, 600)

        # 按钮
        self.start_button = QtWidgets.QPushButton('开始采集', self)
        self.start_button.clicked.connect(self.start_collecting)
        self.stop_button = QtWidgets.QPushButton('紧急停止', self)
        self.stop_button.clicked.connect(self.stop_collecting)

        # 波形显示区域（使用matplotlib的FigureCanvas）
        self.fig, self.ax = plt.subplots(figsize=(8, 5))
        self.canvas = FigureCanvas(self.fig)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.addWidget(self.start_button)
        self.layout.addWidget(self.stop_button)
        self.layout.addWidget(self.canvas)

    def start_collecting(self):
        # 启动 DA 输出波形
        # 生成DPV波形
        t, E = generate_dpv_waveform(E_init=-0.2, E_final=0.2, E_incr=0.004, amplitude=0.05, pulse_width=0.05,
                                     pulse_period=0.5, quiet_time=2)

        # 将波形数据写入 DA 输出
        data_array = (c_uint * len(E))(*[voltage_to_da(v) for v in E])
        erro = DAQdll.Sent_DaData(dev, len(E), data_array)

        # 启动 ADC 采集
        total_samples = int((2 + 2) * ADC_RATE)  # 两个周期的数据量
        adc_buffer = (c_float * total_samples)()

        erro = DAQdll.Ad_Continu_Conf(dev, 0, 0, 1, 0, ADC_RATE, 0, 0, 0, 0)

        # 采集数据并更新显示
        self.is_collecting = True
        self.collect_data.clear()
        self.collect_loop()

    def stop_collecting(self):
        # 停止 DA 输出和 ADC 采集
        DAQdll.Set_DA_Scan(dev, 0, DA_RATE, 0)
        DAQdll.AD_Continu_Stop(dev)
        self.is_collecting = False
        print("采集已停止")

    def collect_loop(self):
        # 采集数据并更新图形
        if not self.is_collecting:
            return

        collected = 0
        while collected < BUFFER_SIZE:
            buf_size = DAQdll.Get_AdBuf_Size(dev)
            if buf_size > 0:
                to_read = min(buf_size, BUFFER_SIZE - collected)
                temp_buf = (c_float * to_read)()
                read_cnt = DAQdll.Read_AdBuf(dev, temp_buf, to_read)
                if read_cnt > 0:
                    self.collect_data.extend(temp_buf[:read_cnt])
                    collected += read_cnt

            time.sleep(0.001)

        # 更新图形显示
        adc_array = np.array(self.collect_data)
        self.ax.clear()
        self.ax.plot(np.arange(len(adc_array)) / ADC_RATE, adc_array, label='ADC Data')
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Voltage (V)')
        self.ax.legend()
        self.canvas.draw()

        # 数据保存
        np.savetxt("adc_data.csv", np.column_stack((np.arange(len(adc_array)) / ADC_RATE, adc_array)), delimiter=",",
                   header="Time (s), Voltage (V)", comments="")


# 启动PyQt5应用
app = QtWidgets.QApplication([])
window = MainWindow()
window.show()
app.exec_()