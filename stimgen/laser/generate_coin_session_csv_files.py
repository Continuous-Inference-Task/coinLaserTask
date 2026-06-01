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


def _build_counterbalanced_orders(design, block_sequence, n_vol, n_noise):
    """Build condition and block file orderings for two counterbalance variants.

    Order 0 (stable-first): blocks in generation order.
    Order 1 (volatile-first): blocks with volatility dimension reversed.

    Returns (cond_orders, block_orders) — each is a list of two lists.
    """
    n_types = n_vol * n_noise
    n_blocks = len(block_sequence)

    # Order 0: blocks as generated (design order)
    cond_order0 = list(block_sequence)

    # Simple block file numbers: 1, 2, 3, ... (they were generated sequentially)
    block_order0 = list(range(1, n_blocks + 1))

    # Order 1: reverse the volatility dimension within each group of n_types
    cond_order1 = []
    for group_start in range(0, n_blocks, n_types):
        group = list(block_sequence[group_start:group_start + n_types])
        half = n_types // n_vol
        reordered = []
        for vol_idx in reversed(range(n_vol)):
            start = vol_idx * n_noise
            reordered.extend(group[start:start + n_noise])
        cond_order1.extend(reordered)

    # Block file order 1: reorder the file indices the same way
    reordered_files = []
    for group_start in range(0, n_blocks, n_types):
        group_files = list(range(group_start + 1, group_start + n_types + 1))
        reordered_group = []
        for vol_idx in reversed(range(n_vol)):
            start = vol_idx * n_noise
            reordered_group.extend(group_files[start:start + n_noise])
        reordered_files.extend(reordered_group)
    block_order1 = reordered_files

    cond_orders = [cond_order0, cond_order1]
    block_orders = [block_order0, block_order1]
    return cond_orders, block_orders


def generate_coin_session_csv_files(
    order_index, task_flag, output_root,
    design, block_sequence, n_sessions, blocks_per_session,
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
    vol_labels, noise_labels, n_vol, n_noise = _derive_dimensions(design)
    n_types = n_vol * n_noise
    n_blocks = len(block_sequence)

    # ── Counterbalance orders ──
    stab_orders = [0, 1, 0, 1]
    img_orders = [0, 0, 1, 1]
    soi = stab_orders[order_index - 1]
    ioi = img_orders[order_index - 1]

    cond_orders, block_orders = _build_counterbalanced_orders(
        design, block_sequence, n_vol, n_noise
    )

    # ── Image assignments (2 variants: forward and reversed) ──
    all_images = [
        'radioactive1.png', 'radioactive2.png',
        'radioactive3.png', 'radioactive4.png',
    ]
    img_forward = all_images[:n_types]
    img_reversed = list(reversed(all_images[:n_types]))
    img_lists = [img_forward, img_reversed]

    cond_list = cond_orders[soi]
    block_list = block_orders[soi]
    image_list = img_lists[ioi]

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
