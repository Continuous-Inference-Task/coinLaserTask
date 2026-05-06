"""
generateCoInSessionCsvFiles - Generates high-level CSV files for the CoIn
(Continuous Inference) Laser task with colour counterbalancing and stability ordering.
"""
import os
from write_exp_csv_file import write_exp_csv_file
from write_exp_csv_file_with_tones import write_exp_csv_file_with_tones


def generate_coin_session_csv_files(seq_version, order_index, task_flag, output_root):
    """
    Generate CoIn session CSV files with counterbalanced orders and colour
    assignments.

    Parameters
    ----------
    seq_version : str
        Version string, e.g. "v4".
    order_index : int
        1-based index (1..4) for counterbalancing.
    task_flag : str
        One of 'practice', 'onlineTrain', 'baseline', 'infusion'.
    output_root : str
        Root output directory.
    """
    # Transforming the order index (1-based)
    stab_orders = [1, 2, 1, 2]
    img_orders = [1, 1, 2, 2]
    stab_order_index = stab_orders[order_index - 1]  # 1-based result
    img_order_index = img_orders[order_index - 1]  # 1-based result

    # 4 different colours, in 2 different assignments
    img_assignment1 = ['radioactive1.png', 'radioactive2.png',
                       'radioactive3.png', 'radioactive4.png']
    img_assignment2 = ['radioactive4.png', 'radioactive3.png',
                       'radioactive2.png', 'radioactive1.png']
    img_lists = [img_assignment1, img_assignment2]

    # Available block files (1-based)
    # blocks = 1:12
    # Corresponding conditions
    stabilities = [1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4]

    # Possible block orders (1-based block indices)
    block_order1 = [1, 3, 2, 4, 6, 8, 5, 7, 9, 10, 11, 12]
    block_order2 = [3, 1, 4, 2, 8, 6, 7, 5, 11, 12, 9, 10]

    stab_order1 = [stabilities[b - 1] for b in block_order1]
    stab_order2 = [stabilities[b - 1] for b in block_order2]

    # Baseline block orders (8 blocks)
    bl_block_order1 = [1, 3, 2, 4, 5, 6, 7, 8]
    bl_block_order2 = [3, 1, 4, 2, 7, 8, 5, 6]
    bl_stab_order1 = [stabilities[b - 1] for b in bl_block_order1]
    bl_stab_order2 = [stabilities[b - 1] for b in bl_block_order2]

    # Condition and block orders
    cond_orders = [stab_order1, stab_order2]
    bl_cond_orders = [bl_stab_order1, bl_stab_order2]
    block_orders = [block_order1, block_order2]
    bl_block_orders = [bl_block_order1, bl_block_order2]

    # Tone conditions for EEG sessions
    tone_conditions = [[1, 3, 2, 3], [3, 3, 2, 1], [1, 2, 3, 3]]
    tone_blocks = [[1, 3, 2, 4], [8, 7, 6, 5], [9, 10, 11, 12]]
    tone_orders = [[1, 2, 3], [2, 3, 1], [3, 1, 2], [2, 1, 3]]

    soi = stab_order_index - 1  # 0-based index for stability order
    ioi = img_order_index - 1    # 0-based index for image assignment

    if task_flag == 'practice':
        cond_list = cond_orders[soi]
        block_list = block_orders[soi]
        image_list = img_lists[ioi]

        session_name = f'practice_{seq_version}'
        root2file = os.path.join(output_root, f'coin_{session_name}_order{order_index}')

        for i_sess in range(1):
            block_idx_start = i_sess * 4
            block_idx_end = block_idx_start + 4
            sess_cond_list = cond_list[block_idx_start:block_idx_end]
            sess_block_list = block_list[block_idx_start:block_idx_end]

            add_file_string = f's{i_sess + 1}_'
            write_exp_csv_file(session_name, sess_cond_list, sess_block_list,
                               image_list, add_file_string, root2file)

    elif task_flag == 'onlineTrain':
        cond_list = cond_orders[soi]
        block_list = block_orders[soi]
        image_list = img_lists[ioi]

        session_name = f'onlineTrain_{seq_version}'
        root2file = os.path.join(output_root, f'coin_{session_name}_order{order_index}')

        for i_sess in range(3):
            block_idx_start = i_sess * 4
            block_idx_end = block_idx_start + 4
            sess_cond_list = cond_list[block_idx_start:block_idx_end]
            sess_block_list = block_list[block_idx_start:block_idx_end]

            add_file_string = f's{i_sess + 1}_'
            write_exp_csv_file(session_name, sess_cond_list, sess_block_list,
                               image_list, add_file_string, root2file)

    elif task_flag == 'baseline':
        cond_list = bl_cond_orders[soi]
        block_list = bl_block_orders[soi]
        image_list = img_lists[ioi]

        session_name = f'baseline_{seq_version}'
        root2file = os.path.join(output_root, f'coin_{session_name}_order{order_index}')

        for i_sess in range(2):
            block_idx_start = i_sess * 4
            block_idx_end = block_idx_start + 4
            sess_cond_list = cond_list[block_idx_start:block_idx_end]
            sess_block_list = block_list[block_idx_start:block_idx_end]

            add_file_string = f's{i_sess + 1}_'

            # Tone sequences
            t_order_idx = tone_orders[soi][i_sess] - 1  # 0-based
            tone_cond_list = tone_conditions[t_order_idx]
            tone_block_list = tone_blocks[t_order_idx]

            write_exp_csv_file_with_tones(session_name, sess_cond_list, sess_block_list,
                                          image_list, tone_cond_list, tone_block_list,
                                          add_file_string, root2file)

    elif task_flag == 'infusion':
        cond_list = cond_orders[soi]
        block_list = block_orders[soi]
        image_list = img_lists[ioi]

        session_name = f'main_{seq_version}'
        root2file = os.path.join(output_root, f'coin_{session_name}_order{order_index}')

        for i_sess in range(3):
            block_idx_start = i_sess * 4
            block_idx_end = block_idx_start + 4
            sess_cond_list = cond_list[block_idx_start:block_idx_end]
            sess_block_list = block_list[block_idx_start:block_idx_end]

            add_file_string = f's{i_sess + 1}_'

            # Tone sequences
            t_order_idx = tone_orders[soi][i_sess] - 1  # 0-based
            tone_cond_list = tone_conditions[t_order_idx]
            tone_block_list = tone_blocks[t_order_idx]

            write_exp_csv_file_with_tones(session_name, sess_cond_list, sess_block_list,
                                          image_list, tone_cond_list, tone_block_list,
                                          add_file_string, root2file)
