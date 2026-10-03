"""Workspace library: owned copies of files, folders and written notes."""
import hashlib
import os
from pathlib import Path
from . import workspaces
from .attachments import TEXT_EXTENSIONS, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, build_attachment_message_parts
from .material_store import store_material

SUPPORTED = TEXT_EXTENSIONS | IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | {'.pdf', '.docx'}
EXCLUDED = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'target', 'build'}


def material_id(material):
    return hashlib.sha256(material['path'].encode()).hexdigest()[:16]


def entries(workspace_id):
    item = next((item for item in workspaces.list_workspaces() if item['id'] == workspace_id), None)
    if item is None:
        raise ValueError('Пространство не найдено')
    result = []
    for material in item.get('materials', []):
        path = Path(material['path'])
        result.append({**material, 'id': material_id(material), 'size': path.stat().st_size if path.exists() else 0,
                       'available': path.exists(), 'enabled': material.get('enabled', True),
                       'type': material.get('type', path.suffix.lstrip('.').upper() or 'Файл')})
    return result


def import_folder(folder):
    root = Path(folder).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Укажите папку')
    materials, errors = [], []
    for base, directories, names in os.walk(root, followlinks=False):
        directories[:] = sorted(name for name in directories if name not in EXCLUDED and not name.startswith('.')
                                and not (Path(base) / name).is_symlink())
        for name in sorted(names):
            source = Path(base) / name
            if name.startswith('.') or source.is_symlink() or source.suffix.lower() not in SUPPORTED:
                continue
            relative = str(source.relative_to(root))
            try:
                path = store_material(name, path=str(source))
                materials.append({'name': relative, 'path': path, 'source': str(root), 'enabled': True})
            except Exception as exc:
                errors.append(f'{relative}: {exc}')
    if not materials and not errors:
        raise ValueError('В папке нет поддерживаемых документов, изображений или кода')
    return materials, errors


def read_entry(entry):
    if not entry['available']:
        raise ValueError('Локальная копия файла недоступна')
    text, images = build_attachment_message_parts([(entry['name'], entry['path'])])
    return '\n\n'.join(text), images


def add_note(title, content):
    if not title.strip() or not content.strip():
        raise ValueError('Введите название и текст заметки')
    name = title.strip() + '.md'
    return {'name': name, 'path': store_material(name, data=content.encode('utf-8')), 'type': 'Заметка', 'enabled': True}


def append_materials(workspace_id, materials):
    item = next((item for item in workspaces.list_workspaces() if item['id'] == workspace_id), None)
    if not item or workspace_id == workspaces.DEFAULT:
        raise ValueError('Выберите рабочее пространство')
    existing = [dict(m) for m in item.get('materials', [])]
    for material in materials:
        if not any(m['path'] == material['path'] and m['name'] == material['name'] for m in existing):
            existing.append(dict(material))
    workspaces.update_workspace(workspace_id, item['name'], item.get('instructions', ''), existing)


def update_note(workspace_id, identifier, title, content):
    item = next((i for i in workspaces.list_workspaces() if i['id'] == workspace_id), None)
    if not item:
        raise ValueError('Пространство не найдено')
    materials = [dict(m) for m in item.get('materials', [])]
    index = next((i for i, m in enumerate(materials) if material_id(m) == identifier and m.get('type') == 'Заметка'), None)
    if index is None:
        raise ValueError('Заметка не найдена')
    materials[index] = {**materials[index], **add_note(title, content), 'enabled': materials[index].get('enabled', True)}
    workspaces.update_workspace(workspace_id, item['name'], item.get('instructions', ''), materials)
