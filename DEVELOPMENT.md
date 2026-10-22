# Development

The ready-to-use Windows installation bundle is provided under Releases. The
repository source requires Python; installing Python is not required to run
the released executable.

## Build the installer

Use native Windows x64 with CPython 3.11 x64. From the repository root:

```powershell
python -m pip install -r requirements_development.txt
python -m build.build_windows_x64
```

The builder produces `dist/DBM-RV-Patcher` and checks PE64/asInvoker properties.
Keep the complete generated onedir runtime. Add the repository's `UpdatePacks`
directory beside the executable and include the applicable dependency license
texts and notices when preparing a distribution.

## Update Pack

The external ZIP contains validated data and project transformations. The
installer executes only its bundled recipe implementation; Python from the
Update Pack is not executed. Donors are checked against pinned archive/member
hashes. The package describes the expected output file hashes and tree digest.

Use disposable test directories for installation/rollback tests. Test scripts
under `tests/` document the available checks and their required inputs; they
are not game verification. Never use a live WoW/WTF tree as a test fixture.

The build embeds assets/patcher-legion.ico and includes both approved icon assets under resources/assets for the window icon. Preserve those files when rebuilding.
