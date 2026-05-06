"""
writeExpCsvFileWithTones - Writes an experiment-level session CSV file with
additional tone sequence columns for MMN (mismatch negativity).
"""
import os


def write_exp_csv_file_with_tones(sess_name, cond_list, block_list, image_list,
                                   tone_cond_list, tone_block_list,
                                   add_file_string='', root2file=''):
    """
    Write an experiment CSV file with tone sequence information.

    Parameters
    ----------
    sess_name : str
        Session name.
    cond_list : list of int
        Condition indices (1-based).
    block_list : list of int
        Block file indices (1-based).
    image_list : list of str
        Image filenames per condition.
    tone_cond_list : list of int
        Tone condition indices (1-based).
    tone_block_list : list of int
        Tone block file indices (1-based).
    add_file_string : str
        Additional string for filename.
    root2file : str
        Output directory.
    """
    block_file_name_base = f'{sess_name}_block'
    tone_file_name_base = 'mmn/mmn_v1_block'

    volatility = [0, 0, 1, 1]
    stochasticity = [0, 1, 0, 1]
    tone_vola = [0, 1, 1]
    tone_stocha = [1, 1, 0]

    if root2file and not os.path.exists(root2file):
        os.makedirs(root2file, exist_ok=True)

    file_path = os.path.join(root2file, f'session_{add_file_string}{sess_name}.csv')
    with open(file_path, 'w') as f:
        f.write('blockID,sourceImage,volatility,stochasticity,blockFileName,'
                'toneVolatility,toneStochasticity,toneSeqFileName\n')
        for i_block in range(len(block_list)):
            cond_idx = cond_list[i_block] - 1  # 0-based
            tone_cond_idx = tone_cond_list[i_block] - 1  # 0-based
            f.write(
                f'{i_block + 1},'
                f'{image_list[cond_idx]},'
                f'{volatility[cond_idx]},'
                f'{stochasticity[cond_idx]},'
                f'{block_file_name_base}{block_list[i_block]}.csv,'
                f'{tone_vola[tone_cond_idx]},'
                f'{tone_stocha[tone_cond_idx]},'
                f'{tone_file_name_base}{tone_block_list[i_block]}.csv\n'
            )
