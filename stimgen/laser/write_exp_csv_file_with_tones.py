"""
writeExpCsvFileWithTones - Writes an experiment-level session CSV file with
additional tone sequence columns for MMN (mismatch negativity).
"""
import os


def write_exp_csv_file_with_tones(
    sess_name, cond_indices, block_files, image_list,
    design, tone_vol_indices, tone_noise_indices, tone_block_files,
    add_file_string='', root2file='',
):
    """Write an experiment CSV file with tone sequence information.

    Parameters
    ----------
    sess_name : str
        Session name.
    cond_indices : list of int
        1-based block type indices for each row.
    block_files : list of int
        1-based raw block file indices to load.
    image_list : list of str
        Image filenames, indexed by (vol_idx * n_noise + noise_idx).
    design : dict
        From design_vola_stocha().
    tone_vol_indices : list of int
        0-based volatility indices for tone conditions per block.
    tone_noise_indices : list of int
        0-based noise (stochasticity) indices for tone conditions per block.
    tone_block_files : list of int
        1-based MMN block file indices per block.
    add_file_string : str
        Additional string for filename.
    root2file : str
        Output directory.
    """
    block_file_name_base = f'{sess_name}_block'
    tone_file_name_base = 'mmn/mmn_v1_block'

    # Derive dimension counts from design
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

    if not vol_labels or not noise_labels:
        n_vol = len(design['blocks']) // len(block_names) if block_names else 0
        vol_labels = [f'vol{i}' for i in range(max(n_vol, 1))]
        noise_labels = [f'noise{i}' for i in range(len(block_names) // max(n_vol, 1))]

    n_noise = len(noise_labels)

    if root2file and not os.path.exists(root2file):
        os.makedirs(root2file, exist_ok=True)

    file_path = os.path.join(root2file, f'session_{add_file_string}{sess_name}.csv')
    with open(file_path, 'w') as f:
        f.write('blockID,sourceImage,volatility,stochasticity,blockFileName,'
                'toneVolatility,toneStochasticity,toneSeqFileName\n')
        for i_block in range(len(cond_indices)):
            cond_idx = cond_indices[i_block] - 1  # 0-based
            vol_idx = cond_idx // n_noise
            noise_idx = cond_idx % n_noise
            img_idx = cond_idx % len(image_list)
            f.write(
                f'{i_block + 1},'
                f'{image_list[img_idx]},'
                f'{vol_idx},'
                f'{noise_idx},'
                f'{block_file_name_base}{block_files[i_block]}.csv,'
                f'{tone_vol_indices[i_block]},'
                f'{tone_noise_indices[i_block]},'
                f'{tone_file_name_base}{tone_block_files[i_block]}.csv\n'
            )
