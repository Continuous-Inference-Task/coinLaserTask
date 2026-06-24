"""
generateCoinSessionCsvFiles - Generates high-level CSV files for the CoIn
(Continuous Inference) Laser task with colour counterbalancing and stability ordering.

Accepts the block design and raw block sequence so that counterbalancing
works for any N×M (volatility × noise) configuration.

MMN tone blocks are assigned 1:1 with laser blocks — each laser block
gets its own pre-generated MMN tone file.
"""
import os
from write_exp_csv_file import write_exp_csv_file
from write_exp_csv_file_with_tones import write_exp_csv_file_with_tones


def _derive_dimensions(design):
    """Extract ordered volatility and noise labels from a block design.

    Returns (vol_labels, noise_labels, n_vol, n_noise).
    """
    block_names = design['blockTypes']
    vol_labels = []
    noise_labels = []
    for name in block_names:
        if '+' in name:
            v, n = name.split('+', 1)
            if v not in vol_labels:
                vol_labels.append(v)
            if n not in noise_labels:
                noise_labels.append(n)
    if not vol_labels:
        n_vol = len(design['blocks'])
        n_noise = 1
        vol_labels = [f'type{i}' for i in range(n_vol)]
        noise_labels = ['fixed']
    return vol_labels, noise_labels, len(vol_labels), len(noise_labels)


def _build_counterbalanced_orders(design, block_sequence):
    """Build condition and block file orderings for two counterbalance variants.

    Order 0 (stable-first): blocks in generation order.
    Order 1 (volatile-first): blocks with volatility dimension reversed.

    Works for any block design, including non-rectangular (_only) designs.

    Returns (cond_orders, block_orders) — each is a list of two lists.
    """
    block_types = design['blockTypes']
    n_types = len(block_types)
    n_blocks = len(block_sequence)

    # Build lookup: type ID -> volatility index
    type_vol_idx = {}
    vol_labels = []
    for i, bt in enumerate(block_types):
        v = bt.split('+', 1)[0] if '+' in bt else bt
        if v not in vol_labels:
            vol_labels.append(v)
        type_vol_idx[i + 1] = vol_labels.index(v)

    # Order 0: blocks as generated (design order)
    cond_order0 = list(block_sequence)
    block_order0 = list(range(1, n_blocks + 1))

    # Order 1: reverse the volatility dimension within each session-sized group
    cond_order1 = []
    block_order1 = []
    for group_start in range(0, n_blocks, n_types):
        group = block_sequence[group_start:group_start + n_types]
        group_files = list(range(group_start + 1, group_start + len(group) + 1))

        # Group by volatility index, preserving intra-group order
        vol_groups = {}
        for t, f in zip(group, group_files):
            v_idx = type_vol_idx[t]
            vol_groups.setdefault(v_idx, []).append((t, f))

        # Reverse volatility order
        for v_idx in reversed(sorted(vol_groups.keys())):
            for t, f in vol_groups[v_idx]:
                cond_order1.append(t)
                block_order1.append(f)

    return [cond_order0, cond_order1], [block_order0, block_order1]


def _get_image_list(task_flag, show_source, n_types, image_order_index):
    """Pick the source-image set for a session, with a forward/reversed variant.

    - ``practice`` always uses the ``radioactive5-8`` images.
    - ``main`` (and other non-practice flags) uses ``radioactive1-4`` when
      *show_source* is True, else the neutral ``not_so_radioactive1-4`` images.

    Returns the image list selected by *image_order_index* (0 = forward, 1 = reversed).
    """
    if task_flag == "practice":
        # Practice always uses the radioactive5-8 images.
        base_images = [
            "radioactive5.png",
            "radioactive6.png",
            "radioactive7.png",
            "radioactive8.png",
        ]
    else:  # main (and other non-practice flags)
        if show_source:
            base_images = [
                "radioactive1.png",
                "radioactive2.png",
                "radioactive3.png",
                "radioactive4.png",
            ]
        else:
            base_images = [
                "not_so_radioactive1.png",
                "not_so_radioactive2.png",
                "not_so_radioactive3.png",
                "not_so_radioactive4.png",
            ]

    img_forward = base_images[:n_types]
    img_reversed = list(reversed(img_forward))
    return [img_forward, img_reversed][image_order_index]


def generate_coin_session_csv_files(
    order_index, task_flag, output_root,
    design, block_sequence, n_sessions, blocks_per_session, show_source=True,
    mmn_filenames=None, tone_vol_list=None, tone_noise_list=None,
):
    """Generate session CSV files with counterbalanced orders and image assignments.

    Parameters
    ----------
    order_index : int
        1-based index (1..4) for counterbalancing.
    task_flag : str
        'practice' or 'main'.
    output_root : str
        Root output directory.
    design : dict
        From design_vola_stocha() — keys 'blockTypes', 'blocks'.
    block_sequence : list of int
        1-based block type indices in generation order.
    n_sessions : int
        Number of session CSVs to split into (each = blocks_per_session blocks).
    blocks_per_session : int
        Number of blocks per session CSV.
    mmn_filenames : list of str or None
        Pre-generated MMN block filenames (one per laser block), e.g.
        ``["mmn/mmn_block1.csv", "mmn/mmn_block2.csv", ...]``.
        Only used when *task_flag* is ``"main"``.
    tone_vol_list : list of int or None
        0-based volatility indices for each MMN block.
    tone_noise_list : list of int or None
        0-based noise (stochasticity) indices for each MMN block.
    """
    n_types = len(design['blockTypes'])
    n_blocks = len(block_sequence)

    # ── Counterbalance orders ──
    stab_orders = [0, 1, 0, 1]
    img_orders = [0, 0, 1, 1]
    soi = stab_orders[order_index - 1]
    ioi = img_orders[order_index - 1]

    cond_orders, block_orders = _build_counterbalanced_orders(
        design, block_sequence
    )

    # ── Image assignments (2 variants: forward and reversed) ──
    # Practice always uses radioactive5-8; main uses radioactive1-4 when
    # show_source is True, else the neutral not_so_radioactive1-4 images.
    image_list = _get_image_list(task_flag, show_source, n_types, ioi)

    cond_list = cond_orders[soi]
    block_list = block_orders[soi]

    session_prefix = f'{task_flag}'
    root2file = os.path.join(output_root, f'coin_{session_prefix}_order{order_index}')

    for i_sess in range(n_sessions):
        start = i_sess * blocks_per_session
        end = min(start + blocks_per_session, n_blocks)
        sess_cond = cond_list[start:end]
        sess_blocks = block_list[start:end]

        add_str = f's{i_sess + 1}_'

        if task_flag == 'main' and mmn_filenames is not None:
            # Apply same counterbalancing reordering to MMN files as laser blocks.
            # sess_blocks contains the reordered laser block indices (e.g. [3,4,1,2]).
            # Index into mmn_filenames (0-based) with the corresponding block index.
            sess_mmn = [mmn_filenames[bidx - 1] for bidx in sess_blocks]
            sess_tone_vol = [tone_vol_list[bidx - 1] for bidx in sess_blocks] if tone_vol_list else [0] * len(sess_mmn)
            sess_tone_noise = [tone_noise_list[bidx - 1] for bidx in sess_blocks] if tone_noise_list else [0] * len(sess_mmn)

            write_exp_csv_file_with_tones(
                session_prefix, sess_cond, sess_blocks, image_list,
                design, sess_tone_vol, sess_tone_noise, sess_mmn,
                add_str, root2file,
            )
        else:
            write_exp_csv_file(
                session_prefix, sess_cond, sess_blocks, image_list,
                design, add_str, root2file,
            )
