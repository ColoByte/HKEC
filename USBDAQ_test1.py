# # from ctypes import *
# # import numpy as np
# # import time
# # import matplotlib.pyplot as plt
# #
# # #调用dll库文件
# # DAQdll = WinDLL("Usb_Daq_V6505.dll")
#
# import os
# from ctypes import *
# import numpy as np
# import time
# import matplotlib.pyplot as plt
#
# # 获取当前脚本所在目录
# current_dir = os.path.dirname(os.path.abspath(__file__))
# dll_path = os.path.join(current_dir, "Usb_Daq_V6505.dll")
#
# # 使用完整路径调用dll
# DAQdll = WinDLL(dll_path)
#
# #首先打开设备
# erro=DAQdll.OpenUSB()
# print(erro)
#
# #采样率100K
# sample_rate=10000
# #采样时间1s
# sample_time=1
# #采样通道0~4
# sample_channel=4
# #计算首个采样通道
# ch_first=0
# #计算最后采样通道
# ch_last=ch_first+sample_channel-1
# #计算所需要采样的数据点个数
# length=int(sample_time*sample_rate)
# #定义规定数据点个数的数组
# addata=(c_float*length)()
#
# #输出时间
# t1=time.time()
# #使用连续采样函数采集数据
# erro =DAQdll.Ad_Continu(0,ch_first,ch_last,1,0,sample_rate ,0,0,0,0,length,byref(addata))
#
# #输出采样总时间(上位机)
# print(time.time()-t1)
# #关闭设备
# erro=DAQdll.CloseUSB()
# #计算采样所得结果的实际电压值
#
# vol=[]
# cur=[]
# voll=[]
# curr=[]
# for i in range(0,2500):  #采样100K个数据，4通道，每个通道25000个
# 	vol.append(addata[i*4])  #通道1数据
# 	cur.append(addata[i*4+1])#通道2数据
# 	voll.append(addata[i*4+2])#通道3数据
# 	curr.append(addata[i*4+3])#通道4数据
# result1=np.array(vol)  #换算通道1数据
# result2=np.array(cur)  #换算通道2数据
# result3=np.array(voll)  #换算通道3数据
# result4=np.array(curr)  #换算通道4数据
# #绘图
# plt.figure()
# plt.plot(result1)#显示通道1数据
# plt.plot(result2)#显示通道2数据
# plt.plot(result3)#显示通道3数据
#
#
# plt.xlabel('Sample Points')
# plt.ylabel('Voltage')
# plt.title('Multi-channel Data Acquisition')
# plt.legend(['Channel 1', 'Channel 2', 'Channel 3', 'Channel 4'])
# plt.grid(True)
# plt.show()  # 这行很重要！

import os
from ctypes import *
import numpy as np
import time
import matplotlib.pyplot as plt

# 获取当前脚本所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))
dll_path = os.path.join(current_dir, "Usb_Daq_V6505.dll")

# 使用完整路径调用dll
DAQdll = WinDLL(dll_path)

# 首先打开设备
erro = DAQdll.OpenUSB()
print(f"OpenUSB Error Code: {erro}")

# 采样率100K
sample_rate = 10000
# 采样时间1s
sample_time = 1
# 采样通道0~4
sample_channel = 4
# 计算首个采样通道
ch_first = 0
# 计算最后采样通道
ch_last = ch_first + sample_channel - 1
# 计算所需要采样的数据点个数
length = int(sample_time * sample_rate)
# 定义规定数据点个数的数组
addata = (c_float * length)()

# 输出时间
t1 = time.time()
# 使用连续采样函数采集数据
erro = DAQdll.Ad_Continu(0, ch_first, ch_last, 1, 0, sample_rate, 0, 0, 0, 0, length, byref(addata))

# 输出采样总时间(上位机)
print(f"Sampling Time: {time.time() - t1}s")
# 关闭设备
erro = DAQdll.CloseUSB()

# 计算采样所得结果的实际电压值
vol = []
cur = []
voll = []
curr = []

# 注意：这里原代码循环写的是2500，如果length变化，建议用 length // 4
for i in range(0, 2500):
    vol.append(addata[i * 4])       # 通道1数据
    cur.append(addata[i * 4 + 1])   # 通道2数据
    voll.append(addata[i * 4 + 2])  # 通道3数据
    curr.append(addata[i * 4 + 3])  # 通道4数据

result1 = np.array(vol)
result2 = np.array(cur)
result3 = np.array(voll)
result4 = np.array(curr)

# --- 修改部分开始 ---

# 设置想要显示的点数（例如：只显示前200个点，这样就能看到清晰的周期）
points_to_show = 200

# 生成对应的横坐标 x轴 (从0到 points_to_show)
x_axis = np.arange(points_to_show)

plt.figure(figsize=(10, 6))

# 绘图时，使用切片 [:points_to_show] 只取前 N 个数据
plt.plot(x_axis, result1[:points_to_show], label='Channel 1')
plt.plot(x_axis, result2[:points_to_show], label='Channel 2')
plt.plot(x_axis, result3[:points_to_show], label='Channel 3')

plt.xlabel('Sample Points')
plt.ylabel('Voltage')
plt.title(f'Multi-channel Data Acquisition (First {points_to_show} points)')
plt.legend()
plt.grid(True)
plt.show()

# --- 修改部分结束 ---