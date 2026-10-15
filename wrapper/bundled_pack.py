"""Resolve a data-only Update Pack beside the EXE, never from Windows cwd."""
import stat
import sys
from pathlib import Path
from engine.pack_v2 import VerifiedPack
from engine import dbm_rv_installer as legacy

PUBLIC_INPUT_IDS = frozenset(('S01', 'S08', 'S18'))

def application_directory():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]

def validate_install_pack(path):
    legacy.safe_chain(Path(path).absolute())
    pack = VerifiedPack(Path(path))
    extra = sorted(set(pack.sources) - PUBLIC_INPUT_IDS)
    if extra:
        raise ValueError('PACK_UNSUPPORTED_SOURCE_DEPENDENCY: ' + ', '.join(extra))
    return pack

def discover_bundled_pack(app_dir=None):
    folder = Path(app_dir) / 'UpdatePacks' if app_dir is not None else application_directory() / 'UpdatePacks'
    try:
        if not folder.is_dir():
            return {'state': 'MISSING', 'message': 'Неполный установочный комплект: отсутствует папка UpdatePacks с нашим пакетом обновления.'}
        legacy.safe_chain(folder.absolute())
        candidates = []
        for path in sorted(folder.iterdir()):
            if path.suffix.casefold() != '.zip':
                continue
            obj = path.lstat()
            if not stat.S_ISREG(obj.st_mode) or getattr(obj, 'st_file_attributes', 0) & 0x400:
                raise ValueError('BUNDLED_PACK_UNSAFE_OBJECT')
            candidates.append(path)
        if not candidates:
            return {'state': 'MISSING', 'message': 'Неполный установочный комплект: наш Update Pack не найден в UpdatePacks.'}
        if len(candidates) != 1:
            return {'state': 'AMBIGUOUS', 'message': 'В комплекте несколько пакетов. Выберите нужный пакет из UpdatePacks; версия не выбирается по номеру автоматически.', 'candidates': [str(p) for p in candidates]}
        pack = validate_install_pack(candidates[0])
        return {'state': 'READY', 'path': str(candidates[0].absolute()), 'identity': pack.identity(), 'message': 'Пакет обновления включён в комплект'}
    except Exception as exc:
        return {'state': 'INVALID', 'message': 'Пакет комплекта непригоден: ' + str(exc)}
