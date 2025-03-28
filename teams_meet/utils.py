import tarfile
import logging
import os

def create_tar_archive(json_file, opus_file, output_file):
    try:
        full_path = os.path.join(os.getcwd(), f'{output_file}.tar')

        with tarfile.open(full_path, 'w') as tar:
            if os.path.exists(json_file):
                tar.add(json_file, arcname=os.path.basename(json_file))
            else:
                logging.warning(f"File not found: {json_file} - Skipping it.")

            if os.path.exists(opus_file):
                tar.add(opus_file, arcname=os.path.basename(opus_file))
            else:
                logging.warning(f"File not found: {opus_file} - Skipping it.")
        logging.info(f"Files successfully archived into {full_path}")
        return full_path
    except PermissionError as e:
        logging.error(f"Permission denied: {e.filename}")
    except tarfile.TarError as e:
        logging.error(f"Error creating tar archive: {str(e)}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}")
    return None


def audio_file_path(audio_file):
    return os.path.join(os.getcwd(), audio_file)