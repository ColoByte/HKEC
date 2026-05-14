# import os
# from ctypes import *
# import numpy as np
# import time
# import matplotlib.pyplot as plt
#
# # ====================== 配置 ======================
# dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Usb_Daq_V6505.dll")
# DAQdll = WinDLL(dll_path)
#
# dev = 0
# DA_RATE = 200
# ADC_RATE = 1000
# Cycle_num = 5
#
# V_SILENT = 0.1
# V_HIGH = 0.2
# V_LOW = 0.0
#
# SILENT_TIME = 2.0
# WAVE_TIME = 2.0
# TOTAL_TIME = SILENT_TIME + WAVE_TIME + 0.8   # 多留一点余量
#
# # ====================== 中文显示 ======================
# plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
# plt.rcParams['axes.unicode_minus'] = False
#
# # ====================== 打开设备 ======================
# erro = DAQdll.OpenUSB()
# print(f"OpenUSB 返回: {erro}")
# if erro != 0:
#     print("打开设备失败！")
#     exit(1)
#
# # ====================== DA 波形生成 ======================
# def voltage_to_da(v):
#     return int((v + 10.0) / 20.0 * 65535 + 0.5)   # 四舍五入
#
# da_silent = voltage_to_da(V_SILENT)
# da_high   = voltage_to_da(V_HIGH)
# da_low    = voltage_to_da(V_LOW)
#
# period_samples = int(DA_RATE / Cycle_num)
# high_samples = int(period_samples * 0.4 + 0.5)
# low_samples = period_samples - high_samples
#
# print(f"DA周期点数: {period_samples} (高:{high_samples}, 低:{low_samples})")
# print(f"DA码值 -> 静默:{da_silent}, 高:{da_high}, 低:{da_low}")
#
# # 生成一个周期数据 (DA0通道)
# one_period = [(0 << 16) | da_high] * high_samples + [(0 << 16) | da_low] * low_samples
#
# # 生成完整波形
# wave_data = []
# wave_data.extend( [(0 << 16) | da_silent] * int(SILENT_TIME * DA_RATE) )
# wave_data.extend( one_period * int((WAVE_TIME * DA_RATE) / period_samples + 1) )
# wave_data = wave_data[:int((SILENT_TIME + WAVE_TIME) * DA_RATE)]   # 精确截取
#
# print(f"总DA数据点数: {len(wave_data)}")
#
# # ====================== 启动 DA ======================
# erro = DAQdll.Set_DA_Scan(dev, 0, DA_RATE, 1)
# print(f"Set_DA_Scan 返回: {erro}")
#
# data_array = (c_uint * len(wave_data))(*wave_data)
# erro = DAQdll.Sent_DaData(dev, len(wave_data), data_array)
# print(f"Sent_DaData 返回: {erro}")
#
# # ====================== ADC 连续采集（改进版） ======================
# total_samples = int(TOTAL_TIME * ADC_RATE)
# adc_buffer = (c_float * total_samples)()
#
# print(f"开始ADC采集 {total_samples} 个点 (理论 {TOTAL_TIME:.1f}s)...")
# t0 = time.time()
#
# # 配置并启动连续采集
# erro = DAQdll.Ad_Continu_Conf(dev, 0, 0, 1, 0, ADC_RATE, 0, 0, 0, 0)
# print(f"Ad_Continu_Conf 返回: {erro}")
#
# collected = 0
# while collected < total_samples:
#     buf_size = DAQdll.Get_AdBuf_Size(dev)
#     if buf_size > 0:
#         to_read = min(buf_size, total_samples - collected)
#         temp_buf = (c_float * to_read)()
#         read_cnt = DAQdll.Read_AdBuf(dev, temp_buf, to_read)
#         if read_cnt > 0:
#             adc_buffer[collected:collected+read_cnt] = temp_buf[:read_cnt]
#             collected += read_cnt
#     time.sleep(0.001)   # 避免CPU占用过高
#
# DAQdll.AD_Continu_Stop(dev)
# print(f"实际采集耗时: {time.time() - t0:.2f} 秒，采集到 {collected} 个点")
#
# # ====================== 停止 DA 并关闭 ======================
# DAQdll.Set_DA_Scan(dev, 0, DA_RATE, 0)
# DAQdll.CloseUSB()
# print("测试完成，设备已关闭")
#
# # ====================== 绘图 ======================
# adc_array = np.array(adc_buffer[:collected])
#
# t_adc = np.arange(len(adc_array)) / ADC_RATE
#
# plt.figure(figsize=(12, 7))
# plt.plot(t_adc, adc_array, 'b-', linewidth=1.2, label='实际采集 (AI01)')
# plt.plot([0, TOTAL_TIME], [V_SILENT, V_SILENT], 'r--', linewidth=1.5, label='期望静默电压 0.1V')
# plt.axvspan(SILENT_TIME, SILENT_TIME + WAVE_TIME, alpha=0.15, color='orange', label='方波区间')
#
# plt.xlabel('时间 (秒)')
# plt.ylabel('电压 (V)')
# plt.title('USB6115-D AO01 → AI01 环回测试\n10Hz 方波 (占空比0.4, 0.0~0.2V)，静默0.1V')
# plt.grid(True, alpha=0.3)
# plt.legend()
# plt.xlim(0, TOTAL_TIME)
# plt.tight_layout()
# plt.show()

