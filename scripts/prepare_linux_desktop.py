"""
Файл: /scripts/prepare_linux_desktop.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Исходники системного помощника как данные: сборка Flet может
          оставить лишь pyc, несовместимые с системным Python другого выпуска.
"""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HELPERS=('linux_desktop_bridge','linux_accessibility','wayland_screen')

def prepare():
    target=ROOT/'App/assets/linux_desktop';target.mkdir(parents=True,exist_ok=True)
    for name in HELPERS:
        (target/(name+'.py.source')).write_bytes((ROOT/'App/services'/(name+'.py')).read_bytes())

if __name__=='__main__':prepare()
