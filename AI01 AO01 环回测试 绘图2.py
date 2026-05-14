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
TOTAL_TIME = SILENT_TIME + WAVE_TIME + 0.8  # 多留一点余量

# ====================== 打开设备 ======================
erro = DAQdll.OpenUSB()
print(f"OpenUSB 返回: {erro}")
if erro != 0:
    print("打开设备失败！")
    exit(1)


# ====================== DA 波形生成 ======================
def voltage_to_da(v):
    return int((v + 10.0) / 20.0 * 65535 + 0.5)  # 四舍五入


da_silent = voltage_to_da(V_SILENT)
da_high = voltage_to_da(V_HIGH)
da_low = voltage_to_da(V_LOW)

period_samples = int(DA_RATE / 10)
high_samples = int(period_samples * 0.4 + 0.5)
low_samples = period_samples - high_samples

print(f"DA周期点数: {period_samples} (高:{high_samples}, 低:{low_samples})")
print(f"DA码值 -> 静默:{da_silent}, 高:{da_high}, 低:{da_low}")

# 生成一个周期数据 (DA0通道)
one_period = [(0 << 16) | da_high] * high_samples + [(0 << 16) | da_low] * low_samples

# 生成完整波形
wave_data = []
wave_data.extend([(0 << 16) | da_silent] * int(SILENT_TIME * DA_RATE))
wave_data.extend(one_period * int((WAVE_TIME * DA_RATE) / period_samples + 1))
wave_data = wave_data[:int((SILENT_TIME + WAVE_TIME) * DA_RATE)]  # 精确截取

print(f"总DA数据点数: {len(wave_data)}")

# ====================== 启动 DA ======================
erro = DAQdll.Set_DA_Scan(dev, 0, DA_RATE, 1)
print(f"Set_DA_Scan 返回: {erro}")

data_array = (c_uint * len(wave_data))(*wave_data)
erro = DAQdll.Sent_DaData(dev, len(wave_data), data_array)
print(f"Sent_DaData 返回: {erro}")

# ====================== ADC 连续采集准备 ======================
READ_BLOCK = 200
total_samples = int(TOTAL_TIME * ADC_RATE)
adc_buffer = (c_float * total_samples)()

print(f"开始ADC采集 {total_samples} 个点 (理论 {TOTAL_TIME:.1f}s)...")
t0 = time.time()

# 配置并启动连续采集
erro = DAQdll.Ad_Continu_Conf(dev, 0, 0, 1, 0, ADC_RATE, 0, 0, 0, 0)
print(f"Ad_Continu_Conf 返回: {erro}")

collected = 0

# ====================== 初始化 PyQtGraph 实时绘图 ======================

# ⬇️ 必须先设置全局背景和前景色，再创建窗口
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')  # 字体和坐标轴设为黑色

app = QApplication(sys.argv)
win = pg.GraphicsLayoutWidget(title="实时采集波形 (AI01)")
win.resize(1000, 600)

plot = win.addPlot(title="V/t")
plot.setLabel('left', '电压 (V)')
plot.setLabel('bottom', '时间 (秒)')
plot.addLegend()
plot.setYRange(-0.5, 0.5)  # 预设Y轴范围
plot.setXRange(0, 0.8)  # 初始X轴展示区间固定为0.5秒

# 波形调成红色 (pen='r')
curve = plot.plot(pen='r', name='实际采集')

# 绘制期望静默电压参考线
h_line = pg.InfiniteLine(pos=V_SILENT, angle=0, pen='g', name=f'期望静默 {V_SILENT}V')
plot.addItem(h_line)
win.show()

# ====================== 核心采集与绘图循环 ======================
def acquisition_and_plot_task():
    global collected

    # 1. 查询板卡缓存中的数据量
    buf_size = DAQdll.Get_AdBuf_Size(dev)

    # 保留你原有的打印逻辑
    if buf_size > 0:
        print(time.strftime("%H:%M:%S", time.localtime()))
        print(f"缓存={buf_size}, 已采={collected}")

    # 2. 累积到200点再读一次
    if buf_size >= READ_BLOCK and collected < total_samples:
        to_read = min(READ_BLOCK, total_samples - collected)
        temp_buf = (c_float * to_read)()
        read_cnt = DAQdll.Read_AdBuf(dev, temp_buf, to_read)

        if read_cnt > 0:
            adc_buffer[collected:collected + read_cnt] = temp_buf[:read_cnt]
            collected += read_cnt

            # 3. 实时更新波形图
            t_adc = np.arange(collected) / ADC_RATE
            curve.setData(t_adc, np.array(adc_buffer[:collected]))

            # 4. 动态更新X轴展示区间，始终保持0.5s的滑动窗口
            # 如果采集时间不足0.5s，从0开始；否则窗口向右平移
            current_time = t_adc[-1]
            if current_time > 0.5:
                plot.setXRange(current_time - 0.5, current_time)
            else:
                plot.setXRange(0, 0.5)

    # 5. 采集完成后的退出逻辑
    if collected >= total_samples:
        timer.stop()
        DAQdll.AD_Continu_Stop(dev)
        print(f"实际采集耗时: {time.time() - t0:.2f} 秒，采集到 {collected} 个点")

        DAQdll.Set_DA_Scan(dev, 0, DA_RATE, 0)
        DAQdll.CloseUSB()
        print("测试完成，设备已关闭")

        QTimer.singleShot(1000, app.quit)


# 使用 QTimer 每 30ms 触发一次采集和绘图任务
timer = QTimer()
timer.timeout.connect(acquisition_and_plot_task)
timer.start(30)

# 启动 Qt 事件循环
sys.exit(app.exec_())