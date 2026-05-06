"""
generateSessionCsvFiles - Generates high-level CSV files for the CoIn Laser
task for PsychoPy/Pavlovia: training and main task sequences.
"""
from write_exp_csv_file import write_exp_csv_file
from write_exp_csv_file_with_tones import write_exp_csv_file_with_tones


def generate_session_csv_files(seq_version, order_index, task_flag):
    """
    Generate session CSV files with counterbalanced block orders.

    Parameters
    ----------
    seq_version : str
        Version string, e.g. "CBv3".
    order_index : int
        1-based index (1..3) for counterbalancing order.
    task_flag : str
        One of 'online', 'onlineTrain', 'EEG', 'baseline'.
    """
    # Available lists
    image_list = ['radioactive1.png', 'radioactive2.png',
                  'radioactive3.png', 'radioactive4.png']

    # 3 mini-sessions with different condition orders
    # conditions refers to volatility & stochasticity
    conditions = [[1, 2, 3, 4], [3, 4, 1, 2], [1, 3, 2, 4]]
    blocks = [conditions[0][:],
              [c + 4 for c in conditions[1]],
              [c + 8 for c in conditions[2]]]

    # Baseline sessions (only 2 mini-sessions)
    bl_conditions = [[1, 2, 3, 4], [3, 4, 1, 2]]
    bl_blocks = [bl_conditions[0][:],
                 [c + 4 for c in bl_conditions[1]]]

    # Possible orders (1-based index -> 0-based)
    orders = [[1, 3, 2], [3, 1, 2], [2, 3, 1]]  # 1-based
    bl_orders = [[1, 2], [2, 1]]  # 1-based

    tone_conditions = [[1, 3, 2, 3], [3, 3, 2, 1], [1, 2, 3, 3]]
    tone_blocks = [[1, 3, 2, 4], [8, 7, 6, 5], [9, 10, 11, 11]]
    tone_orders = [[1, 2, 3], [2, 3, 1], [3, 1, 2]]  # 1-based

    oi = order_index - 1  # convert to 0-based

    if task_flag == 'online':
        # One main task sequence with 12 blocks
        order = orders[oi]
        cond_list = []
        block_list = []
        for idx in order:
            cond_list.extend(conditions[idx - 1])
            block_list.extend(blocks[idx - 1])

        main_sess_name = f'main_{seq_version}'
        write_exp_csv_file(main_sess_name, cond_list, block_list, image_list)

    elif task_flag == 'onlineTrain':
        # 3 sessions, 4 blocks each
        order = orders[oi]
        for i_sess in range(3):
            sess_idx = order[i_sess] - 1  # 0-based
            cond_list = conditions[sess_idx]
            block_list = blocks[sess_idx]

            online_sess_name = f'onlineTrain_{seq_version}'
            add_file_string = f's{i_sess + 1}_'
            write_exp_csv_file(online_sess_name, cond_list, block_list,
                               image_list, add_file_string)

    elif task_flag == 'EEG':
        # 3 sessions with tones
        order = orders[oi]
        t_order = tone_orders[oi]
        for i_sess in range(3):
            sess_idx = order[i_sess] - 1
            cond_list = conditions[sess_idx]
            block_list = blocks[sess_idx]

            online_sess_name = f'main_{seq_version}'
            add_file_string = f's{i_sess + 1}_'

            t_sess_idx = t_order[i_sess] - 1
            tone_cond_list = tone_conditions[t_sess_idx]
            tone_block_list = tone_blocks[t_sess_idx]
            write_exp_csv_file_with_tones(online_sess_name, cond_list, block_list,
                                          image_list, tone_cond_list, tone_block_list,
                                          add_file_string)

    elif task_flag == 'baseline':
        # 2 sessions with tones
        bl_order = bl_orders[oi]
        t_order = tone_orders[oi]
        for i_sess in range(2):
            sess_idx = bl_order[i_sess] - 1
            cond_list = bl_conditions[sess_idx]
            block_list = bl_blocks[sess_idx]

            online_sess_name = f'baseline_{seq_version}'
            add_file_string = f's{i_sess + 1}_'

            t_sess_idx = t_order[i_sess] - 1
            tone_cond_list = tone_conditions[t_sess_idx]
            tone_block_list = tone_blocks[t_sess_idx]
            write_exp_csv_file_with_tones(online_sess_name, cond_list, block_list,
                                          image_list, tone_cond_list, tone_block_list,
                                          add_file_string)

    # Generate training sequence for online and EEG
    if task_flag in ('online', 'EEG'):
        train_cond_list = conditions[0]
        train_block_list = train_cond_list[:]
        train_sess_name = f'training_{task_flag}_{seq_version}'
        write_exp_csv_file(train_sess_name, train_cond_list, train_block_list,
                           image_list)
