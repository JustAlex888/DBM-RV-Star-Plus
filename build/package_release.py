"""Package the native build and the single matching data pack."""
from pathlib import Path
import hashlib,json,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1]
PREFIX='DBM-RV-Star-Plus-0.1.17-TEST-PATCHER-20261107-01'
def main():
 out=ROOT/'release';out.mkdir(exist_ok=True);pkg=out/'package/DBM-RV-Patcher'
 shutil.copytree(ROOT/'dist/DBM-RV-Patcher',pkg,dirs_exist_ok=True)
 shutil.copytree(ROOT/'licenses',pkg/'Licenses',dirs_exist_ok=True)
 shutil.copytree(ROOT/'UpdatePacks',pkg/'UpdatePacks',dirs_exist_ok=True)
 assert len(list((pkg/'UpdatePacks').glob('*.zip')))==1
 shutil.copyfile(ROOT/'THIRD_PARTY_NOTICES.md',pkg/'Licenses/THIRD_PARTY_NOTICES.md')
 ru='''DBM RV*+ 0.1.17 TEST / Установщик 0.2.11 / PATCHER-20261107-01
Распакуйте весь архив. Запустите DBM-RV-Patcher.exe.
Закройте WoW перед применением. Укажите корневую папку игры.
Обновление: точные установленные 0.1.14, 0.1.15, 0.1.16 или PRIVATE-TEST005.
Первая установка: выберите три оригинальных ZIP по ссылкам установщика.
Нажмите «Проверить», изучите результат, затем «Применить».
Настройки WTF и независимая диагностика сохраняются. Перед заменой установщик создаёт внутреннюю резервную копию.
Это предварительный выпуск: новые normal-тайминги требуют игрового прогона.
https://github.com/JustAlex888/DBM-RV-Star-Plus
'''
 en='''DBM RV*+ 0.1.17 TEST / Installer 0.2.11 / PATCHER-20261107-01
Extract the complete archive. Close WoW and run DBM-RV-Patcher.exe.
Select your WoW directory. Choose Update for an exact supported installed release,
or First installation and select all three original ZIPs using the supplied links.
Run Check, review the result, then Apply. WTF and independent diagnostics are preserved.
This prerelease contains new normal timings that still require a game test.
https://github.com/JustAlex888/DBM-RV-Star-Plus
'''
 (pkg/'README_RU.txt').write_text(ru,encoding='utf8');(pkg/'README_EN.txt').write_text(en,encoding='utf8')
 install=out/(PREFIX+'-Windows-x64-INSTALL.zip')
 with zipfile.ZipFile(install,'w',zipfile.ZIP_DEFLATED,compresslevel=9)as z:
  for p in sorted(pkg.rglob('*')):
   if p.is_file():z.write(p,'DBM-RV-Patcher/'+p.relative_to(pkg).as_posix())
 source=out/(PREFIX+'-SOURCE.zip')
 with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED,compresslevel=9)as z:
  for p in sorted(ROOT.rglob('*')):
   rel=p.relative_to(ROOT)
   if not p.is_file()or set(rel.parts)&{'dist','release','work','reports','__pycache__','.git'}or p.suffix in ('.pyc','.spec'):continue
   z.write(p,rel.as_posix())
 manifest={p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size}for p in [install,source]}
 (out/'SHA256.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
 for p in [install,source]:
  with zipfile.ZipFile(p)as z:assert z.testzip()is None
 print(json.dumps(manifest))
if __name__=='__main__':main()
