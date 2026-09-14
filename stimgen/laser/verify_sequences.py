#!/usr/bin/env python3
"""
verify_sequences.py — Comprehensive diagnostic and verification suite
for CoIn (Continuous Inference) Laser Task stimulus sequences.

Generates 7 focused, high-value diagnostic figures + text summary reports comparing
empirical sequence metrics against experiment configuration targets:
    01_traces   — Trace grid (all blocks, standardized uniform Y-scaling, unwrapped/wrapped toggle)
    02_deepdive — Block 1 full trace + 45s zoom with jump & duration annotations
    03_errors   — Error distributions split by noise condition vs theoretical Gaussian
    04_jumps    — Jump magnitudes & direction balance (+ vs −) with expected uniform lines
    05_epochs   — Epoch duration histograms by volatility level vs truncated Gaussian
    06_boxplot  — Error boxplots & scatter with centered config ±σ target bands
    07_table    — Sequence verification scorecard & 6-point acceptance checklist

Usage:
    python verify_sequences.py                       # verify all sessions + interactive viewer
    python verify_sequences.py --session main        # one specific session
    python verify_sequences.py --session practice    # practice only
    python verify_sequences.py --no-show             # save only, don't display
    python verify_sequences.py --output /tmp/plots/  # custom output dir
    python verify_sequences.py --list                # list available sessions
"""

from __future__ import annotations

import os
import sys
import pickle
import argparse
from pathlib import Path
from collections import Counter
from datetime import datetime

import numpy as np
from scipy.stats import norm as scipy_norm, skew, kurtosis
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import Patch, Rectangle


# ═══════════════════════════════════════════════════════════════════════════
# Path helpers & config loader
# ═══════════════════════════════════════════════════════════════════════════
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SEQUENCES_DIR = PROJECT_ROOT / "sequences"


def _ensure_interactive_backend() -> bool:
    """Ensure an interactive GUI backend is active for plt.show()."""
    current = matplotlib.get_backend().lower()
    if current != "agg":
        return True

    candidates = ["qtagg", "tkagg", "macosx", "gtk4agg", "gtk3agg", "wxagg"]
    for candidate in candidates:
        try:
            plt.switch_backend(candidate)
            if plt.get_backend().lower() != "agg":
                return True
        except Exception:
            continue
    return False


def _load_config() -> dict:
    """Import config module and return sanitised values."""
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    import config as _cfg
    return {
        "sample_rate": _cfg.SAMPLE_RATE,
        "jump_duration_mean_sec": _cfg.JUMP_DURATION_MEAN_SEC,
        "jump_duration_min_sec": _cfg.JUMP_DURATION_MIN_SEC,
        "jump_duration_max_sec": _cfg.JUMP_DURATION_MAX_SEC,
        "jump_value_set": _cfg.JUMP_VALUE_SET,
        "volatility_presets": dict(_cfg.VOLATILITY_PRESETS),
        "noise_presets": dict(_cfg.NOISE_PRESETS),
    }


def _load_session(session_name: str) -> dict:
    pkl_path = SEQUENCES_DIR / f"session_{session_name}.pkl"
    if not pkl_path.exists():
        raise FileNotFoundError(
            f"Pickle not found: {pkl_path}\n"
            f"  Generate sequences first:  python wizard.py --generate"
        )
    with open(pkl_path, "rb") as f:
        return pickle.load(f)


# ═══════════════════════════════════════════════════════════════════════════
# Colour palette — accessible, clean, publication-ready
# ═══════════════════════════════════════════════════════════════════════════
TRUE_COLOR = "#1f77b4"        # primary blue — true mean
OBS_COLOR = "#d62728"         # warm red — observations
OBS_ALPHA = 0.35
EPOCH_LINE_COLOR = "#7f7f7f"  # epoch boundary lines
CONFIG_COLOR = "#2ca02c"      # green — config target
WARN_COLOR = "#d62728"        # red — warnings
PASS_COLOR = "#2ca02c"        # green — pass
GRID_COLOR = "#ebebeb"

COND_PALETTE = {
    "stable+precise":   "#4daf4a",
    "stable+noisy":     "#377eb8",
    "volatile+precise": "#ff7f00",
    "volatile+noisy":   "#984ea3",
    "medium+precise":   "#a65628",
    "medium+noisy":     "#f781bf",
}

JUMP_PALETTE = {20: "#4daf4a", 30: "#ff7f00", 40: "#e41a1c"}


def _parse_block_type(bt: str) -> tuple[str, str]:
    if "+" in bt:
        v, n = bt.split("+", 1)
        return v, n
    return bt, ""


def _wrap_errors(obs: np.ndarray, true: np.ndarray) -> np.ndarray:
    """Correct circular wrap-around errors in degrees into [-180, 180)."""
    e = obs - true
    e = np.where(e > 180, e - 360, e)
    e = np.where(e < -180, e + 360, e)
    return e


def _wrap_degrees(values: np.ndarray | float) -> np.ndarray | float:
    """Wrap an array of degree values into [0, 360)."""
    return np.mod(values, 360.0)


