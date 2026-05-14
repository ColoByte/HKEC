import numpy as np


def generate_swv_waveform(
    E_init,
    E_final,
    E_incr,
    amplitude,     # 半幅 A
    frequency,     # Hz
    quiet_time,
    polarity=1     # 1: 先负(-A→+A), 0: 先正
):
    """
    生成SWV波形

    返回：
        t : 时间数组
        E : 电压数组
    """

    # ---------- 参数检查 ----------
    if E_incr <= 0:
        raise ValueError("E_incr 必须 > 0")

    if frequency <= 0:
        raise ValueError("frequency 必须 > 0")

    # ---------- 时间与采样 ----------
    N_period = 100
    fs = 100 * frequency
    dt = 1 / fs

    # ---------- Quiet Time ----------
    N_quiet = int(round(quiet_time * fs))
    E_quiet = np.full(N_quiet, E_init)

    # ---------- 阶梯生成 ----------
    steps = []
    E_step = E_init

    while True:
        steps.append(E_step)
        E_step += E_incr
        if E_step >= E_final:
            steps.append(E_step)  # 允许微偏，最后一个 ≥ Final
            break

    steps = np.array(steps)

    # ---------- 单周期构造 ----------
    N_half = 50

    waveform = []

    for E_step in steps:
        if polarity == 1:
            # 先负
            cycle = np.concatenate([
                np.full(N_half, E_step - amplitude),
                np.full(N_half, E_step + amplitude)
            ])
        else:
            # 先正
            cycle = np.concatenate([
                np.full(N_half, E_step + amplitude),
                np.full(N_half, E_step - amplitude)
            ])

        waveform.append(cycle)

    E_main = np.concatenate(waveform)

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