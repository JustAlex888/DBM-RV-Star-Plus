# Authors, dependencies and licenses

DBM RV*+ 0.1.14 TEST uses the DBM-RV Patcher 0.2.5 Modular TEST installer.
This repository contains the patcher implementation, project transformation rules,
the bundled Update Pack, documentation and screenshots. Donor ZIP archives and
the complete combined gameplay addon tree are not distributed here.

## Original gameplay sources

- Aleksart163 DBM-RV-LEG: `e97f138de7d3ba846e8a2ee36a35730831e04e27`.
- DeadlyBossMods DBM-Dungeons: `2dbfa75c48d654044b597a233c378f1af00d2b62`.
- DeadlyBossMods historical source: `8ac1ee4fe4ad54c7de126a39109cf324fd8109ed`.

Users download these separately using the installer's pinned links. Original
copyright and attribution in locally reconstructed files are retained. No
upstream license is replaced by this project. Aleksart163's permission for his
own contribution is documented at
https://github.com/Aleksart163/DBM-RV-LEG/issues/62#issuecomment-6072498965.

## Installer dependencies

The Windows distribution includes CPython, PyInstaller, CustomTkinter, darkdetect,
packaging, Pillow, NumPy and their bundled dependencies, Tcl/Tk, OpenSSL, libffi,
Roboto fonts and Windows runtime components. Their applicable license texts and
notices are retained in the distribution and under `licenses/` in this repository.
See `licenses/BUNDLED_COMPONENTS.md` and the component license files.
These third-party components are not claimed as original project code.

## Audio

The Update Pack contains 21 approved audio files with their applicable CC0,
CC BY 3.0 and MIT licenses and attribution. Their per-file credits and license
documents are retained inside `data/APPROVED_AUDIO.zip` in the Update Pack and
installed with the corresponding sound addon. A package-level MIT license is
not presented as relicensing all included media.
