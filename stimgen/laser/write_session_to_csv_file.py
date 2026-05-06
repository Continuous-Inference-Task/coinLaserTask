"""
writeSessionToCsvFile - Writes out one csv file per block within a session
to be used in the psychopy laser experiment.
"""
import os
import numpy as np


def write_session_to_csv_file(session, sess_name, sequence_root=''):
    """
    Write one CSV file per block in the session.

    Parameters
    ----------
    session : dict
        Session dict with 'nBlocks' and 'blocks' list.
    sess_name : str
        Base name for the session files.
    sequence_root : str
        Output directory. Default: current directory.
    """
    if sequence_root and not os.path.exists(sequence_root):
        os.makedirs(sequence_root, exist_ok=True)

    for i_block in range(session['nBlocks']):
        stim = session['blocks'][i_block]['stim']
        mean_deg = stim['meanValueVectorDeg']
        obs_deg = stim['valueVectorDeg']
        std_deg = stim['stdValueVectorDeg']

        file_path = os.path.join(sequence_root, f'{sess_name}_block{i_block + 1}.csv')
        with open(file_path, 'w') as f:
            f.write('true_pos,obs_pos,true_var\n')
            for j in range(len(mean_deg)):
                f.write(f'{int(mean_deg[j])},{int(obs_deg[j])},{int(std_deg[j])}\n')
