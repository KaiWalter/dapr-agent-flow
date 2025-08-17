import os
from services.onedrive import move_file_to_archive

def archive_recording_activity(ctx, input: dict) -> dict:
    """
    Activity to move a processed recording from the inbox to the archive folder on OneDrive.
    Expects input dict with keys: 'file_id', 'file_name', 'inbox_folder', 'archive_folder' (optional).
    """
    file_id = input['file_id']
    file_name = input.get('file_name')
    inbox_folder = input.get('inbox_folder')
    archive_folder = input.get('archive_folder') or os.getenv('ONEDRIVE_VOICE_ARCHIVE')
    if not archive_folder:
        raise ValueError("ONEDRIVE_VOICE_ARCHIVE environment variable not set and no archive_folder provided.")
    move_file_to_archive(file_id=file_id, file_name=file_name, inbox_folder=inbox_folder, archive_folder=archive_folder)
    return {'status': 'archived', 'file_id': file_id, 'archive_folder': archive_folder}
