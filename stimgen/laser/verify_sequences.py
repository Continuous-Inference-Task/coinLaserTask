#!/usr/bin/env python3
"""
verify_sequences.py — Load generated laser sequences and produce
polished diagnostic/verification plots with config comparisons overlaid.

Usage:
    python verify_sequences.py                          # verify all sessions
    python verify_sequences.py --session main        # one specific session
    python verify_sequences.py --session practice    # practice only
    python verify_sequences.py --no-show                # save only, don't display
    python verify_sequences.py --output /tmp/my_plots/  # custom output dir
    python verify_sequences.py --list                   # list available sessions

Each run produces for every session:
    <session>_VERIFY_full.png   — 7-panel diagnostic figure
    <session>_VERIFY_summary.txt — text report printed + saved

Panels with **config expected** annotations:
    1. Trace grid — all blocks, true mean + noisy obs + config epoch mean
    2. Block deep-dive — full trace with epoch boundaries, first-30s zoom
    3. Error histogram — obs−true vs. N(0, config_σ²) overlay
    4. Jump-size histogram — bars labelled, unexpected sizes flagged
    5. Epoch durations — per-block-type histogram with config [μ,σ,min,max] lines
    6. Error boxplot — per-block-type with config-expected σ band
    7. Stats table — actual vs. config expected side-by-side
"""

from __future__ import annotations

import os
import sys
import subprocess
import pickle
import argparse
from pathlib import Path
from collections import Counter

import numpy as np
from scipy.stats import norm as scipy_norm
import matplotlib
# Don't force a backend here — let run_verification() decide.
# When show=True we use the system default (TkAgg/Qt5Agg/MacOSX)
# so plt.show() works natively everywhere.
# When show=False we switch to Agg for headless PNG saving.
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.gridspec import GridSpec


def _try_show_figure(fig) -> bool:
    """Show the figure in a native matplotlib window.

    Uses the system default interactive backend (TkAgg on Linux/Windows,
    MacOSX on macOS).  Falls back gracefully if no display is available
    (SSH, headless server).
    """
    try:
        plt.show(block=False)
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════
# path helpers
# ═══════════════════════════════════════════════════════════════════════════
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SEQUENCES_DIR = PROJECT_ROOT / "sequences"


def _load_config():
    """Import config module and return sanitised values."""
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
# colour palette — soft, distinguishable, colourblind-friendly
# ═══════════════════════════════════════════════════════════════════════════
TRUE_COLOR = "#2166ac"        # deep blue — true mean
OBS_COLOR = "#b2182b"         # warm red — observations
OBS_ALPHA = 0.35
EPOCH_LINE_COLOR = "#999999"  # grey epoch boundaries
CONFIG_COLOR = "#4daf4a"      # green — config reference lines
WARN_COLOR = "#e41a1c"        # bright red — warnings
GRID_COLOR = "#e0e0e0"

COND_PALETTE = {
    "stable+precise":  "#a6d854",
    "stable+noisy":    "#66c2a5",
    "volatile+precise": "#fc8d62",
    "volatile+noisy":  "#e78ac3",
}

JUMP_PALETTE = {20: "#4daf4a", 30: "#ff7f00", 40: "#e41a1c"}


def _parse_block_type(bt: str) -> tuple[str, str]:
    if "+" in bt:
        v, n = bt.split("+", 1)
        return v, n
    return bt, ""


def _wrap_errors(obs, true):
    """Correct circular wrap-around errors in degrees."""
    e = obs - true
    e = np.where(e > 180, e - 360, e)
    e = np.where(e < -180, e + 360, e)
    return e


