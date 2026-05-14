import os
from ctypes import *
import numpy as np
import time
import matplotlib.pyplot as plt
from datetime import datetime

# ====================== 配置 ======================
dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Usb_Daq_V6505.dll")
DAQdll = WinDLL(dll_path)

dev = 0
ADC_RATE = 1000
V_MIN, V_MAX = -10.0, 10.0   # DA 默认量程

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

# ====================== 修复后的 DPV 波形生成 ======================
def generate_dpv_waveform(E_init, E_final, E_incr, amplitude, pulse_width, pulse_period, quiet_time):
    if E_incr <= 0:
        raise ValueError("E_incr 必须 > 0")
    if pulse_width > pulse_period:
        raise ValueError("pulse_width 不能大于 pulse_period")

    N_period = 100
    fs = 100.0 / pulse_period          # DAC 采样率
    if not (100 <= fs <= 10000):
        raise ValueError(f"DAC采样率 {fs:.1f} Hz 超出允许范围 [100, 10000] Hz")

    dt = 1.0 / fs
    N_pulse = int(round(pulse_width / pulse_period * N_period))
    N_base = N_period - N_pulse

    # 生成阶梯电位
    steps = []
    E = E_init
    while E < E_final:
        steps.append(E)
        E += E_incr
    steps.append(E_final)   # 确保包含终点
    steps = np.array(steps)

    # Quiet Time
    N_quiet = int(round(quiet_time * fs))
    E_quiet = np.full(N_quiet, E_init, dtype=float)

    # DPV 主体
    waveform = []
    for E_step in steps:
        base_part = np.full(N_base, E_step, dtype=float)
        pulse_part = np.full(N_pulse, E_step + amplitude, dtype=float)
        cycle = np.concatenate([base_part, pulse_part])
        waveform.append(cycle)

    E_main = np.concatenate(waveform)
    E_total = np.concatenate([E_quiet, E_main])
    t = np.arange(len(E_total)) * dt

    return t, E_total, fs   # 返回 fs 供 DA 使用

# ====================== 电压转 DA 码 ======================
def voltage_to_da(v):
    return int(((v - V_MIN) / (V_MAX - V_MIN)) * 65535 + 0.5)

# ====================== 主实验类 ======================
class DPVExperiment:
    def __init__(self):
        self.dev = 0
        self.adc_data = []
        self.expected_data = []
        self.time_data = []
        self.fig, self.ax = None, None
        self.line = None
        self.cycle_time = None

    def run(self, E_init=-0.2, E_final=0.6, E_incr=0.004, amplitude=0.05,
            pulse_width=0.05, pulse_period=0.2, quiet_time=2.0):

        # 生成波形
        t_dac, E_dac, da_fs = generate_dpv_waveform(E_init, E_final, E_incr, amplitude,
                                                    pulse_width, pulse_period, quiet_time)
        print(f"DPV波形生成完成: 总点数={len(E_dac)}, DAC采样率={da_fs:.1f} Hz")

        # 打开设备
        if DAQdll.OpenUSB() != 0:
            print("打开设备失败")
            return

        # 构造 DA 数据 (通道0)
        da_data = [(0 << 16) | voltage_to_da(v) for v in E_dac]
        da_array = (c_uint * len(da_data))(*da_data)

        # 启动 DA
        DAQdll.Set_DA_Scan(self.dev, 0, int(da_fs), 1)
        DAQdll.Sent_DaData(self.dev, len(da_data), da_array)
        print("DA 输出已启动")

        # 启动 ADC
        total_samples_est = int((len(E_dac)/da_fs + 1.0) * ADC_RATE) + 10000
        adc_buffer = (c_float * total_samples_est)()

        DAQdll.Ad_Continu_Conf(self.dev, 0, 0, 1, 0, ADC_RATE, 0, 0, 0, 0)
        print("ADC 采集已启动，开始边采边处理...")

        # 实时绘图初始化（显示最近5个周期）
        self.cycle_time = pulse_period
        self.fig, self.ax = plt.subplots(figsize=(10, 6))
        self.line, = self.ax.plot([], [], 'b-', lw=1.2)
        self.ax.set_xlabel('时间 (s)')
        self.ax.set_ylabel('电压 (V)')
        self.ax.set_title('DPV 实时采集波形 (最近 5 个周期)')
        self.ax.grid(True)

        collected = 0
        start_time = time.time()

        try:
            while True:
                buf_size = DAQdll.Get_AdBuf_Size(self.dev)
                if buf_size >= 1000:
                    to_read = min(buf_size, total_samples_est - collected)
                    temp = (c_float * to_read)()
                    read_cnt = DAQdll.Read_AdBuf(self.dev, temp, to_read)

                    if read_cnt > 0:
                        current_time = np.arange(collected, collected + read_cnt) / ADC_RATE
                        self.time_data.extend(current_time)
                        self.adc_data.extend(temp[:read_cnt])
                        # 期望电压（简单对齐，实际可做更好插值）
                        idx = np.minimum(np.floor(current_time * da_fs).astype(int), len(E_dac)-1)
                        self.expected_data.extend(E_dac[idx])

                        collected += read_cnt

                        # 实时更新最近5个周期
                        window = 5 * self.cycle_time
                        recent_idx = np.array(self.time_data) > (max(self.time_data) - window) if self.time_data else []
                        if len(recent_idx) > 0 and len(recent_idx) > 100:
                            self.line.set_data(self.time_data[-len(recent_idx):], self.adc_data[-len(recent_idx):])
                            self.ax.relim()
                            self.ax.autoscale_view()
                            plt.pause(0.001)

                if collected > len(E_dac) * (ADC_RATE / da_fs) * 1.2:   # 采集足够数据后退出
                    break

                time.sleep(0.002)

        finally:
            # 停止 DA 和 ADC
            DAQdll.Set_DA_Scan(self.dev, 0, int(da_fs), 0)
            DAQdll.AD_Continu_Stop(self.dev)
            DAQdll.CloseUSB()
            print("实验结束，DA 和 ADC 已停止")

        # ====================== 保存数据 ======================
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"DPV_data_{timestamp}.txt"

        data_save = np.column_stack((self.time_data, self.expected_data, self.adc_data))
        np.savetxt(filename, data_save, delimiter=',',
                  header="time,expected_voltage,actual_voltage", comments='', fmt='%.6f')
        print(f"数据已保存至: {filename}")

        # ====================== 完整绘图 ======================
        plt.figure(figsize=(12, 7))
        plt.plot(self.time_data, self.adc_data, 'b-', linewidth=1.0, label='实际采集电压 (AI01)')
        plt.xlabel('时间 (s)')
        plt.ylabel('电压 (V)')
        plt.title('DPV 完整采集波形')
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.show()


# ====================== 运行测试 ======================
if __name__ == "__main__":
    exp = DPVExperiment()
    # 示例参数（请根据实际电化学实验修改）
    exp.run(
        E_init=-0.2,
        E_final=0.6,
        E_incr=0.004,
        amplitude=0.05,
        pulse_width=0.05,
        pulse_period=0.2,      # 对应 DAC fs=500 Hz
        quiet_time=2.0
    )