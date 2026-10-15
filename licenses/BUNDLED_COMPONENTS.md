# Distributed components and notices — R12 / packaging PUB1

The installer executable is unchanged:0.2.5-modular-TEST / PATCHER-20261015-03.
PUB1 supplements distribution documentation only; it does not modify runtime,
source recipes, donor inputs, the update pack, or installed game files.

| Component | Redistribution basis / accompanying notice |
|---|---|
| Project installer/recipe/compatibility code | Project development history; changes separately documented. No upstream is relicensed. |
| Aleksart163 own DBM-RV contributions | https://github.com/Aleksart163/DBM-RV-LEG/issues/62#issuecomment-6072498965; original authorship and unofficial continuation status retained. |
| Original DBM gameplay sources | NOT redistributed here. Three pinned original ZIPs are supplied by the user. Locally constructed output retains its authors and notices. |
| CPython3.11.9 and standard library | Python-LICENSE.txt, including PSF/CWI/BeOpen/CNRI, incorporated-software notices and Windows distribution conditions. Python binaries are unmodified. |
| PyInstaller6.16 bootloader and embedded loader | PyInstaller-COPYING.txt; bootloader exception permits distribution of the combined executable. Unmodified bootloader. |
| CustomTkinter5.2.2 / darkdetect0.8.0 | CustomTkinter-MIT.txt / Darkdetect-BSD.txt; included unmodified. |
| Pillow12.3.0 / bundled codec libraries | Pillow-LICENSE.txt, including its incorporated-library notices. |
| NumPy2.3.5 / OpenBLAS / bundled GCC runtime | NumPy-LICENSE.txt and _internal/numpy-2.3.5.dist-info/LICENSE.txt, including runtime exceptions and incorporated-library notices. |
| packaging26.3 | LICENSE, LICENSE.APACHE, LICENSE.BSD. |
| Tcl/Tk8.6 | Tcl-8.6.13-LICENSE.txt and _internal/_tk_data/license.terms; original resource/source notices retained. |
| OpenSSL3.0.13 | OpenSSL-3.0.13-LICENSE.txt (Apache2.0), source https://github.com/openssl/openssl/tree/openssl-3.0.13 . |
| libffi3.4.4 | libffi-3.4.4-LICENSE.txt; copyright and permission notice retained. |
| Roboto fonts | Roboto-Apache-2.0-LICENSE.txt and Roboto-EMBEDDED-NOTICES.txt; original font bytes and embedded notices retained. |
| Microsoft UCRT/VC runtime | Python-LICENSE.txt Windows binary-build conditions; WINDOWS_RUNTIME_TERMS.txt. Windows use only; no Microsoft endorsement. |
|21 approved sound assets | Licenses and attribution are inside the bundled UpdatePack/data/APPROVED_AUDIO.zip and copied by the installer into the game addon.1CC0,18CC-BY3.0,2MIT. The pack's own MIT notice does not relicense all media. |

Required acknowledgements accompany this distribution. Third-party components
are not represented as original project code. This is an unofficial free test
patcher for Legion7.3.5/UWoW, not an official DBM release.