def _style_ax(ax, xlabel="", ylabel="", title="", **kwargs):
    """Apply consistent clean styling to an axes."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, color=GRID_COLOR, linewidth=0.4, alpha=0.7)
    ax.tick_params(labelsize=10)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=11, color="#444444")
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=11, color="#444444")
    if title:
        ax.set_title(title, fontsize=13, fontweight="bold", color="#333333", **kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# Panel 1 — Trace Grid
# ═══════════════════════════════════════════════════════════════════════════
def _plot_trace_grid(axes, session: dict, cfg: dict) -> None:
    n_blocks = session["nBlocks"]
    for i in range(n_blocks):
        ax = axes.flat[i] if hasattr(axes, "flat") else axes
        blk = session["blocks"][i]
        stim = blk["stim"]
        t = stim["time"] / 60  # minutes
        true_pos = stim["meanValueVectorDeg"]
        obs_pos = stim["valueVectorDeg"]
        noise_cfg = stim["stdValueVectorDeg"][0]

        # down-sample observations for scatter
        n_pts = len(t)
        step = max(1, n_pts // 2000)
        idx = slice(0, n_pts, step)

        ax.plot(t, true_pos, color=TRUE_COLOR, linewidth=0.9,
                label="True mean", zorder=4)
        ax.scatter(t[idx], obs_pos[idx], color=OBS_COLOR, s=0.25,
                   alpha=OBS_ALPHA, label="Observations", zorder=2, rasterized=True)

        # config expected epoch duration as annotation
        bt = blk["blockType"]
        v_label, n_label = _parse_block_type(bt)
        v_params = cfg["volatility_presets"].get(v_label)

        ax.set_title(f"B{i+1}: {bt}   σ={noise_cfg:.0f}°", fontsize=11,
                     fontweight="bold", color="#333333")
        ax.set_xlabel("Time (min)", fontsize=10, color="#666666")
        ax.set_ylabel("Position (°)", fontsize=10, color="#666666")
        ax.tick_params(labelsize=9)
        ax.set_ylim(-5, 365)
        ax.grid(True, color=GRID_COLOR, linewidth=0.3, alpha=0.5)

    # hide unused
    for j in range(n_blocks, len(axes.flat)):
        axes.flat[j].set_visible(False)

    # single legend
    if n_blocks > 0:
        first_ax = axes.flat[0] if hasattr(axes, "flat") else axes
        first_ax.legend(fontsize=10, framealpha=0.85, loc="upper right",
                        handlelength=1.2, borderpad=0.4)


# ═══════════════════════════════════════════════════════════════════════════
# Panel 2 — Block Deep-Dive (first block)
# ═══════════════════════════════════════════════════════════════════════════
def _plot_block_deep_dive(ax_full, ax_zoom, session: dict, cfg: dict) -> None:
    blk = session["blocks"][0]
    stim = blk["stim"]
    t = stim["time"]
    true_pos = stim["meanValueVectorDeg"]
    obs_pos = stim["valueVectorDeg"]
    noise_cfg = stim["stdValueVectorDeg"][0]

    boundaries = np.cumsum(stim["meanDurations"]) / session["sampleRate"]
    n_epochs = len(boundaries)

    bt = blk["blockType"]
    v_label, _ = _parse_block_type(bt)
    v_params = cfg["volatility_presets"].get(v_label, [])
    v_mean = v_params[0] if len(v_params) > 0 else None

    # ── full trace ──
    ax_full.plot(t / 60, true_pos, color=TRUE_COLOR, linewidth=0.7,
                 label="True mean", zorder=4)
    ax_full.plot(t / 60, obs_pos, color=OBS_COLOR, linewidth=0.2,
                 alpha=0.6, label="Observed", zorder=2)
    for b in boundaries:
        ax_full.axvline(x=b / 60, color=EPOCH_LINE_COLOR, linestyle=":",
                        linewidth=0.4, alpha=0.5, zorder=1)
    _style_ax(ax_full,
              title=f"Block 1: {bt} — Full Trace "
                    f"({blk['duration']/60:.0f} min, {n_epochs} epochs)",
              ylabel="Position (°)")
    ax_full.legend(fontsize=10, framealpha=0.8, loc="upper right")
    ax_full.set_ylim(-5, 365)

    # ── 30 s zoom ──
    zoom_end = min(30, t[-1])
    mask = t <= zoom_end
    ax_zoom.plot(t[mask], true_pos[mask], color=TRUE_COLOR, linewidth=1.0,
                 zorder=4)
    ax_zoom.plot(t[mask], obs_pos[mask], color=OBS_COLOR, linewidth=0.4,
                 alpha=0.7, zorder=2)
    for b in boundaries:
        if b <= zoom_end:
            ax_zoom.axvline(x=b, color=EPOCH_LINE_COLOR, linestyle=":",
                            linewidth=0.6, alpha=0.6, zorder=1)
    _style_ax(ax_zoom, title="First 30 s — Zoom",
              xlabel="Time (s)", ylabel="Position (°)")
    ax_zoom.set_ylim(-5, 365)


# ═══════════════════════════════════════════════════════════════════════════
# Panel 3 — Error Histogram (obs − true) vs theoretical normal
# ═══════════════════════════════════════════════════════════════════════════
def _plot_error_histogram(ax, session: dict, cfg: dict) -> None:
    all_errors = []
    all_noise_cfg = []
    for blk in session["blocks"]:
        stim = blk["stim"]
        errors = _wrap_errors(stim["valueVectorDeg"], stim["meanValueVectorDeg"])
        all_errors.append(errors)
        all_noise_cfg.append(stim["stdValueVectorDeg"][0])

    combined = np.concatenate(all_errors)
    # use the first block's config noise for the overlay — or average
    noise_cfg = all_noise_cfg[0]

    ax.hist(combined, bins=120, density=True, color="#7b8cc4", alpha=0.55,
            edgecolor="white", linewidth=0.2, label="All blocks")

    x = np.linspace(-4 * noise_cfg, 4 * noise_cfg, 300)
    ax.plot(x, scipy_norm.pdf(x, 0, noise_cfg), color=CONFIG_COLOR,
            linewidth=2.0, linestyle="-",
            label=f"Config: N(0, {noise_cfg:.0f}°)")
    # actual best-fit normal
    actual_std = np.std(combined)
    ax.plot(x, scipy_norm.pdf(x, 0, actual_std), color="#e41a1c",
            linewidth=1.5, linestyle="--",
            label=f"Actual: N(0, {actual_std:.1f}°)")

    _style_ax(ax,
              title="Observation Error Distribution",
              xlabel="Error obs−true (°)", ylabel="Density")
    ax.legend(fontsize=10, framealpha=0.85, loc="upper right")
    ax.set_xlim(-4 * noise_cfg, 4 * noise_cfg)

    # deviation annotation
    dev_pct = abs(actual_std - noise_cfg) / noise_cfg * 100
    color = WARN_COLOR if dev_pct > 10 else "#333333"
    ax.text(0.98, 0.95,
            f"σ config={noise_cfg:.0f}°\nσ actual={actual_std:.1f}°  "
            f"({dev_pct:.1f}% off)",
            transform=ax.transAxes, fontsize=10.5, ha="right", va="top",
            color=color, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="#cccccc", alpha=0.85))


# ═══════════════════════════════════════════════════════════════════════════
# Panel 4 — Jump Size Histogram
# ═══════════════════════════════════════════════════════════════════════════
def _plot_jump_histogram(ax, session: dict, cfg: dict) -> None:
    all_jumps = []
    for blk in session["blocks"]:
        jumps = np.abs(np.diff(blk["stim"]["meanValues"]))
        all_jumps.extend(jumps.tolist())
    all_jumps = np.array(all_jumps)

    expected = sorted(set(abs(v) for v in cfg["jump_value_set"]))
    counts = [int(np.sum(all_jumps == e)) for e in expected]
    bar_colors = [JUMP_PALETTE.get(e, "#999999") for e in expected]

    bars = ax.bar([str(e) for e in expected], counts, color=bar_colors,
                  edgecolor="white", linewidth=0.6, width=0.65)

    # value labels on top of bars
    for bar, count, e in zip(bars, counts, expected):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(0.5, bar.get_height() * 0.03),
                str(count), ha="center", va="bottom", fontsize=11,
                fontweight="bold", color="#333333")

    # unexpected jumps
    unexpected = all_jumps[~np.isin(all_jumps, expected)]
    if len(unexpected) > 0:
        ax.text(0.5, 0.93, f"⚠ {len(unexpected)} UNEXPECTED!",
                transform=ax.transAxes, fontsize=12, color=WARN_COLOR,
                fontweight="bold", ha="center", va="top",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#fff2f2",
                          edgecolor=WARN_COLOR, alpha=0.9))

    # config annotation
    cfg_label = f"Config: JUMP_VALUE_SET = {cfg['jump_value_set']}"
    ax.text(0.5, -0.18, cfg_label, transform=ax.transAxes, fontsize=10,
            ha="center", va="top", color="#666666",
            style="italic")

    _style_ax(ax, title="True-Mean Jump Sizes — All Blocks",
              xlabel="Jump magnitude (°)", ylabel="Count")
    ax.set_yticks(ax.get_yticks())
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))


# ═══════════════════════════════════════════════════════════════════════════
# Panel 5 — Epoch Duration Histogram with config lines
# ═══════════════════════════════════════════════════════════════════════════
def _plot_epoch_duration_histogram(ax, session: dict, cfg: dict) -> None:
    n_blocks = session["nBlocks"]
    # group by block type — collect durations and config params
    bt_groups: dict[str, dict] = {}
    for i, blk in enumerate(session["blocks"]):
        bt = blk["blockType"]
        durs = np.array(blk["stim"]["meanDurations"]) / session["sampleRate"]
        if bt not in bt_groups:
            v_label, _ = _parse_block_type(bt)
            v_params = cfg["volatility_presets"].get(v_label, [])
            bt_groups[bt] = {"durs": [], "config": v_params, "color": None}
        bt_groups[bt]["durs"].extend(durs.tolist())

    # assign colors
    cmap = plt.cm.tab10
    for j, bt in enumerate(bt_groups):
        bt_groups[bt]["color"] = cmap(j % 10)

    all_dur_arrays = [np.array(v["durs"]) for v in bt_groups.values()]
    if all_dur_arrays:
        max_dur = max(np.max(a) for a in all_dur_arrays)
    else:
        max_dur = 10
    bins = np.linspace(0, max_dur * 1.05, 55)

    for bt, grp in bt_groups.items():
        durs = np.array(grp["durs"])
        ax.hist(durs, bins=bins, alpha=0.45, color=grp["color"],
                label=f"{bt} (n={len(durs)})", edgecolor="white",
                linewidth=0.2)

        # config vertical lines: mean (solid), min/max (dashed)
        cfg_params = grp["config"]
        if len(cfg_params) >= 4:
            cfg_mean, cfg_std, cfg_min, cfg_max = cfg_params[:4]
            ymax = ax.get_ylim()[1]
            ax.axvline(x=cfg_mean, color=grp["color"], linewidth=2.0,
                       linestyle="-", alpha=0.8)
            ax.axvline(x=cfg_min, color=grp["color"], linewidth=1.0,
                       linestyle="--", alpha=0.5)
            ax.axvline(x=cfg_max, color=grp["color"], linewidth=1.0,
                       linestyle="--", alpha=0.5)
            # config text label
            ax.text(cfg_mean, ymax * 0.92,
                    f"  config μ={cfg_mean}s", fontsize=9.5,
                    color=grp["color"], fontweight="bold", va="top")

    _style_ax(ax,
              title="Epoch Duration Distribution — per Block Type",
              xlabel="Epoch duration (s)", ylabel="Count")
    ax.legend(fontsize=9.5, framealpha=0.85, loc="upper right",
              handlelength=1.0)


# ═══════════════════════════════════════════════════════════════════════════
# Panel 6 — Error Boxplot with config σ bands
# ═══════════════════════════════════════════════════════════════════════════
def _plot_error_boxplot(ax, session: dict, cfg: dict) -> None:
    block_types = session["blockTypes"]
    data = []
    config_stds = []
    for blk in session["blocks"]:
        errors = _wrap_errors(blk["stim"]["valueVectorDeg"],
                              blk["stim"]["meanValueVectorDeg"])
        data.append(errors)
        config_stds.append(blk["stim"]["stdValueVectorDeg"][0])

    bp = ax.boxplot(data, tick_labels=block_types, patch_artist=True,
                    showfliers=False, widths=0.55, medianprops={"color": "#333333",
                    "linewidth": 1.2})

    n_bt = len(block_types)
    cmap = plt.cm.Set2
    for i, (patch, bt) in enumerate(zip(bp["boxes"], block_types)):
        color = COND_PALETTE.get(bt, cmap(i / max(n_bt, 1)))
        patch.set_facecolor(color)
        patch.set_alpha(0.55)
        patch.set_edgecolor("#333333")
        patch.set_linewidth(0.6)

    # config σ horizontal band for each block type
    for i, (bt, cfg_std) in enumerate(zip(block_types, config_stds)):
        x_pos = i + 1
        ax.axhspan(-cfg_std, cfg_std, xmin=(x_pos - 0.38) / n_bt,
                   xmax=(x_pos + 0.38) / n_bt,
                   facecolor=CONFIG_COLOR, alpha=0.08, zorder=0)
        ax.axhline(y=cfg_std, xmin=(x_pos - 0.4) / n_bt,
                   xmax=(x_pos + 0.4) / n_bt,
                   color=CONFIG_COLOR, linewidth=1.0, linestyle="--", alpha=0.7)
        ax.axhline(y=-cfg_std, xmin=(x_pos - 0.4) / n_bt,
                   xmax=(x_pos + 0.4) / n_bt,
                   color=CONFIG_COLOR, linewidth=1.0, linestyle="--", alpha=0.7)
        actual_std = np.std(data[i])
        dev = abs(actual_std - cfg_std) / cfg_std * 100
        color = WARN_COLOR if dev > 10 else "#444444"
        ax.annotate(f"σ={actual_std:.1f}°", xy=(x_pos, np.percentile(data[i], 90)),
                    fontsize=9.5, ha="center", va="bottom", color=color,
                    fontweight="bold")

    _style_ax(ax, title="Observation Error by Block Type",
              ylabel="Error (°)")
    ax.axhline(y=0, color="#333333", linewidth=0.6, linestyle="-", alpha=0.5)

    # legend for config band
    from matplotlib.patches import Patch
    config_patch = Patch(facecolor=CONFIG_COLOR, alpha=0.15,
                         label=f"Config ±σ range")
    ax.legend(handles=[config_patch], fontsize=9.5, framealpha=0.85,
              loc="lower right")


# ═══════════════════════════════════════════════════════════════════════════
# Panel 7 — Stats Table: actual vs. config expected
# ═══════════════════════════════════════════════════════════════════════════
def _plot_stats_table(ax, session: dict, cfg: dict) -> None:
    col_labels = ["Blk", "Block Type",
                  "Epochs", "Dur μ (s)", "Config μ (s)",
                  "σ actual", "σ config", "Δσ%",
                  "Jumps", "Σ|Δ|°"]

    cell_text = []
    cell_colors = []
    all_ok = True

    for i, blk in enumerate(session["blocks"]):
        stim = blk["stim"]
        bt = blk["blockType"]
        v_label, n_label = _parse_block_type(bt)

        durs_sec = np.array(stim["meanDurations"]) / session["sampleRate"]

        errors = _wrap_errors(stim["valueVectorDeg"], stim["meanValueVectorDeg"])
        jumps = np.diff(stim["meanValues"])

        config_std = stim["stdValueVectorDeg"][0]
        actual_std = np.std(errors)
        dev_pct = abs(actual_std - config_std) / config_std * 100

        v_params = cfg["volatility_presets"].get(v_label, [])
        config_dur_mean = v_params[0] if len(v_params) > 0 else None

        dur_mean_str = f"{np.mean(durs_sec):.1f}"
        cfg_mean_str = f"{config_dur_mean:.0f}" if config_dur_mean is not None else "—"

        dev_str = f"{dev_pct:.1f}"
        row_color = "#ffffff"
        if dev_pct > 10:
            dev_str = f"⚠ {dev_pct:.1f}"
            row_color = "#fff0f0"
            all_ok = False

        row = [
            str(i + 1), bt,
            f"{len(stim['meanValues'])}*",
            dur_mean_str, cfg_mean_str,
            f"{actual_std:.1f}", f"{config_std:.0f}", dev_str,
            str(len(jumps)), f"{np.sum(np.abs(jumps)):.0f}",
        ]
        cell_text.append(row)

        bg = COND_PALETTE.get(bt, "#f5f5f5")
        # use warning background if row has issues
        row_colors = [bg] * len(row)
        if row_color != "#ffffff":
            # only tint the dev cell
            row_colors = [bg if j != 7 else row_color for j in range(len(row))]
        cell_colors.append(row_colors)

    ax.axis("tight")
    ax.axis("off")
    table = ax.table(cellText=cell_text, colLabels=col_labels,
                     cellColours=cell_colors, cellLoc="center", loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 1.45)

    # style header
    for j in range(len(col_labels)):
        table[0, j].set_facecolor("#3a3a3a")
        table[0, j].set_text_props(color="white", fontweight="bold", fontsize=10.5)

    status = "✓ PASS" if all_ok else "⚠ FLAGGED"
    status_color = "#2ca02c" if all_ok else WARN_COLOR
    ax.set_title(f"Per-Block Summary  —  {status}", fontsize=12,
                 fontweight="bold", color=status_color, pad=10)

    return all_ok


# ═══════════════════════════════════════════════════════════════════════════
# Config header box
# ═══════════════════════════════════════════════════════════════════════════
def _add_config_header(fig, cfg: dict, session_name: str):
    """Add a compact config summary text box to the top of the figure."""
    lines = [
        f"Config:  SR={cfg['sample_rate']} Hz  |  "
        f"Jumps={cfg['jump_value_set']}  |  "
        f"Jump dur ∈ [{cfg['jump_duration_min_sec']}, "
        f"{cfg['jump_duration_max_sec']}] s  "
        f"(μ={cfg['jump_duration_mean_sec']} s)",
    ]
    vol_lines = []
    for k, v in cfg["volatility_presets"].items():
        if isinstance(v, list) and len(v) >= 4:
            vol_lines.append(f"{k}: μ={v[0]}s, σ={v[1]}s, ∈[{v[2]},{v[3]}]s")
    noise_lines = [f"Noise presets: " +
                   ", ".join(f"{k}={v}°" for k, v in cfg["noise_presets"].items())]

    all_text = " | ".join(lines + [",  ".join(vol_lines)] + noise_lines)
    fig.text(0.5, 0.993, all_text, fontsize=9, ha="center", va="top",
             color="#555555", style="italic",
             fontfamily="monospace")


# ═══════════════════════════════════════════════════════════════════════════
# Text summary
# ═══════════════════════════════════════════════════════════════════════════
def _print_text_summary(session: dict, session_name: str, cfg: dict) -> str:
    lines = []
    sep = "━" * 72
    lines.append(sep)
    lines.append(f"  Sequence Verification Report — {session_name}")
    lines.append(sep)
    lines.append(f"  Blocks:              {session['nBlocks']}")
    lines.append(f"  Block duration:      {session['blockDuration']} min each")
    lines.append(f"  Sample rate:         {session['sampleRate']} Hz")
    lines.append(f"  Block types:         {', '.join(session['blockTypes'])}")
    lines.append("")
    lines.append("  ── Config Reference ──")
    for k, v in cfg["volatility_presets"].items():
        if isinstance(v, list) and len(v) >= 4:
            lines.append(f"    {k:12s}  μ={v[0]}s  σ={v[1]}s  ∈[{v[2]}, {v[3]}] s")
    for k, v in cfg["noise_presets"].items():
        lines.append(f"    {k:12s}  σ={v}°")
    lines.append(f"    Jump set:   {cfg['jump_value_set']}")
    lines.append(f"    Sub-jumps:  μ={cfg['jump_duration_mean_sec']}s  "
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
        cfg_info = f"  (config μ={cfg_mean}s)" if cfg_mean else ""
        lines.append(f"    Epochs:             {len(durs_sec)} total")
        lines.append(f"      Duration:         μ={np.mean(durs_sec):.1f}s  σ={np.std(durs_sec):.1f}s  "
                     f"∈[{np.min(durs_sec):.1f}, {np.max(durs_sec):.1f}]s{cfg_info}")
        lines.append(f"      Last epoch:       {durs_sec[-1]:.1f}s (truncated)")

        jumps = np.diff(stim["meanValues"])
        lines.append(f"    Jumps:              {len(jumps)} total")
        for ej in expected_jumps:
            pos = int(np.sum(jumps == ej))
            neg = int(np.sum(jumps == -ej))
            lines.append(f"      ±{ej}°:           {pos + neg}  (+{pos}/−{neg})")

        unexpected = jumps[~np.isin(np.abs(jumps), expected_jumps)]
        if len(unexpected) > 0:
            c = Counter(unexpected.astype(int))
            lines.append(f"    ⚠ UNEXPECTED:       {dict(c)}")
            all_ok = False

        errors = _wrap_errors(stim["valueVectorDeg"], stim["meanValueVectorDeg"])
        config_std = stim["stdValueVectorDeg"][0]
        actual_std = np.std(errors)
        dev = abs(actual_std - config_std) / config_std * 100
        flag = " ⚠" if dev > 10 else ""
        lines.append(f"    σ:                  config={config_std:.0f}°  "
                     f"actual={actual_std:.1f}°  ({dev:.1f}% off){flag}")
        if dev > 10:
            all_ok = False
        lines.append("")

    lines.append("-" * 72)
    if all_ok:
        lines.append("  ✓ All checks passed — sequences match config (accounting for last epoch truncation).")
    else:
        lines.append("  ⚠ Issues flagged — see markers above.")
    lines.append(sep)

    summary = "\n".join(lines)
    print(summary)
    return summary


# ═══════════════════════════════════════════════════════════════════════════
# Individual figure builders — one high-res PNG per diagnostic
# ═══════════════════════════════════════════════════════════════════════════

FIG_SPECS = [
    ("01_traces",     "Trace Grid — True Mean + Observations",        22, 14),
    ("02_deepdive",   "Block Deep-Dive — Full Trace + 30 s Zoom",      22, 16),
    ("03_errors",     "Observation Error Distribution",                 14, 10),
    ("04_jumps",      "True-Mean Jump Sizes",                          14, 10),
    ("05_epochs",     "Epoch Duration Distribution",                   16, 10),
    ("06_boxplot",    "Observation Error by Block Type",               14, 10),
    ("07_table",      "Per-Block Summary Statistics",                  18, 6),
]


def _prepare_fig(fig, title_suffix: str, w: float, h: float, session_name: str) -> plt.Figure:
    if fig is None:
        fig = plt.figure(figsize=(w, h), facecolor="white")
    else:
        fig.clf()
        fig.set_facecolor("white")
    
    fig.suptitle(f"{title_suffix}  —  {session_name}",
                 fontsize=13, fontweight="bold", color="#222222", y=0.98)
    return fig


def build_figure_traces(session, session_name, cfg, fig=None):
    n_blocks = session["nBlocks"]
    n_cols = min(n_blocks, 4)
    n_rows = int(np.ceil(n_blocks / n_cols))
    fig = _prepare_fig(fig, FIG_SPECS[0][1], FIG_SPECS[0][2], FIG_SPECS[0][3], session_name)
    gs = fig.add_gridspec(n_rows, n_cols, hspace=0.55, wspace=0.30,
                           left=0.06, right=0.97, top=0.93, bottom=0.10)
    axes = gs.subplots(squeeze=False)
    _plot_trace_grid(axes, session, cfg)
    _add_config_header(fig, cfg, session_name)
    return fig


def build_figure_deepdive(session, session_name, cfg, fig=None):
    fig = _prepare_fig(fig, FIG_SPECS[1][1], FIG_SPECS[1][2], FIG_SPECS[1][3], session_name)
    gs = fig.add_gridspec(2, 1, hspace=0.38,
                           left=0.07, right=0.97, top=0.91, bottom=0.10)
    ax_full = fig.add_subplot(gs[0])
    ax_zoom = fig.add_subplot(gs[1])
    _plot_block_deep_dive(ax_full, ax_zoom, session, cfg)
    _add_config_header(fig, cfg, session_name)
    return fig


def build_figure_errors(session, session_name, cfg, fig=None):
    fig = _prepare_fig(fig, FIG_SPECS[2][1], FIG_SPECS[2][2], FIG_SPECS[2][3], session_name)
    ax = fig.add_subplot(1, 1, 1)
    _plot_error_histogram(ax, session, cfg)
    return fig


def build_figure_jumps(session, session_name, cfg, fig=None):
    fig = _prepare_fig(fig, FIG_SPECS[3][1], FIG_SPECS[3][2], FIG_SPECS[3][3], session_name)
    ax = fig.add_subplot(1, 1, 1)
    _plot_jump_histogram(ax, session, cfg)
    return fig


def build_figure_epochs(session, session_name, cfg, fig=None):
    fig = _prepare_fig(fig, FIG_SPECS[4][1], FIG_SPECS[4][2], FIG_SPECS[4][3], session_name)
    ax = fig.add_subplot(1, 1, 1)
    _plot_epoch_duration_histogram(ax, session, cfg)
    return fig


def build_figure_boxplot(session, session_name, cfg, fig=None):
    fig = _prepare_fig(fig, FIG_SPECS[5][1], FIG_SPECS[5][2], FIG_SPECS[5][3], session_name)
    ax = fig.add_subplot(1, 1, 1)
    _plot_error_boxplot(ax, session, cfg)
    return fig


def build_figure_table(session, session_name, cfg, fig=None):
    fig = _prepare_fig(fig, FIG_SPECS[6][1], FIG_SPECS[6][2], FIG_SPECS[6][3], session_name)
    ax = fig.add_subplot(1, 1, 1)
    _plot_stats_table(ax, session, cfg)
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
    """Backward compat — returns the trace grid."""
    return build_figure_traces(session, session_name, cfg)


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════
def _discover_sessions() -> list[str]:
    if not SEQUENCES_DIR.exists():
        return []
    return sorted(p.stem.replace("session_", "")
                  for p in SEQUENCES_DIR.glob("session_*.pkl"))


def _show_interactive_viewer(session: dict, session_name: str, cfg: dict):
    """Launch a single interactive figure window to cycle through all verification plots."""
    import matplotlib.pyplot as plt

    backend = plt.get_backend()
    if backend.lower() == 'agg':
        print("\n  [WARNING] Cannot show interactive GUI because the current backend is headless ('Agg').")
        print("  Please run in a terminal with GUI display capabilities to view interactive plots.")
        return

    current_idx = [0]
    
    # Create single window with a fixed, stable size that fits screens nicely
    fig = plt.figure(figsize=(15, 9), facecolor="white")
    
    def draw_plot():
        fig.clf()
        builder = _BUILDERS[current_idx[0]]
        suffix, title, w, h = FIG_SPECS[current_idx[0]]
        
        # Build plot onto the existing figure
        builder(session, session_name, cfg, fig=fig)
        
        # Add footer instructions
        nav_text = f"Plot {current_idx[0] + 1}/{len(_BUILDERS)} | Navigation: [Left/Right Arrow] or [N/P] to cycle | [Q] or [Esc] to return to menu"
        fig.text(0.5, 0.015, nav_text, fontsize=10, ha="center", va="bottom",
                 color="#444444", fontweight="bold",
                 bbox=dict(boxstyle="round,pad=0.4", facecolor="#f5f5f5", edgecolor="#cccccc", alpha=0.9))
        
        fig.canvas.draw()
        
    def on_key(event):
        if event.key in ("right", "n", "space"):
            current_idx[0] = (current_idx[0] + 1) % len(_BUILDERS)
            draw_plot()
        elif event.key in ("left", "p", "backspace"):
            current_idx[0] = (current_idx[0] - 1) % len(_BUILDERS)
            draw_plot()
        elif event.key in ("q", "escape"):
            plt.close(fig)

    fig.canvas.mpl_connect("key_press_event", on_key)
    
    # Draw initial plot
    draw_plot()
    
    # Block and wait for window close
    plt.show(block=True)


def _verify_single_session(session_name: str, out_dir: Path, cfg: dict, save_to_disk: bool, show: bool, print_only: bool):
    try:
        session = _load_session(session_name)
    except FileNotFoundError as e:
        print(f"  ERROR: {e}")
        return

    # Print summary to console and write to disk
    summary = _print_text_summary(session, session_name, cfg)
    txt_path = out_dir / f"session_{session_name}_VERIFY_summary.txt"
    try:
        txt_path.write_text(summary)
        print(f"  → Saved report to: {txt_path}")
    except Exception as exc:
        print(f"  WARNING: Could not write summary to disk: {exc}")

    if not print_only:
        # 1. Save plots to disk if requested
        if save_to_disk:
            print(f"  Saving diagnostic plots for {session_name} to disk...")
            for builder, (suffix, _title, _w, _h) in zip(_BUILDERS, FIG_SPECS):
                fig = builder(session, session_name, cfg)
                out_path = out_dir / f"session_{session_name}_VERIFY_{suffix}.png"
                try:
                    fig.savefig(out_path, dpi=200, bbox_inches="tight",
                                facecolor="white", edgecolor="none")
                    print(f"    → {out_path}")
                except Exception as exc:
                    print(f"    ERROR saving {suffix}: {exc}")
                finally:
                    plt.close(fig)

        # 2. Show interactive GUI if requested
        if show:
            _show_interactive_viewer(session, session_name, cfg)


def run_verification(session_filter: str | None = None,
                      output_dir: str | Path | None = None,
                      show: bool = False,
                      print_only: bool = False,
                      save_to_disk: bool = True) -> int:
    """Programmatic entry point — usable from wizard.py.

    Returns the number of sessions verified (0 = nothing found / error).
    """
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

    # ── choose backend ──
    if show and not print_only:
        # Use interactive backend so plt.show() works natively
        try:
            matplotlib.use("TkAgg", force=True)
        except Exception:
            pass  # fall back to whatever is available
    else:
        matplotlib.use("Agg", force=True)

    # ── interactive session selection menu ──
    # If the user requested show/interactive view, but did not filter a single session,
    # and we have multiple sessions, show an interactive terminal menu.
    if show and not session_filter and len(all_sessions) > 1:
        while True:
            print("\n" + "═"*60)
            print("  Sequence Verification & Diagnostic Plot Menu".center(60))
            print("═"*60)
            print("  Discovered sessions:")
            for idx, s in enumerate(all_sessions, 1):
                print(f"    {idx}. {s}")
            print("\n  Options:")
            print("    [a] Verify all sessions (saves PNGs & summary.txt to disk)")
            print("    [q] Quit verification and return to main setup menu")
            print("─"*60)
            
            try:
                choice = input("  Select a session or option: ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                print()
                return 0
                
            if choice == 'q':
                return 0
            elif choice == 'a':
                print("\n  Verifying all sessions and saving to disk...")
                for s in all_sessions:
                    _verify_single_session(s, out_dir, cfg, save_to_disk=save_to_disk, show=False, print_only=print_only)
                print("\n  ✓ All sessions verified and saved to disk.")
                return len(all_sessions)
            elif choice.isdigit() and 1 <= int(choice) <= len(all_sessions):
                selected_session = all_sessions[int(choice) - 1]
                _verify_single_session(selected_session, out_dir, cfg, save_to_disk=save_to_disk, show=True, print_only=print_only)
            else:
                print("  Invalid choice, please select a number or option.")
    else:
        # Standard sequential path (e.g. running from command line with filter or non-interactive)
        count = 0
        for session_name in sessions_to_verify:
            print(f"\n  Verifying: {session_name} …")
            _verify_single_session(session_name, out_dir, cfg, save_to_disk=save_to_disk, show=show, print_only=print_only)
            count += 1
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
