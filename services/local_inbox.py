import os
import shutil
from typing import List
from models.voice2action import FileRef

def list_local_inbox(folder: str) -> List[FileRef]:
    os.makedirs(folder, exist_ok=True)
    files = []
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if os.path.isfile(path) and (name.lower().endswith('.wav') or name.lower().endswith('.mp3')):
            files.append(FileRef(id=name, name=name))
    return files

def move_file_to_local_archive(file_name: str, inbox_folder: str, archive_folder: str):
    os.makedirs(archive_folder, exist_ok=True)
    src = os.path.join(inbox_folder, file_name)
    dst = os.path.join(archive_folder, file_name)
    if os.path.exists(dst):
        os.remove(dst)
    shutil.move(src, dst)