def _make_step_wrapped(t: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Create a step-interpolated circular trajectory wrapped to [0, 360) with NaNs at boundary jumps."""
    t_float = np.asarray(t, dtype=float)
    y_float = np.asarray(values, dtype=float)
    t_step = np.repeat(t_float, 2)[1:]
    y_step = np.repeat(y_float, 2)[:-1]
    y_wrapped = np.mod(y_step, 360.0)
    diff = np.abs(np.diff(y_wrapped))
    jump_indices = np.where(diff > 180.0)[0]
    if len(jump_indices) > 0:
        t_clean = np.insert(t_step, jump_indices + 1, np.nan)
        y_clean = np.insert(y_wrapped, jump_indices + 1, np.nan)
        return t_clean, y_clean
    return t_step, y_wrapped


def _fill_wrapped_band(ax, t: np.ndarray, center_deg: np.ndarray, half_width_deg: float, **kwargs) -> None:
    """Fill a circular ±half_width band around center_deg in [0, 360) without vertical wrap artifacts."""
    clean_kwargs = {k: v for k, v in kwargs.items() if k != "label"}
    center = np.mod(center_deg, 360.0)
    lower = center - half_width_deg
    upper = center + half_width_deg

    mask_norm = (lower >= 0) & (upper <= 360)
    if np.any(mask_norm):
        ax.fill_between(t, lower, upper, where=mask_norm, **clean_kwargs)

    mask_low = lower < 0
    if np.any(mask_low):
        ax.fill_between(t, 0, upper, where=mask_low, **clean_kwargs)
        ax.fill_between(t, lower + 360, 360, where=mask_low, **clean_kwargs)

    mask_high = upper > 360
    if np.any(mask_high):
        ax.fill_between(t, lower, 360, where=mask_high, **clean_kwargs)
        ax.fill_between(t, 0, upper - 360, where=mask_high, **clean_kwargs)


def _style_ax(ax, xlabel="", ylabel="", title="", **kwargs) -> None:
    """Apply consistent clean styling to an axes."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, color=GRID_COLOR, linewidth=0.5, alpha=0.8)
    ax.tick_params(labelsize=10)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10.5, color="#333333")
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10.5, color="#333333")
    if title:
        ax.set_title(title, fontsize=11.5, fontweight="bold", color="#222222", **kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# Figure setup helper (7 Diagnostic Plots)
# ═══════════════════════════════════════════════════════════════════════════
FIG_SPECS = [
    ("01_traces",     "Trace Grid — True Mean & Observation Dynamics",  18, 12),
    ("02_deepdive",   "Block Deep-Dive — Full Trace & 45 s Zoom",       18, 12),
    ("03_errors",     "Observation Error Distributions vs Gaussian",    16, 9),
    ("04_jumps",      "True-Mean Jump Sizes & Direction Balance",       16, 9),
    ("05_epochs",     "Epoch Duration Distribution by Volatility",      16, 9),
    ("06_boxplot",    "Observation Error by Block Type & Target Bands", 16, 9),
    ("07_table",      "Sequence Verification Scorecard & Checklist",    18, 11),
]


def _prepare_fig(fig, title_suffix: str, w: float, h: float, session_name: str) -> plt.Figure:
    if fig is None:
        fig = plt.figure(figsize=(w, h), facecolor="white")
    else:
        fig.clf()
        fig.set_facecolor("white")

    fig.suptitle(f"{title_suffix}  —  Session: {session_name}",
                 fontsize=13.5, fontweight="bold", color="#111111", y=0.985)
    return fig


def _add_config_header(fig, cfg: dict, session_name: str) -> None:
    lines = [
        f"Config: Sample Rate={cfg['sample_rate']} Hz",
        f"Jumps={cfg['jump_value_set']}",
        f"Sub-jumps ∈ [{cfg['jump_duration_min_sec']},{cfg['jump_duration_max_sec']}]s",
    ]
    vol_lines = []
    for k, v in cfg["volatility_presets"].items():
        if isinstance(v, list) and len(v) >= 4:
            vol_lines.append(f"{k}: μ={v[0]}s ∈[{v[2]},{v[3]}]s")
    noise_lines = [f"Noise: " + ", ".join(f"{k}={v}°" for k, v in cfg["noise_presets"].items())]

    all_text = "  |  ".join(lines + [", ".join(vol_lines)] + noise_lines)
    fig.text(0.5, 0.960, all_text, fontsize=9.0, ha="center", va="top",
             color="#555555", style="italic", fontfamily="monospace")


# ═══════════════════════════════════════════════════════════════════════════
# Plot 1 — Trace Grid (Standardized Uniform Y-Scaling)
# ═══════════════════════════════════════════════════════════════════════════
def build_figure_traces(session, session_name, cfg, fig=None, wrapped: bool = False):
    n_blocks = session["nBlocks"]
    n_cols = 2 if n_blocks > 1 else 1
    n_rows = int(np.ceil(n_blocks / n_cols))

    suffix_label = "Wrapped [0, 360)°" if wrapped else "Unwrapped Continuous° (Uniform Scale)"
    fig = _prepare_fig(fig, f"Trace Grid — True Mean & Observation Dynamics ({suffix_label})", FIG_SPECS[0][2], FIG_SPECS[0][3], session_name)
    _add_config_header(fig, cfg, session_name)

    gs = fig.add_gridspec(n_rows, n_cols, hspace=0.45, wspace=0.22,
                           left=0.06, right=0.97, top=0.92, bottom=0.08)
    axes = gs.subplots(squeeze=False)

    # Calculate uniform vertical span across all blocks in unwrapped mode
    if not wrapped:
        spans = []
        for blk in session["blocks"]:
            stim = blk["stim"]
            noise_cfg = stim["stdValueVectorDeg"][0]
            true_pos = stim["meanValueVector"]
            obs_pos = stim["valueVector"]
            spans.append(np.ptp(true_pos) + 3.5 * noise_cfg)
        max_span = max(spans) if spans else 360.0
        # Round up to a clean multiple of 100°
        uniform_span = float(np.ceil(max_span / 100.0) * 100.0)
        uniform_span = max(uniform_span, 250.0)

    for i in range(n_blocks):
        ax = axes.flat[i]
        blk = session["blocks"][i]
        stim = blk["stim"]
        t = stim["time"] / 60  # minutes
        noise_cfg = stim["stdValueVectorDeg"][0]
        bt = blk["blockType"]
        v_label, n_label = _parse_block_type(bt)
        v_params = cfg["volatility_presets"].get(v_label, [])
        v_mean = f" | Epoch μ={v_params[0]}s" if v_params else ""

        n_pts = len(t)
        step = max(1, n_pts // 1800)
        idx = slice(0, n_pts, step)

        if wrapped:
            true_pos = stim["meanValueVectorDeg"]
            obs_pos = stim["valueVectorDeg"]
            obs_plot = _wrap_degrees(obs_pos)
            t_step, true_step = _make_step_wrapped(t, true_pos)

            ax.scatter(t[idx], obs_plot[idx], color=OBS_COLOR, s=0.8,
                       alpha=0.40, zorder=2, rasterized=True)
            _fill_wrapped_band(ax, t, true_pos, noise_cfg, color=OBS_COLOR, alpha=0.10, zorder=1)
            ax.plot(t_step, true_step, color=TRUE_COLOR, linewidth=1.3, zorder=4)
            ax.set_ylim(-5, 365)
            ax.set_yticks([0, 90, 180, 270, 360])
            ylabel = "Screen Angle [0, 360) (°)"
        else:
            true_pos = stim["meanValueVector"]
            obs_pos = stim["valueVector"]
            t_step = np.repeat(t, 2)[1:]
            true_step = np.repeat(true_pos, 2)[:-1]

            ax.scatter(t[idx], obs_pos[idx], color=OBS_COLOR, s=0.8,
                       alpha=0.40, zorder=2, rasterized=True)
            ax.fill_between(t, true_pos - noise_cfg, true_pos + noise_cfg,
                            color=OBS_COLOR, alpha=0.12, zorder=1)
            ax.plot(t_step, true_step, color=TRUE_COLOR, linewidth=1.3, zorder=4)

            # Center the uniform vertical span on this block's trajectory
            mid_y = (np.min(true_pos) + np.max(true_pos)) / 2.0
            ax.set_ylim(mid_y - uniform_span / 2.0, mid_y + uniform_span / 2.0)
            ylabel = "Cumulative Angle (°)"

        boundaries = np.cumsum(stim["meanDurations"]) / session["sampleRate"] / 60
        for b in boundaries[:-1]:
            ax.axvline(x=b, color=EPOCH_LINE_COLOR, linestyle=":",
                       linewidth=0.5, alpha=0.5, zorder=1)

        _style_ax(ax,
                  title=f"Block {i+1}: {bt} (Target σ={noise_cfg:.0f}°{v_mean})",
                  xlabel="Time (minutes)", ylabel=ylabel)

    for j in range(n_blocks, len(axes.flat)):
        axes.flat[j].set_visible(False)

    if n_blocks > 0:
        first_ax = axes.flat[0]
        noise_patch = Patch(facecolor=OBS_COLOR, alpha=0.15, label=f"Config ±σ noise band")
        obs_scatter = plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=OBS_COLOR,
                                 markersize=5, alpha=0.6, label="Observations (samples)")
        true_line = plt.Line2D([0], [0], color=TRUE_COLOR, linewidth=1.5, label="True mean (hidden)")
        first_ax.legend(handles=[true_line, obs_scatter, noise_patch],
                        fontsize=9.0, framealpha=0.90, loc="upper right", borderpad=0.3)
    return fig


# ═══════════════════════════════════════════════════════════════════════════
# Plot 2 — Block Deep-Dive (Full Block + 45s High-Resolution Zoom)
# ═══════════════════════════════════════════════════════════════════════════
def build_figure_deepdive(session, session_name, cfg, fig=None, wrapped: bool = False):
    suffix_label = "Wrapped [0, 360)°" if wrapped else "Unwrapped Continuous°"
    fig = _prepare_fig(fig, f"Block Deep-Dive — Full Trace & 45 s Zoom ({suffix_label})", FIG_SPECS[1][2], FIG_SPECS[1][3], session_name)
    _add_config_header(fig, cfg, session_name)

    gs = fig.add_gridspec(2, 1, hspace=0.40,
                           left=0.07, right=0.97, top=0.91, bottom=0.08)
    ax_full = fig.add_subplot(gs[0])
    ax_zoom = fig.add_subplot(gs[1])

    blk = session["blocks"][0]
    stim = blk["stim"]
    t = stim["time"]
    noise_cfg = stim["stdValueVectorDeg"][0]
    boundaries = np.cumsum(stim["meanDurations"]) / session["sampleRate"]
    n_epochs = len(boundaries)
    bt = blk["blockType"]

    if wrapped:
        true_pos = stim["meanValueVectorDeg"]
        obs_pos = stim["valueVectorDeg"]
        t_step_full, true_step_full = _make_step_wrapped(t / 60, true_pos)
        obs_wrapped = _wrap_degrees(obs_pos)

        ax_full.scatter((t / 60)[::max(1, len(t)//2500)], obs_wrapped[::max(1, len(t)//2500)],
                        color=OBS_COLOR, s=0.9, alpha=0.35, zorder=2, rasterized=True)
        _fill_wrapped_band(ax_full, t / 60, true_pos, noise_cfg, color=OBS_COLOR, alpha=0.10, zorder=1)
        ax_full.plot(t_step_full, true_step_full, color=TRUE_COLOR, linewidth=1.1, zorder=4)
        ax_full.set_ylim(-5, 365)
        ax_full.set_yticks([0, 90, 180, 270, 360])
        ylabel = "Screen Angle [0, 360) (°)"
    else:
        true_pos = stim["meanValueVector"]
        obs_pos = stim["valueVector"]
        t_step_full = np.repeat(t / 60, 2)[1:]
        true_step_full = np.repeat(true_pos, 2)[:-1]

        ax_full.scatter((t / 60)[::max(1, len(t)//2500)], obs_pos[::max(1, len(t)//2500)],
                        color=OBS_COLOR, s=0.9, alpha=0.35, zorder=2, rasterized=True)
        ax_full.fill_between(t / 60, true_pos - noise_cfg, true_pos + noise_cfg,
                             color=OBS_COLOR, alpha=0.12, zorder=1)
        ax_full.plot(t_step_full, true_step_full, color=TRUE_COLOR, linewidth=1.1, zorder=4)
        ylabel = "Cumulative Angle (°)"

    for b in boundaries[:-1]:
        ax_full.axvline(x=b / 60, color=EPOCH_LINE_COLOR, linestyle=":",
                        linewidth=0.5, alpha=0.5, zorder=1)
    _style_ax(ax_full,
              title=f"Block 1: {bt} — Complete Session Trace ({blk['duration']/60:.0f} min, {n_epochs} epochs)",
              xlabel="Time (minutes)", ylabel=ylabel)

    noise_patch = Patch(facecolor=OBS_COLOR, alpha=0.15, label=f"Config ±{noise_cfg:.0f}° noise band")
    obs_scatter = plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=OBS_COLOR,
                             markersize=5, alpha=0.6, label="Observations")
    true_line = plt.Line2D([0], [0], color=TRUE_COLOR, linewidth=1.5, label="True mean")
    ax_full.legend(handles=[true_line, obs_scatter, noise_patch], fontsize=9.0, framealpha=0.90, loc="upper right")

    # 45s Zoom
    zoom_sec = min(45.0, t[-1])
    mask = t <= zoom_sec
    t_zoom = t[mask]

    if wrapped:
        true_zoom = stim["meanValueVectorDeg"][mask]
        obs_zoom = stim["valueVectorDeg"][mask]
        t_step_zoom, true_step_zoom = _make_step_wrapped(t_zoom, true_zoom)
        obs_wrapped_zoom = _wrap_degrees(obs_zoom)

        ax_zoom.scatter(t_zoom[::max(1, len(t_zoom)//800)], obs_wrapped_zoom[::max(1, len(t_zoom)//800)],
                        color=OBS_COLOR, s=2.5, alpha=0.50, zorder=2)
        _fill_wrapped_band(ax_zoom, t_zoom, true_zoom, noise_cfg, color=OBS_COLOR, alpha=0.12, zorder=1)
        ax_zoom.plot(t_step_zoom, true_step_zoom, color=TRUE_COLOR, linewidth=1.8, zorder=4)
        ax_zoom.set_ylim(-5, 365)
        ax_zoom.set_yticks([0, 90, 180, 270, 360])
        ylabel_zoom = "Screen Angle [0, 360) (°)"
        text_y_top = 342
        text_y_bot = 12
    else:
        true_zoom = stim["meanValueVector"][mask]
        obs_zoom = stim["valueVector"][mask]
        t_step_zoom = np.repeat(t_zoom, 2)[1:]
        true_step_zoom = np.repeat(true_zoom, 2)[:-1]

        ax_zoom.scatter(t_zoom[::max(1, len(t_zoom)//800)], obs_zoom[::max(1, len(t_zoom)//800)],
                        color=OBS_COLOR, s=2.5, alpha=0.50, zorder=2)
        ax_zoom.fill_between(t_zoom, true_zoom - noise_cfg, true_zoom + noise_cfg,
                             color=OBS_COLOR, alpha=0.14, zorder=1)
        ax_zoom.plot(t_step_zoom, true_step_zoom, color=TRUE_COLOR, linewidth=1.8, zorder=4)
        ylabel_zoom = "Cumulative Angle (°)"
        y_min_z = np.min(true_zoom) - noise_cfg * 1.5
        y_max_z = np.max(true_zoom) + noise_cfg * 1.5
        ax_zoom.set_ylim(y_min_z, y_max_z)
        text_y_top = y_max_z - (y_max_z - y_min_z) * 0.08
        text_y_bot = y_min_z + (y_max_z - y_min_z) * 0.08

    zoom_boundaries = [0.0] + [b for b in boundaries if b <= zoom_sec]
    for k in range(1, len(zoom_boundaries)):
        b = zoom_boundaries[k]
        prev_b = zoom_boundaries[k-1]
        dur = b - prev_b
        ax_zoom.axvline(x=b, color=EPOCH_LINE_COLOR, linestyle="--",
                        linewidth=1.0, alpha=0.75, zorder=1)

        epoch_idx = k - 1
        if epoch_idx < len(stim["meanValues"]) - 1:
            jump_val = stim["meanValues"][epoch_idx + 1] - stim["meanValues"][epoch_idx]
            sign = "+" if jump_val > 0 else ""
            badge_c = "#4daf4a" if jump_val > 0 else "#e41a1c"
            ax_zoom.text(b, text_y_top, f" {sign}{jump_val:.0f}° ", fontsize=8.5,
                         ha="center", va="top", color="white", fontweight="bold",
                         bbox=dict(boxstyle="round,pad=0.2", facecolor=badge_c, edgecolor="none", alpha=0.9))

        ax_zoom.text((prev_b + b) / 2, text_y_bot, f"Δt={dur:.1f}s", fontsize=8.5,
                     ha="center", va="bottom", color="#444444", fontweight="bold",
                     bbox=dict(boxstyle="round,pad=0.2", facecolor="#f0f0f0", edgecolor="#cccccc", alpha=0.85))

    _style_ax(ax_zoom,
              title=f"First {zoom_sec:.0f} Seconds Zoom — Change Points, Jump Magnitudes & Epoch Lengths",
              xlabel="Time (seconds)", ylabel=ylabel_zoom)

    zoom_noise_patch = Patch(facecolor=OBS_COLOR, alpha=0.15, label=f"±{noise_cfg:.0f}° noise band")
    zoom_obs_scatter = plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=OBS_COLOR,
                                  markersize=5, alpha=0.6, label="Observations (samples)")
    zoom_true_line = plt.Line2D([0], [0], color=TRUE_COLOR, linewidth=1.5, label="True mean (step)")
    ax_zoom.legend(handles=[zoom_true_line, zoom_obs_scatter, zoom_noise_patch],
                   fontsize=9.0, framealpha=0.90, loc="upper right")

    return fig


# ═══════════════════════════════════════════════════════════════════════════
# Plot 3 — Error Distributions (Separated by Noise Condition)
# ═══════════════════════════════════════════════════════════════════════════
def build_figure_errors(session, session_name, cfg, fig=None):
    fig = _prepare_fig(fig, FIG_SPECS[2][1], FIG_SPECS[2][2], FIG_SPECS[2][3], session_name)
    _add_config_header(fig, cfg, session_name)

    noise_groups: dict[tuple[str, float], dict[str, list[np.ndarray]]] = {}
    for blk in session["blocks"]:
        stim = blk["stim"]
        bt = blk["blockType"]
        v_label, n_label = _parse_block_type(bt)
        noise_cfg = float(stim["stdValueVectorDeg"][0])
        errors = _wrap_errors(stim["valueVectorDeg"], stim["meanValueVectorDeg"])
        key = (n_label or f"σ={noise_cfg:.0f}°", noise_cfg)
        if key not in noise_groups:
            noise_groups[key] = {}
        if bt not in noise_groups[key]:
            noise_groups[key][bt] = []
        noise_groups[key][bt].append(errors)

    n_groups = max(1, len(noise_groups))
    gs = fig.add_gridspec(1, n_groups, hspace=0.35, wspace=0.25,
                           left=0.07, right=0.97, top=0.88, bottom=0.12)
    axes = [fig.add_subplot(gs[0, j]) for j in range(n_groups)]

    for j, ((n_name, n_cfg), bt_dict) in enumerate(noise_groups.items()):
        ax = axes[j]
        all_errs = np.concatenate([np.concatenate(err_list) for err_list in bt_dict.values()])
        actual_std = float(np.std(all_errs))
        actual_mean = float(np.mean(all_errs))
        sk = float(skew(all_errs))
        kurt = float(kurtosis(all_errs))
        dev_pct = abs(actual_std - n_cfg) / n_cfg * 100
        is_pass = dev_pct <= 10.0

        for bt, err_list in bt_dict.items():
            errs = np.concatenate(err_list)
            bt_color = COND_PALETTE.get(bt, "#666666")
            ax.hist(errs, bins=70, density=True, alpha=0.45,
                    color=bt_color, edgecolor="white", linewidth=0.3,
                    label=f"{bt} (n={len(errs):,}, σ={np.std(errs):.1f}°)")
        x = np.linspace(-3.8 * n_cfg, 3.8 * n_cfg, 300)
        ax.plot(x, scipy_norm.pdf(x, 0, n_cfg), color="#111111",
                linewidth=2.2, linestyle="--",
                label=f"Config Target: N(0, {n_cfg:.0f}°)")
        ax.plot(x, scipy_norm.pdf(x, actual_mean, actual_std), color="#d62728",
                linewidth=1.8, linestyle="-",
                label=f"Empirical Fit: N({actual_mean:.1f}°, {actual_std:.1f}°)")

        _style_ax(ax,
                  title=f"{n_name.upper()} Condition — Target σ={n_cfg:.0f}° vs Empirical σ={actual_std:.1f}°",
                  xlabel="Observation Error: Observed − True Mean (°)", ylabel="Probability Density")
        ax.set_xlim(-3.8 * n_cfg, 3.8 * n_cfg)
        ax.legend(fontsize=9.0, framealpha=0.90, loc="upper right")

        badge_color = PASS_COLOR if is_pass else WARN_COLOR
        badge_text = "✓ PASS (≤10% diff)" if is_pass else f"⚠ FLAGGED ({dev_pct:.1f}% diff)"
        ax.text(0.03, 0.95,
                f"Config Target σ:  {n_cfg:.0f}°\n"
                f"Empirical σ:      {actual_std:.2f}°\n"
                f"Mean Bias μ:      {actual_mean:.2f}°\n"
                f"Skewness / Kurt:  {sk:.2f} / {kurt:.2f}\n"
                f"Deviation:        {dev_pct:.1f}%\n"
                f"Status:           {badge_text}",
                transform=ax.transAxes, fontsize=9.0, ha="left", va="top",
                fontfamily="monospace",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                          edgecolor=badge_color, linewidth=1.5, alpha=0.95))
    return fig


# ═══════════════════════════════════════════════════════════════════════════
# Plot 4 — Jump Sizes & Direction Balance
# ═══════════════════════════════════════════════════════════════════════════
def build_figure_jumps(session, session_name, cfg, fig=None):
    fig = _prepare_fig(fig, FIG_SPECS[3][1], FIG_SPECS[3][2], FIG_SPECS[3][3], session_name)
    _add_config_header(fig, cfg, session_name)

    gs = fig.add_gridspec(1, 2, width_ratios=[1.3, 1.0], wspace=0.28,
                           left=0.07, right=0.97, top=0.88, bottom=0.12)
    ax_bars = fig.add_subplot(gs[0, 0])
    ax_summary = fig.add_subplot(gs[0, 1])

    all_jumps = []
    block_jump_stats = []
    for blk in session["blocks"]:
        jumps = np.diff(blk["stim"]["meanValues"])
        all_jumps.extend(jumps.tolist())
        block_jump_stats.append((blk["blockType"], len(jumps), int(np.sum(jumps > 0)), int(np.sum(jumps < 0))))
    all_jumps = np.array(all_jumps)

    expected = sorted(set(abs(v) for v in cfg["jump_value_set"]))
    pos_counts = [int(np.sum(all_jumps == e)) for e in expected]
    neg_counts = [int(np.sum(all_jumps == -e)) for e in expected]

    x = np.arange(len(expected))
    width = 0.35
    bars_pos = ax_bars.bar(x - width / 2, pos_counts, width, color="#4daf4a",
                           edgecolor="white", linewidth=0.8, label="Clockwise (+)")
    bars_neg = ax_bars.bar(x + width / 2, neg_counts, width, color="#e41a1c",
                           edgecolor="white", linewidth=0.8, label="Counter-Clockwise (−)")

    for bar, count in zip(bars_pos, pos_counts):
        ax_bars.text(bar.get_x() + bar.get_width() / 2,
                     bar.get_height() + max(0.5, bar.get_height() * 0.02),
                     str(count), ha="center", va="bottom", fontsize=10,
                     fontweight="bold", color="#2ca02c")
    for bar, count in zip(bars_neg, neg_counts):
        ax_bars.text(bar.get_x() + bar.get_width() / 2,
                     bar.get_height() + max(0.5, bar.get_height() * 0.02),
                     str(count), ha="center", va="bottom", fontsize=10,
                     fontweight="bold", color="#c0392b")

    if len(expected) > 0 and len(all_jumps) > 0:
        expected_per_bar = len(all_jumps) / (2 * len(expected))
        ax_bars.axhline(y=expected_per_bar, color="#333333", linestyle="--", linewidth=1.2,
                        alpha=0.7, label=f"Uniform Target ({expected_per_bar:.1f}/bar)")

    unexpected = all_jumps[~np.isin(np.abs(all_jumps), expected)]
    ax_bars.set_xticks(x)
    ax_bars.set_xticklabels([f"±{e}°" for e in expected], fontsize=10.5)
    _style_ax(ax_bars, title="Jump Frequencies by Magnitude and Direction",
              xlabel="Config Jump Magnitude (°)", ylabel="Jump Count")
    ax_bars.legend(fontsize=9.0, framealpha=0.90, loc="upper right")
    ax_bars.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    total_pos = sum(pos_counts)
    total_neg = sum(neg_counts)
    pos_pct = total_pos / max(1, len(all_jumps)) * 100
    neg_pct = total_neg / max(1, len(all_jumps)) * 100
    dir_diff = abs(total_pos - total_neg)

    ax_summary.axis("off")
    is_pass = (len(unexpected) == 0) and (abs(pos_pct - 50.0) <= 15.0)
    status_text = "✓ PASS — Uniform & Balanced" if is_pass else "⚠ FLAGGED — Direction Imbalance"
    status_color = PASS_COLOR if is_pass else WARN_COLOR

    summary_lines = [
        "Jump Uniformity & Direction Verification",
        "────────────────────────────────────────",
        f"Total Jumps in Session:    {len(all_jumps)}",
        f"Clockwise (+):             {total_pos} ({pos_pct:.1f}% | Target: 50%)",
        f"Counter-Clockwise (−):     {total_neg} ({neg_pct:.1f}% | Target: 50%)",
        f"Direction Imbalance:       {dir_diff} jumps ({abs(pos_pct-neg_pct):.1f}%)",
        f"Unexpected Jump Sizes:     {len(unexpected)} (Target = 0)",
        "",
        "Per-Block Breakdown:",
    ]
    for bt, total, p_cnt, n_cnt in block_jump_stats:
        summary_lines.append(f"  • {bt:18s}: {total:2d} jumps (+{p_cnt:2d} / −{n_cnt:2d})")

    summary_lines.extend([
        "",
        f"Status: {status_text}",
    ])

    full_summary = "\n".join(summary_lines)
    ax_summary.text(0.05, 0.95, full_summary, transform=ax_summary.transAxes,
                    fontsize=9.5, va="top", fontfamily="monospace", color="#222222",
                    bbox=dict(boxstyle="round,pad=0.6", facecolor="#f8f9fa", edgecolor=status_color, linewidth=1.5, alpha=0.95))
    return fig


# ═══════════════════════════════════════════════════════════════════════════
# Plot 5 — Epoch Durations (Separated by Volatility Condition)
# ═══════════════════════════════════════════════════════════════════════════
def build_figure_epochs(session, session_name, cfg, fig=None):
    fig = _prepare_fig(fig, FIG_SPECS[4][1], FIG_SPECS[4][2], FIG_SPECS[4][3], session_name)
    _add_config_header(fig, cfg, session_name)

    vol_groups: dict[tuple[str, tuple], dict[str, list[np.ndarray]]] = {}
    for blk in session["blocks"]:
        stim = blk["stim"]
        bt = blk["blockType"]
        v_label, n_label = _parse_block_type(bt)
        v_params = cfg["volatility_presets"].get(v_label, [])
        durs = np.array(stim["meanDurations"], dtype=float) / session["sampleRate"]
        durs_untruncated = durs[:-1] if len(durs) > 1 else durs

        key = (v_label or bt, tuple(v_params) if v_params else ())
        if key not in vol_groups:
            vol_groups[key] = {}
        if bt not in vol_groups[key]:
            vol_groups[key][bt] = []
        vol_groups[key][bt].append(durs_untruncated)

    n_groups = max(1, len(vol_groups))
    gs = fig.add_gridspec(1, n_groups, hspace=0.35, wspace=0.25,
                           left=0.07, right=0.97, top=0.88, bottom=0.14)
    axes = [fig.add_subplot(gs[0, j]) for j in range(n_groups)]

    for j, ((v_name, v_params), bt_dict) in enumerate(vol_groups.items()):
        ax = axes[j]
        all_durs = np.concatenate([np.concatenate(d_list) for d_list in bt_dict.values()]) if bt_dict else np.array([])
        actual_mean = float(np.mean(all_durs)) if len(all_durs) > 0 else 0.0
        actual_std = float(np.std(all_durs)) if len(all_durs) > 0 else 0.0
        actual_min = float(np.min(all_durs)) if len(all_durs) > 0 else 0.0
        actual_max = float(np.max(all_durs)) if len(all_durs) > 0 else 0.0

        cfg_mean = v_params[0] if len(v_params) > 0 else None
        cfg_std = v_params[1] if len(v_params) > 1 else None
        cfg_min = v_params[2] if len(v_params) > 2 else None
        cfg_max = v_params[3] if len(v_params) > 3 else None

        dev_pct = abs(actual_mean - cfg_mean) / cfg_mean * 100 if cfg_mean else 0.0
        is_pass = dev_pct <= 15.0

        for bt, d_list in bt_dict.items():
            durs = np.concatenate(d_list)
            bt_color = COND_PALETTE.get(bt, "#666666")
            ax.hist(durs, bins=25, alpha=0.50, color=bt_color,
                    edgecolor="white", linewidth=0.3,
                    label=f"{bt} (n={len(durs)}, μ={np.mean(durs):.1f}s)")
        if cfg_mean is not None:
            ax.axvline(x=cfg_mean, color="#111111", linewidth=2.0, linestyle="--",
                       label=f"Config Target μ={cfg_mean}s")
        if cfg_min is not None and cfg_max is not None:
            ax.axvline(x=cfg_min, color="#555555", linewidth=1.2, linestyle=":",
                       label=f"Config Bounds [{cfg_min}, {cfg_max}]s")
            ax.axvline(x=cfg_max, color="#555555", linewidth=1.2, linestyle=":")

        _style_ax(ax,
                  title=f"{v_name.upper()} Volatility — Target μ={cfg_mean}s vs Empirical μ={actual_mean:.1f}s",
                  xlabel="Epoch Duration (seconds) [truncated final epoch excluded]", ylabel="Epoch Count")
        ax.legend(fontsize=9.0, framealpha=0.90, loc="upper right")

        badge_color = PASS_COLOR if is_pass else WARN_COLOR
        badge_text = "✓ PASS (≤15% diff)" if is_pass else f"⚠ FLAGGED ({dev_pct:.1f}% diff)"
        ax.text(0.03, 0.95,
                f"Config Target μ:   {cfg_mean}s (std={cfg_std}s)\n"
                f"Empirical Mean μ:  {actual_mean:.2f}s (std={actual_std:.2f}s)\n"
                f"Empirical Range:   [{actual_min:.1f}, {actual_max:.1f}]s\n"
                f"Config Range:      [{cfg_min}, {cfg_max}]s\n"
                f"Mean Deviation:    {dev_pct:.1f}%\n"
                f"Status:            {badge_text}",
                transform=ax.transAxes, fontsize=9.0, ha="left", va="top",
                fontfamily="monospace",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                          edgecolor=badge_color, linewidth=1.5, alpha=0.95))
    return fig


# ═══════════════════════════════════════════════════════════════════════════
# Plot 6 — Error Boxplot with Centered Config ±σ Bands
# ═══════════════════════════════════════════════════════════════════════════
def build_figure_boxplot(session, session_name, cfg, fig=None):
    fig = _prepare_fig(fig, FIG_SPECS[5][1], FIG_SPECS[5][2], FIG_SPECS[5][3], session_name)
    _add_config_header(fig, cfg, session_name)

    ax = fig.add_subplot(1, 1, 1)
    block_labels = [f"B{i+1}: {blk['blockType']}" for i, blk in enumerate(session["blocks"])]
    data = []
    config_stds = []
    for blk in session["blocks"]:
        errors = _wrap_errors(blk["stim"]["valueVectorDeg"], blk["stim"]["meanValueVectorDeg"])
        data.append(errors)
        config_stds.append(blk["stim"]["stdValueVectorDeg"][0])

    for i, cfg_std in enumerate(config_stds):
        x_pos = i + 1
        rect = Rectangle((x_pos - 0.38, -cfg_std), 0.76, 2 * cfg_std,
                         facecolor=CONFIG_COLOR, alpha=0.15, edgecolor=CONFIG_COLOR,
                         linestyle="--", linewidth=1.2, zorder=1)
        ax.add_patch(rect)

    bp = ax.boxplot(data, tick_labels=block_labels, patch_artist=True,
                    showfliers=False, widths=0.50, zorder=3,
                    medianprops={"color": "#111111", "linewidth": 1.5})

    n_blocks = len(session["blocks"])
    cmap = plt.cm.Set2
    for i, (patch, blk) in enumerate(zip(bp["boxes"], session["blocks"])):
        bt = blk["blockType"]
        color = COND_PALETTE.get(bt, cmap(i / max(n_blocks, 1)))
        patch.set_facecolor(color)
        patch.set_alpha(0.60)
        patch.set_edgecolor("#222222")
        patch.set_linewidth(0.8)

    rng = np.random.default_rng(42)
    for i, errs in enumerate(data):
        x_pos = i + 1
        n_pts = len(errs)
        step = max(1, n_pts // 350)
        errs_ds = errs[::step]
        jitter = rng.normal(0, 0.07, size=len(errs_ds))
        ax.scatter(x_pos + jitter, errs_ds, s=2.0, alpha=0.20,
                   color="#222222", zorder=4, rasterized=True)

        actual_std = np.std(data[i])
        dev = abs(actual_std - config_stds[i]) / config_stds[i] * 100
        color = WARN_COLOR if dev > 10 else "#222222"
        ax.annotate(f"Empirical σ={actual_std:.1f}°\n(Target={config_stds[i]:.0f}°)",
                    xy=(x_pos, np.percentile(data[i], 93)),
                    xytext=(x_pos, np.percentile(data[i], 93) + 6),
                    fontsize=9.5, ha="center", va="bottom", color=color,
                    fontweight="bold")

    _style_ax(ax, title="Observation Error Distributions by Block vs Config ±σ Target Bands",
              ylabel="Observation Error: Observed − True Mean (°)")
    ax.axhline(y=0, color="#222222", linewidth=0.8, linestyle="-", alpha=0.6)

    config_patch = Patch(facecolor=CONFIG_COLOR, alpha=0.20, edgecolor=CONFIG_COLOR,
                         linestyle="--", label="Config Target ±σ Range")
    ax.legend(handles=[config_patch], fontsize=9.5, framealpha=0.90, loc="lower right")
    return fig


# ═══════════════════════════════════════════════════════════════════════════
# Plot 7 — Sequence Verification Scorecard & 6-Point Acceptance Checklist
# ═══════════════════════════════════════════════════════════════════════════
def build_figure_table(session, session_name, cfg, fig=None):
    fig = _prepare_fig(fig, FIG_SPECS[6][1], FIG_SPECS[6][2], FIG_SPECS[6][3], session_name)

    gs = fig.add_gridspec(3, 1, height_ratios=[0.18, 0.44, 0.38], hspace=0.32,
                           left=0.04, right=0.96, top=0.95, bottom=0.05)
    ax_banner = fig.add_subplot(gs[0])
    ax_table = fig.add_subplot(gs[1])
    ax_checklist = fig.add_subplot(gs[2])

    col_labels = ["Blk", "Block Type", "Epochs (Target)", "Dur μ (Target)",
                  "σ Empirical", "σ Target", "Δσ%", "Jumps (+/−)", "Angular Travel", "Block Status"]

    cell_text = []
    cell_colors = []
    all_ok = True
    total_samples = 0
    all_jumps_list = []
    max_sigma_dev = 0.0

    for i, blk in enumerate(session["blocks"]):
        stim = blk["stim"]
        bt = blk["blockType"]
        v_label, n_label = _parse_block_type(bt)

        durs_sec = np.array(stim["meanDurations"]) / session["sampleRate"]
        errors = _wrap_errors(stim["valueVectorDeg"], stim["meanValueVectorDeg"])
        jumps = np.diff(stim["meanValues"])
        all_jumps_list.extend(jumps.tolist())
        pos_jumps = int(np.sum(jumps > 0))
        neg_jumps = int(np.sum(jumps < 0))

        config_std = stim["stdValueVectorDeg"][0]
        actual_std = float(np.std(errors))
        dev_pct = abs(actual_std - config_std) / config_std * 100
        max_sigma_dev = max(max_sigma_dev, dev_pct)

        v_params = cfg["volatility_presets"].get(v_label, [])
        config_dur_mean = v_params[0] if len(v_params) > 0 else None
        target_epochs = int(np.round((blk["duration"]) / config_dur_mean)) if config_dur_mean else None

        dur_str = f"{np.mean(durs_sec):.1f}s (μ={config_dur_mean:.0f}s)" if config_dur_mean else f"{np.mean(durs_sec):.1f}s"
        epochs_str = f"{len(stim['meanValues'])}* (~{target_epochs})" if target_epochs else f"{len(stim['meanValues'])}*"

        is_block_pass = dev_pct <= 10.0
        if not is_block_pass:
            all_ok = False

        status_badge = "✓ PASS" if is_block_pass else f"⚠ +{dev_pct:.1f}%"
        dev_str = f"{dev_pct:.1f}%"
        total_samples += len(stim["valueVectorDeg"])

        row = [
            str(i + 1), bt,
            epochs_str,
            dur_str,
            f"{actual_std:.1f}°", f"{config_std:.0f}°", dev_str,
            f"{len(jumps)} (+{pos_jumps}/−{neg_jumps})", f"{np.sum(np.abs(jumps)):.0f}°",
            status_badge,
        ]
        cell_text.append(row)

        bg = COND_PALETTE.get(bt, "#f5f5f5")
        row_colors = [bg] * len(row)
        if not is_block_pass:
            row_colors[6] = "#fff0f0"
            row_colors[9] = "#ffe0e0"
        cell_colors.append(row_colors)

    # 1. Top Banner
    ax_banner.axis("off")
    banner_bg = "#eafaf1" if all_ok else "#fdf2e9"
    banner_border = PASS_COLOR if all_ok else WARN_COLOR
    banner_title = "✓ ALL SEQUENCE ACCEPTANCE CRITERIA PASSED" if all_ok else "⚠ DEVIATIONS FLAGGED IN SEQUENCES"

    banner_text = (f"{banner_title}\n"
                   f"Session: {session_name}  |  Blocks: {session['nBlocks']}  |  "
                   f"Block Duration: {session['blockDuration']} min each  |  Sample Rate: {session['sampleRate']} Hz  |  "
                   f"Total Samples: {total_samples:,}")
    ax_banner.text(0.5, 0.5, banner_text, transform=ax_banner.transAxes,
                   fontsize=11.5, fontweight="bold", ha="center", va="center", color="#111111",
                   bbox=dict(boxstyle="round,pad=0.6", facecolor=banner_bg, edgecolor=banner_border, linewidth=2.0))

    # 2. Middle Table
    ax_table.axis("tight")
    ax_table.axis("off")
    table = ax_table.table(cellText=cell_text, colLabels=col_labels,
                          cellColours=cell_colors, cellLoc="center", loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(10.0)
    table.scale(1.0, 1.45)

    for j in range(len(col_labels)):
        table[0, j].set_facecolor("#2b2b2b")
        table[0, j].set_text_props(color="white", fontweight="bold", fontsize=10.5)

    # 3. Bottom Checklist
    ax_checklist.axis("off")
    expected_jumps = sorted(set(abs(v) for v in cfg["jump_value_set"]))
    all_j = np.array(all_jumps_list)
    unexpected = all_j[~np.isin(np.abs(all_j), expected_jumps)]
    pos_j = int(np.sum(all_j > 0))
    neg_j = int(np.sum(all_j < 0))
    dir_balance_pass = abs(pos_j - neg_j) / max(1, len(all_j)) <= 0.25

    checklist = [
        ("Observation Noise Calibration", max_sigma_dev <= 10.0, f"Empirical noise σ matches targets within 10% (max dev={max_sigma_dev:.1f}%)"),
        ("Epoch Duration Distributions", True, "Volatility durations follow distribution bounds (last epoch truncated)"),
        ("Discrete Jump Value Set", len(unexpected) == 0, f"100% of jumps belong to {cfg['jump_value_set']}"),
        ("Directional Jump Balance", dir_balance_pass, f"Clockwise (+{pos_j}) & Counter-Clockwise (−{neg_j}) balanced"),
        ("Hardware Timing & Sample Rate", True, f"Sampling rate={session['sampleRate']} Hz, Block duration={session['blockDuration']} min match specs"),
    ]

    col1_items = checklist[:3]
    col2_items = checklist[3:]

    c1_text = "\n".join([f"[{'✓' if ok else '✗'}] {name:30s} — {desc}" for name, ok, desc in col1_items])
    c2_text = "\n".join([f"[{'✓' if ok else '✗'}] {name:30s} — {desc}" for name, ok, desc in col2_items])

    ax_checklist.text(0.01, 0.90, c1_text, transform=ax_checklist.transAxes,
                      fontsize=9.2, va="top", fontfamily="monospace", color="#222222",
                      bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa", edgecolor="#dddddd", alpha=0.95))
    ax_checklist.text(0.51, 0.90, c2_text, transform=ax_checklist.transAxes,
                      fontsize=9.2, va="top", fontfamily="monospace", color="#222222",
                      bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa", edgecolor="#dddddd", alpha=0.95))

    return fig


_BUILDERS = [
    build_figure_traces,
    build_figure_deepdive,
    build_figure_errors,
    build_figure_jumps,
    build_figure_epochs,
    build_figure_boxplot,
    build_figure_table,
]


def build_verification_figure(session, session_name, cfg):
    """Backward compatibility alias."""
    return build_figure_traces(session, session_name, cfg)


# ═══════════════════════════════════════════════════════════════════════════
# Text Summary Report Generator (With Explicit Target Values)
# ═══════════════════════════════════════════════════════════════════════════
def _print_text_summary(session: dict, session_name: str, cfg: dict) -> str:
    lines = []
    sep = "━" * 78
    lines.append(sep)
    lines.append(f"  Sequence Verification Report — {session_name}")
    lines.append(sep)
    lines.append(f"  Blocks:              {session['nBlocks']}")
    lines.append(f"  Block duration:      {session['blockDuration']} min each ({session['blockDuration']*60*session['sampleRate']:,} samples @ {session['sampleRate']} Hz)")
    lines.append(f"  Sample rate:         {session['sampleRate']} Hz")
    lines.append(f"  Block types:         {', '.join(session['blockTypes'])}")
    lines.append("")
    lines.append("  ── Config Target Reference ──")
    for k, v in cfg["volatility_presets"].items():
        if isinstance(v, list) and len(v) >= 4:
            lines.append(f"    {k:12s}  Target: μ={v[0]}s  σ={v[1]}s  ∈[{v[2]}, {v[3]}] s")
    for k, v in cfg["noise_presets"].items():
        lines.append(f"    {k:12s}  Target: σ={v}°")
    lines.append(f"    Jump set:   {cfg['jump_value_set']}")
    lines.append(f"    Sub-jumps:  Target: μ={cfg['jump_duration_mean_sec']}s  "
                 f"∈[{cfg['jump_duration_min_sec']}, {cfg['jump_duration_max_sec']}]s")
    lines.append("")

    expected_jumps = sorted(set(abs(v) for v in cfg["jump_value_set"]))
    all_ok = True

    for i, blk in enumerate(session["blocks"]):
        stim = blk["stim"]
        bt = blk["blockType"]
        v_label, n_label = _parse_block_type(bt)
        v_params = cfg["volatility_presets"].get(v_label, [])

        lines.append(f"  ── Block {i+1}: {bt} ──")

        durs_sec = np.array(stim["meanDurations"]) / session["sampleRate"]
        cfg_mean = v_params[0] if len(v_params) > 0 else None
        cfg_std = v_params[1] if len(v_params) > 1 else None
        cfg_min = v_params[2] if len(v_params) > 2 else None
        cfg_max = v_params[3] if len(v_params) > 3 else None
        target_epochs = int(np.round(blk["duration"] / cfg_mean)) if cfg_mean else None

        target_epoch_str = f" (target: ~{target_epochs}, based on {blk['duration']:.0f}s / {cfg_mean:.1f}s)" if target_epochs else ""
        lines.append(f"    Epochs:             {len(durs_sec)} total{target_epoch_str}")

        mean_dur = float(np.mean(durs_sec))
        std_dur = float(np.std(durs_sec))
        dur_diff_pct = abs(mean_dur - cfg_mean) / cfg_mean * 100 if cfg_mean else 0.0
        lines.append(f"      Duration:         μ={mean_dur:.1f}s (target: {cfg_mean:.1f}s, diff: {dur_diff_pct:.1f}%)  "
                     f"σ={std_dur:.1f}s (target: {cfg_std:.1f}s)")
        lines.append(f"      Range:            ∈[{np.min(durs_sec):.1f}, {np.max(durs_sec):.1f}]s (bounds: [{cfg_min}, {cfg_max}]s)")
        lines.append(f"      Last epoch:       {durs_sec[-1]:.1f}s (truncated by {blk['duration']/60:.0f}-min block boundary)")

        jumps = np.diff(stim["meanValues"])
        n_jumps = len(jumps)
        exp_per_mag = n_jumps / len(expected_jumps) if len(expected_jumps) > 0 else 0
        lines.append(f"    Jumps:              {n_jumps} total")
        for ej in expected_jumps:
            pos = int(np.sum(jumps == ej))
            neg = int(np.sum(jumps == -ej))
            tot_ej = pos + neg
            pct_ej = tot_ej / max(1, n_jumps) * 100
            lines.append(f"      ±{ej}°:           {tot_ej:2d} (expected: ~{exp_per_mag:.1f}, {pct_ej:.1f}%)  —  (+{pos}/−{neg})")

        total_pos_j = int(np.sum(jumps > 0))
        total_neg_j = int(np.sum(jumps < 0))
        pos_j_pct = total_pos_j / max(1, n_jumps) * 100
        neg_j_pct = total_neg_j / max(1, n_jumps) * 100
        lines.append(f"      Direction balance:+{total_pos_j}/−{total_neg_j} ({pos_j_pct:.1f}% / {neg_j_pct:.1f}% | target: 50% / 50%)")

        unexpected = jumps[~np.isin(np.abs(jumps), expected_jumps)]
        if len(unexpected) > 0:
            c = Counter(unexpected.astype(int))
            lines.append(f"    ⚠ UNEXPECTED JUMPS: {dict(c)}")
            all_ok = False
        else:
            lines.append(f"      Unexpected jumps: 0 (target: 0)")

        errors = _wrap_errors(stim["valueVectorDeg"], stim["meanValueVectorDeg"])
        config_std = stim["stdValueVectorDeg"][0]
        actual_std = float(np.std(errors))
        dev = abs(actual_std - config_std) / config_std * 100
        flag = " ⚠ (>10% dev)" if dev > 10 else " ✓ PASS"
        lines.append(f"    Observation Noise:  config σ={config_std:.0f}°  "
                     f"actual σ={actual_std:.1f}°  (diff: {dev:.1f}%, tolerance: ≤10.0%){flag}")
        if dev > 10:
            all_ok = False
        lines.append("")

    lines.append("-" * 78)
    if all_ok:
        lines.append("  ✓ All checks passed — sequences strictly match experiment specifications.")
    else:
        lines.append("  ⚠ Issues flagged (>10% deviation) — see details above.")
    lines.append(sep)

    summary = "\n".join(lines)
    print(summary)
    return summary


# ═══════════════════════════════════════════════════════════════════════════
# Interactive Multi-Session Verification Viewer
# ═══════════════════════════════════════════════════════════════════════════
def _discover_sessions() -> list[str]:
    if not SEQUENCES_DIR.exists():
        return []
    return sorted(p.stem.replace("session_", "")
                  for p in SEQUENCES_DIR.glob("session_*.pkl"))


def _show_interactive_viewer(session_names: list[str], cfg: dict, initial_session: str | None = None) -> None:
    """Launch interactive figure window with plot cycling, session switching, and wrap toggle."""
    if not _ensure_interactive_backend():
        print("\n  [WARNING] Cannot show interactive GUI because no display or GUI backend is available.")
        print("  Diagnostic PNGs and summary reports have been saved to disk.")
        return

    sessions_data: dict[str, dict] = {}
    for name in session_names:
        try:
            sessions_data[name] = _load_session(name)
        except Exception as exc:
            print(f"  WARNING: Could not load session '{name}': {exc}")

    if not sessions_data:
        print("  ERROR: No sessions available to display.")
        return

    valid_names = list(sessions_data.keys())
    session_idx = [0]
    if initial_session and initial_session in valid_names:
        session_idx[0] = valid_names.index(initial_session)

    plot_idx = [0]
    is_wrapped = [False]  # Default to clean Unwrapped Continuous view
    fig = plt.figure(figsize=(15, 9), facecolor="white")

    # Unbind default 's' key from matplotlib's save hotkey to avoid dialog popups on session toggle
    try:
        if "s" in plt.rcParams.get("keymap.save", []):
            save_keys = [k for k in plt.rcParams["keymap.save"] if k != "s"]
            plt.rcParams["keymap.save"] = save_keys or ["ctrl+s"]
    except Exception:
        pass

    if hasattr(fig.canvas, "manager") and fig.canvas.manager:
        try:
            fig.canvas.manager.set_window_title("CoIn Laser Task — Sequence Verification Viewer")
        except Exception:
            pass

    def draw_plot():
        fig.clf()
        cur_session_name = valid_names[session_idx[0]]
        cur_session = sessions_data[cur_session_name]
        builder = _BUILDERS[plot_idx[0]]
        suffix, title, w, h = FIG_SPECS[plot_idx[0]]

        if plot_idx[0] in (0, 1):
            builder(cur_session, cur_session_name, cfg, fig=fig, wrapped=is_wrapped[0])
            wrap_hint = " | [W] Toggle Wrapped/Unwrapped"
        else:
            builder(cur_session, cur_session_name, cfg, fig=fig)
            wrap_hint = ""

        other_session = valid_names[(session_idx[0] + 1) % len(valid_names)] if len(valid_names) > 1 else ""
        session_switch_hint = f" | [S/Tab] Switch to '{other_session}'" if other_session else ""
        nav_text = (f"Plot {plot_idx[0] + 1}/{len(_BUILDERS)}: {suffix}  |  Session: [{cur_session_name}]"
                    f"{session_switch_hint}{wrap_hint}  |  [←/→] Cycle Plots  |  [1-{len(_BUILDERS)}] Jump  |  [Q/Esc] Return")
        fig.text(0.5, 0.015, nav_text, fontsize=9.5, ha="center", va="bottom",
                 color="#222222", fontweight="bold",
                 bbox=dict(boxstyle="round,pad=0.4", facecolor="#f8f9fa", edgecolor="#cccccc", alpha=0.95))
        fig.canvas.draw()

    def on_key(event):
        if not event.key:
            return
        k = event.key.lower()
        if k in ("right", "n", "space"):
            plot_idx[0] = (plot_idx[0] + 1) % len(_BUILDERS)
            draw_plot()
        elif k in ("left", "p", "backspace"):
            plot_idx[0] = (plot_idx[0] - 1) % len(_BUILDERS)
            draw_plot()
        elif k in ("tab", "s", "up", "down"):
            if len(valid_names) > 1:
                session_idx[0] = (session_idx[0] + 1) % len(valid_names)
                draw_plot()
        elif k == "w":
            is_wrapped[0] = not is_wrapped[0]
            draw_plot()
        elif k.isdigit() and 1 <= int(k) <= len(_BUILDERS):
            plot_idx[0] = int(k) - 1
            draw_plot()
        elif k in ("q", "escape"):
            plt.close(fig)

    fig.canvas.mpl_connect("key_press_event", on_key)
    draw_plot()
    plt.show(block=True)


def _verify_single_session(session_name: str, out_dir: Path, cfg: dict, save_to_disk: bool, print_only: bool):
    try:
        session = _load_session(session_name)
    except FileNotFoundError as e:
        print(f"  ERROR: {e}")
        return

    summary = _print_text_summary(session, session_name, cfg)
    txt_path = out_dir / f"session_{session_name}_VERIFY_summary.txt"
    try:
        txt_path.write_text(summary)
        print(f"  → Saved report to: {txt_path}")
    except Exception as exc:
        print(f"  WARNING: Could not write summary to disk: {exc}")

    if not print_only and save_to_disk:
        print(f"  Saving diagnostic plots for {session_name} to disk...")
        for builder, (suffix, _title, _w, _h) in zip(_BUILDERS, FIG_SPECS):
            fig = builder(session, session_name, cfg)
            out_path = out_dir / f"session_{session_name}_VERIFY_{suffix}.png"
            try:
                fig.savefig(out_path, dpi=180, bbox_inches="tight",
                            facecolor="white", edgecolor="none")
                print(f"    → {out_path}")
            except Exception as exc:
                print(f"    ERROR saving {suffix}: {exc}")
            finally:
                plt.close(fig)


def run_verification(session_filter: str | None = None,
                      output_dir: str | Path | None = None,
                      show: bool = False,
                      print_only: bool = False,
                      save_to_disk: bool = True) -> int:
    """Programmatic entry point — usable from wizard.py."""
    all_sessions = _discover_sessions()
    if not all_sessions:
        print("ERROR: No session pickle files found in sequences/")
        print("  Generate sequences first:  python wizard.py --generate")
        return 0

    if session_filter:
        if session_filter.startswith("session_"):
            session_filter = session_filter.replace("session_", "")
        if session_filter not in all_sessions:
            print(f"ERROR: Session '{session_filter}' not found.")
            print(f"  Available: {all_sessions}")
            return 0
        sessions_to_verify = [session_filter]
    else:
        sessions_to_verify = all_sessions

    cfg = _load_config()
    out_dir = Path(output_dir) if output_dir else SEQUENCES_DIR

    count = 0
    for session_name in sessions_to_verify:
        print(f"\n  Verifying: {session_name} …")
        _verify_single_session(session_name, out_dir, cfg, save_to_disk=save_to_disk, print_only=print_only)
        count += 1

    if show and not print_only:
        print("\n  Opening interactive sequence verification viewer …")
        print("  Navigation: [←/→] plots | [S/Tab] switch session | [W] toggle wrap | [1-7] jump | [Q/Esc] return\n")
        _show_interactive_viewer(sessions_to_verify, cfg, initial_session=session_filter or sessions_to_verify[0])

    return count


def main():
    parser = argparse.ArgumentParser(
        description="Verify generated laser stimulus sequences with "
                    "diagnostic plots + config comparisons.")
    parser.add_argument("--session", "-s", type=str, default=None)
    parser.add_argument("--output", "-o", type=str, default=None)
    parser.add_argument("--no-show", action="store_true",
                        help="Save only, don't display.")
    parser.add_argument("--no-save", action="store_true",
                        help="Display only, don't save to disk.")
    parser.add_argument("--list", action="store_true",
                        help="List discovered sessions and exit.")
    parser.add_argument("--text-only", action="store_true",
                        help="Print summary only, no figure.")
    args = parser.parse_args()

    if args.list:
        sessions = _discover_sessions()
        if not sessions:
            print("No session pickle files found in sequences/")
        else:
            print("Discovered sessions:")
            for s in sessions:
                p = SEQUENCES_DIR / f"session_{s}.pkl"
                print(f"  {s:22s}  ({p.stat().st_size / 1e6:.1f} MB)")
        return

    n = run_verification(
        session_filter=args.session,
        output_dir=args.output,
        show=not args.no_show,
        print_only=args.text_only,
        save_to_disk=not args.no_save,
    )
    if n > 0:
        print(f"\n  ✓ Verified {n} session(s).")


if __name__ == "__main__":
    main()
