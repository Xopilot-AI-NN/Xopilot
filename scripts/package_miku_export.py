"""
Файл: /scripts/package_miku_export.py
Разработчик: DenBroLiik
Версия: 2.0.10
Описание: Комплект исходников экспортёра Miku для отдельной версии Python.
"""
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def package():
    source=ROOT/'App/services/_rvc_export'
    target=ROOT/'App/assets/voice/miku-export-source.zip'
    target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.iterdir()):
            if path.is_file() and (path.suffix=='.py' or path.name.startswith('LICENSE') or path.name=='PROVENANCE.md'):
                item=zipfile.ZipInfo(path.name)
                item.compress_type=zipfile.ZIP_DEFLATED
                archive.writestr(item,path.read_bytes())
    return target


if __name__=='__main__':print(package())
