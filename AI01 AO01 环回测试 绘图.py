import os
from ctypes import *
import numpy as np
import time
import sys
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

# ====================== 配置 ======================
dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Usb_Daq_V6505.dll")
DAQdll = WinDLL(dll_path)

dev = 0
DA_RATE = 200
ADC_RATE = 1000

V_SILENT = 0.1
V_HIGH = 0.2
V_LOW = 0.0

SILENT_TIME = 2.0
WAVE_TIME = 20.0
TOTAL_TIME = SILENT_TIME + WAVE_TIME + 0.8

# ====================== 打开设备 ======================
erro = DAQdll.OpenUSB()
print(f"OpenUSB 返回: {erro}")
if erro != 0:
    print("打开设备失败！")
    exit(1)


# ====================== DA 波形生成 ======================
def voltage_to_da(v):
    return int((v + 10.0) / 20.0 * 65535 + 0.5)


da_silent = voltage_to_da(V_SILENT)
da_high = voltage_to_da(V_HIGH)
da_low = voltage_to_da(V_LOW)

period_samples = int(DA_RATE / 10)
high_samples = int(period_samples * 0.4 + 0.5)
low_samples = period_samples - high_samples

one_period = [(0 << 16) | da_high] * high_samples + [(0 << 16) | da_low] * low_samples

wave_data = []
wave_data.extend([(0 << 16) | da_silent] * int(SILENT_TIME * DA_RATE))
wave_data.extend(one_period * int((WAVE_TIME * DA_RATE) / period_samples + 1))
wave_data = wave_data[:int((SILENT_TIME + WAVE_TIME) * DA_RATE)]

# ====================== 启动 DA ======================
erro = DAQdll.Set_DA_Scan(dev, 0, DA_RATE, 1)
erro = DAQdll.Sent_DaData(dev, len(wave_data), (c_uint * len(wave_data))(*wave_data))

# ====================== ADC 连续采集 ======================
READ_BLOCK = 200
total_samples = int(TOTAL_TIME * ADC_RATE)
adc_buffer = (c_float * total_samples)()

erro = DAQdll.Ad_Continu_Conf(dev, 0, 0, 1, 0, ADC_RATE, 0, 0, 0, 0)
print(f"开始ADC采集 {total_samples} 个点...")
t0 = time.time()

# ====================== 初始化 PyQtGraph 实时绘图 ======================
app = QApplication(sys.argv)
win = pg.GraphicsLayoutWidget(title="实时采集波形 (AI01)")
win.resize(1000, 600)
plot = win.addPlot(title="电压 vs 时间")
plot.setLabel('left', '电压 (V)')
plot.setLabel('bottom', '时间 (秒)')
plot.addLegend()
plot.setYRange(-0.5, 0.5)  # 根据你的电压范围预设Y轴
curve = plot.plot(pen='b', name='实际采集')
# 绘制期望静默电压参考线
h_line = pg.InfiniteLine(pos=V_SILENT, angle=0, pen='r', name=f'期望静默 {V_SILENT}V')
plot.addItem(h_line)
win.show()

collected = 0


def update_plot():
    global collected
    # 查询并读取数据
    buf_size = DAQdll.Get_AdBuf_Size(dev)
    if buf_size >= READ_BLOCK and collected < total_samples:
        to_read = min(READ_BLOCK, total_samples - collected)
        temp_buf = (c_float * to_read)()
        read_cnt = DAQdll.Read_AdBuf(dev, temp_buf, to_read)
        if read_cnt > 0:
            adc_buffer[collected:collected + read_cnt] = temp_buf[:read_cnt]
            collected += read_cnt

            # 实时更新曲线数据
            t_adc = np.arange(collected) / ADC_RATE
            curve.setData(t_adc, np.array(adc_buffer[:collected]))

    # 采集完成后自动退出
    if collected >= total_samples:
        timer.stop()
        DAQdll.AD_Continu_Stop(dev)
        DAQdll.Set_DA_Scan(dev, 0, DA_RATE, 0)
        DAQdll.CloseUSB()
        print(f"采集完成！耗时: {time.time() - t0:.2f} 秒")
        # 稍微延迟后退出GUI，确保最后一帧绘制完成
        QTimer.singleShot(1000, app.quit)


# 使用定时器每 30ms (约33fps) 刷新一次界面
timer = QTimer()
timer.timeout.connect(update_plot)
timer.start(30)

sys.exit(app.exec_())