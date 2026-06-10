"""
writeExpCsvFile - Writes an experiment-level session CSV file listing block
metadata for PsychoPy/Pavlovia.
"""
import os


def write_exp_csv_file(
    sess_name, cond_indices, block_files, image_list,
    design, add_file_string='', root2file='',
):
    """Write an experiment CSV file listing blocks, conditions, and images.

    Parameters
    ----------
    sess_name : str
        Session name (used in filenames).
    cond_indices : list of int
        1-based block type indices for each row in this session.
    block_files : list of int
        1-based raw block file indices to load.
    image_list : list of str
        Image filenames, indexed by (vol_idx * n_noise + noise_idx).
    design : dict
        From design_vola_stocha() — keys 'blockTypes', 'blocks'.
    add_file_string : str
        Additional string to prepend to the session filename.
    root2file : str
        Output directory.
    """
    block_file_name_base = f'{sess_name}_block'
    block_names = design['blockTypes']

    # Extract unique volatility and noise labels from block type names ("vol+noise")
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
        n_vol = len(block_names)
        vol_labels = [f'vol{i}' for i in range(n_vol)]
        noise_labels = ['fixed']
    if not noise_labels:
        noise_labels = ['fixed']

    n_noise = len(noise_labels)

    if root2file and not os.path.exists(root2file):
        os.makedirs(root2file, exist_ok=True)

    file_path = os.path.join(root2file, f'session_{add_file_string}{sess_name}.csv')
    with open(file_path, 'w') as f:
        f.write('blockID,sourceImage,volatility,stochasticity,blockFileName\n')
        for i_block in range(len(cond_indices)):
            cond_idx = cond_indices[i_block] - 1  # 0-based
            bt_name = block_names[cond_idx] if cond_idx < len(block_names) else block_names[-1]
            if '+' in bt_name:
                v, n = bt_name.split('+', 1)
            else:
                v, n = bt_name, noise_labels[0] if noise_labels else ''
            vol_idx = vol_labels.index(v) if v in vol_labels else 0
            noise_idx = noise_labels.index(n) if n in noise_labels else 0
            img_idx = cond_idx % len(image_list)  # wrap if more types than images
            f.write(
                f'{i_block + 1},'
                f'{image_list[img_idx]},'
                f'{vol_idx},'
                f'{noise_idx},'
                f'{block_file_name_base}{block_files[i_block]}.csv\n'
            )
