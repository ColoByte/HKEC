import numpy as np


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


def save_waveform(filename, t, E):
    data = np.column_stack((t, E))
    np.savetxt(
        filename,
        data,
        delimiter=",",
        header="time,voltage",
        comments="",
        fmt="%.6f"
    )