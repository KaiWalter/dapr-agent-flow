import os
from services.onedrive import move_file_to_archive
from services.local_inbox import move_file_to_local_archive

def archive_recording_onedrive_activity(ctx, input: dict) -> dict:
    """
    Archive implementation for OneDrive.
    Expects: { 'file_id': str, 'file_name': str|None, 'inbox_folder': str|None, 'archive_folder': str|None }
    """
    file_id = input['file_id']
    file_name = input.get('file_name')
    inbox_folder = input.get('inbox_folder')
    archive_folder = input.get('archive_folder')
    if not archive_folder:
        raise ValueError("archive_recording_onedrive_activity requires 'archive_folder' in input.")
    if not inbox_folder:
        raise ValueError("archive_recording_onedrive_activity requires 'inbox_folder' in input.")
    move_file_to_archive(file_id=file_id, file_name=file_name, inbox_folder=inbox_folder, archive_folder=archive_folder)
    return {'status': 'archived', 'file_id': file_id, 'archive_folder': archive_folder}


def archive_recording_local_activity(ctx, input: dict) -> dict:
    """
    Archive implementation for local filesystem.
    Expects: { 'file_id': str, 'file_name': str|None, 'inbox_folder': str|None, 'archive_folder': str|None }
    """
    file_id = input['file_id']
    file_name = input.get('file_name')
    inbox_folder = input.get('inbox_folder')
    archive_folder = input.get('archive_folder')
    if not archive_folder:
        raise ValueError("archive_recording_local_activity requires 'archive_folder' in input.")
    if not inbox_folder:
        raise ValueError("archive_recording_local_activity requires 'inbox_folder' in input.")
    os.makedirs(archive_folder, exist_ok=True)
    move_file_to_local_archive(file_name=file_name or file_id, inbox_folder=inbox_folder, archive_folder=archive_folder)
    return {'status': 'archived', 'file_id': file_id, 'archive_folder': archive_folder}