#修改为200点读取一次
import os
from ctypes import *
import numpy as np
import time
import matplotlib.pyplot as plt

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
WAVE_TIME = 2.0
TOTAL_TIME = SILENT_TIME + WAVE_TIME + 0.8   # 多留一点余量

# ====================== 中文显示 ======================
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# ====================== 打开设备 ======================
erro = DAQdll.OpenUSB()
print(f"OpenUSB 返回: {erro}")
if erro != 0:
    print("打开设备失败！")
    exit(1)

# ====================== DA 波形生成 ======================
def voltage_to_da(v):
    return int((v + 10.0) / 20.0 * 65535 + 0.5)   # 四舍五入

da_silent = voltage_to_da(V_SILENT)
da_high   = voltage_to_da(V_HIGH)
da_low    = voltage_to_da(V_LOW)

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
wave_data = wave_data[:int((SILENT_TIME + WAVE_TIME) * DA_RATE)]   # 精确截取

print(f"总DA数据点数: {len(wave_data)}")

# ====================== 启动 DA ======================
erro = DAQdll.Set_DA_Scan(dev, 0, DA_RATE, 1)
print(f"Set_DA_Scan 返回: {erro}")

data_array = (c_uint * len(wave_data))(*wave_data)
erro = DAQdll.Sent_DaData(dev, len(wave_data), data_array)
print(f"Sent_DaData 返回: {erro}")

# ====================== ADC 连续采集（每200点读取一次） ======================
READ_BLOCK = 200

total_samples = int(TOTAL_TIME * ADC_RATE)
adc_buffer = (c_float * total_samples)()

print(f"开始ADC采集 {total_samples} 个点 (理论 {TOTAL_TIME:.1f}s)...")
t0 = time.time()

# 配置并启动连续采集
erro = DAQdll.Ad_Continu_Conf(dev, 0, 0, 1, 0, ADC_RATE, 0, 0, 0, 0)
print(f"Ad_Continu_Conf 返回: {erro}")

collected = 0

while collected < total_samples:

    # 查询板卡缓存中的数据量
    buf_size = DAQdll.Get_AdBuf_Size(dev)

    if buf_size > 0:
        print(time.strftime("%H:%M:%S", time.localtime()))
        print(f"缓存={buf_size}, 已采={collected}")


    # 累积到200点再读一次
    if buf_size >= READ_BLOCK:

        # 防止最后一次超出目标长度
        to_read = min(READ_BLOCK, total_samples - collected)

        temp_buf = (c_float * to_read)()

        read_cnt = DAQdll.Read_AdBuf(dev, temp_buf, to_read)

        if read_cnt > 0:
            adc_buffer[collected:collected + read_cnt] = temp_buf[:read_cnt]
            collected += read_cnt

    time.sleep(0.1)   # 避免CPU占用过高


DAQdll.AD_Continu_Stop(dev)
print(f"实际采集耗时: {time.time() - t0:.2f} 秒，采集到 {collected} 个点")

# ====================== 停止 DA 并关闭 ======================
DAQdll.Set_DA_Scan(dev, 0, DA_RATE, 0)
DAQdll.CloseUSB()
print("测试完成，设备已关闭")

# ====================== 绘图 ======================
adc_array = np.array(adc_buffer[:collected])

t_adc = np.arange(len(adc_array)) / ADC_RATE

plt.figure(figsize=(12, 7))
plt.plot(t_adc, adc_array, 'b-', linewidth=1.2, label='实际采集 (AI01)')
plt.plot([0, TOTAL_TIME], [V_SILENT, V_SILENT], 'r--', linewidth=1.5, label='期望静默电压 0.1V')
plt.axvspan(SILENT_TIME, SILENT_TIME + WAVE_TIME,
            alpha=0.15, color='orange', label='方波区间')

plt.xlabel('时间 (秒)')
plt.ylabel('电压 (V)')
plt.title('USB6115-D AO01 → AI01 环回测试\n10Hz 方波 (占空比0.4, 0.0~0.2V)，静默0.1V')

plt.grid(True, alpha=0.3)
plt.legend()
plt.xlim(0, TOTAL_TIME)

plt.tight_layout()
plt.show()