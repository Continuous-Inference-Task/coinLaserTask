"""
writeExpCsvFile - Writes an experiment-level session CSV file listing block
metadata for PsychoPy/Pavlovia.
"""
import os


def write_exp_csv_file(sess_name, cond_list, block_list, image_list,
                       add_file_string='', root2file=''):
    """
    Write an experiment CSV file listing blocks, conditions, and images.

    Parameters
    ----------
    sess_name : str
        Session name (used in filenames).
    cond_list : list of int
        Condition indices (1-based) for each block.
    block_list : list of int
        Block file indices (1-based) for each block.
    image_list : list of str
        Image filenames for each condition.
    add_file_string : str
        Additional string to prepend to the session filename.
    root2file : str
        Output directory.
    """
    block_file_name_base = f'{sess_name}_block'
    volatility = [0, 0, 1, 1]
    stochasticity = [0, 1, 0, 1]

    if root2file and not os.path.exists(root2file):
        os.makedirs(root2file, exist_ok=True)

    file_path = os.path.join(root2file, f'session_{add_file_string}{sess_name}.csv')
    with open(file_path, 'w') as f:
        f.write('blockID,sourceImage,volatility,stochasticity,blockFileName\n')
        for i_block in range(len(block_list)):
            cond_idx = cond_list[i_block] - 1  # 0-based
            f.write(
                f'{i_block + 1},'
                f'{image_list[cond_idx]},'
                f'{volatility[cond_idx]},'
                f'{stochasticity[cond_idx]},'
                f'{block_file_name_base}{block_list[i_block]}.csv\n'
            )
