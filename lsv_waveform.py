import numpy as np


def generate_lsv_waveform(
    E_init,
    E_final,
    scan_rate,   # V/s
    quiet_time
):
    """
    生成LSV波形

    返回：
        t : 时间数组
        E : 电压数组
    """

    # ---------- 参数检查 ----------
    if scan_rate <= 0:
        raise ValueError("scan_rate 必须 > 0")

    if E_final <= E_init:
        raise ValueError("当前实现仅支持 E_final > E_init")

    # ---------- 采样参数 ----------
    fs = 100  # Hz
    dt = 1 / fs

    # ---------- Quiet Time ----------
    N_quiet = int(round(quiet_time * fs))
    E_quiet = np.full(N_quiet, E_init)

    # ---------- 扫描步进 ----------
    dE = scan_rate * dt   # = rate / 100

    # ---------- 生成扫描段 ----------
    ramp = []
    E = E_init

    while E < E_final:
        ramp.append(E)
        E += dE

    ramp = np.array(ramp)

    # ---------- 合并 ----------
    E_total = np.concatenate([E_quiet, ramp])

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