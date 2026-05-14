import matplotlib.pyplot as plt
from dpv_waveform import generate_dpv_waveform, save_waveform

# ===== 参数（你给的参考值）=====
E_init = -0.2
E_final = 0.2
E_incr = 0.004

amplitude = 0.05
pulse_width = 0.05
pulse_period = 0.5

quiet_time = 2

# ===== 生成波形 =====
t, E = generate_dpv_waveform(
    E_init,
    E_final,
    E_incr,
    amplitude,
    pulse_width,
    pulse_period,
    quiet_time
)

# ===== 保存 =====
save_waveform("dpv_waveform.csv", t, E)

# ===== 全局图 =====
plt.figure(figsize=(12, 5))
plt.plot(t, E)

plt.axhline(E_init, linestyle=':', label='Init')
plt.axhline(E_final, linestyle='--', label='Final')

plt.xlabel("Time (s)")
plt.ylabel("Voltage (V)")
plt.title("DPV Waveform (Global)")
plt.legend()
plt.grid(True)


# =====================================================
# ===== 局部放大（只加这一块）=====
# =====================================================
enable_zoom = True

# 参数（按需改）
start = 0.0   # float=ratio，int=索引
end = 1.0    # float=ratio，int=索引
step = 0     # >0优先（长度），=0用end

if enable_zoom:
    N = len(t)

    # start
    if isinstance(start, float):
        s = int(N * start)
    else:
        s = int(start)

    # end / step
    if step > 0:
        e = s + step
    else:
        if isinstance(end, float):
            e = int(N * end)
        else:
            e = int(end)

    # 边界保护
    s = max(0, s)
    e = min(N, e)

    plt.figure(figsize=(12, 5))
    plt.plot(t[s:e], E[s:e])

    plt.axhline(E_init, linestyle=':', label='Init')
    plt.axhline(E_final, linestyle='--', label='Final')

    plt.xlabel("Time (s)")
    plt.ylabel("Voltage (V)")
    plt.title(f"DPV Waveform (Zoom [{s}:{e}])")
    plt.legend()
    plt.grid(True)

plt.show()