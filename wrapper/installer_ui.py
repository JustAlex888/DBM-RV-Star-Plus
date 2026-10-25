"""Two-screen Phase 8 UAT revision. GUI orchestrates the deterministic engine."""
import argparse
import json
import os
import queue
import sys
import threading
import webbrowser
from pathlib import Path
from engine.dbm_rv_modular_installer import PatchEngine, ENGINE_VERSION
from engine.pack_v2 import VerifiedPack
from engine.dbm_rv_phase8_engine import fault_from_name
from engine import dbm_rv_phase8_engine as core
from wrapper import i18n
from wrapper.bundled_pack import discover_bundled_pack, validate_install_pack
from wrapper import windows_access

WRAPPER_VERSION = '0.2.10-modular-TEST'
BUILD_ID = 'PATCHER-20261025-02'
SOURCE_LINKS = (
 ('DBM-RV от Aleksart163', 'Основной DBM-RV. Поддерживаемая ревизия: e97f138.', 'https://github.com/Aleksart163/DBM-RV-LEG', 'https://github.com/Aleksart163/DBM-RV-LEG/archive/e97f138de7d3ba846e8a2ee36a35730831e04e27.zip'),
 ('DBM-Dungeons', 'Дополнительный источник WoD/BfA: Deadly Boss Mods. Ревизия: 2dbfa75.', 'https://github.com/DeadlyBossMods/DBM-Dungeons', 'https://github.com/DeadlyBossMods/DBM-Dungeons/archive/2dbfa75c48d654044b597a233c378f1af00d2b62.zip'),
 ('source_s18_title', 'source_s18_desc', 'https://github.com/DeadlyBossMods/DeadlyBossMods/tree/8ac1ee4fe4ad54c7de126a39109cf324fd8109ed', 'https://github.com/DeadlyBossMods/DeadlyBossMods/archive/8ac1ee4fe4ad54c7de126a39109cf324fd8109ed.zip'),
)

def resource_root():
    return Path(sys._MEIPASS) / 'resources' if getattr(sys, '_MEIPASS', None) else Path(__file__).resolve().parents[1]

def resolve_addons_root(selected):
    if not str(selected).strip():
        raise ValueError('SELECT_WOW_ROOT')
    path = Path(selected).absolute()
    addons = path if path.name.casefold() == 'addons' and path.parent.name.casefold() == 'interface' else path / 'Interface' / 'AddOns'
    if not addons.is_dir():
        raise ValueError('ADDONS_ROOT_NOT_FOUND')
    return addons

def describe_pack(raw):
    if not str(raw).strip():
        raise ValueError('BUNDLE_MISSING')
    return VerifiedPack(Path(raw)).identity()


class CheckedPackEngine(PatchEngine):
    """Carry pack identity across the user's CHECK→APPLY without changing core."""
    def __init__(self, *, expected_pack_sha256=None, **kwargs):
        self.expected_pack_sha256 = expected_pack_sha256
        super().__init__(**kwargs)

    def _validate_inputs(self):
        super()._validate_inputs()
        if self.expected_pack_sha256 is not None and self.bundle.sha256 != self.expected_pack_sha256:
            raise core.BaselineFailure('PACK_CHANGED_SINCE_USER_CHECK')

    def _recheck_preconditions(self):
        super()._recheck_preconditions()
        self.access_probe = windows_access.inspect_access(
            self.target_root, self.existing_roots, self.backup_root if self.before else None)
        if not self.check_only and self.access_probe['status'] == 'DENIED':
            denied = next(c['path'] for c in self.access_probe['checks'] if c['status'] == 'DENIED')
            raise core.UnsafePathFailure('ACCESS_DENIED' if self.access_probe['admin'] else 'ADMIN_REQUIRED', denied)

    def run(self):
        result = super().run()
        probe = getattr(self, 'access_probe', {})
        result.details['access_probe'] = probe
        result.details['requires_admin'] = probe.get('status') == 'DENIED' and not probe.get('admin')
        return result


def run_engine(*, target, source_s01, source_s08, pack_path, check_only,
               test_fault='none', backup_path=None, expected_inventory=None,
               expected_mode=None, progress=None, source_extra=None, expected_pack_sha256=None):
    # Both wrapper/engine are version-independent: no 0.1.7 resources needed.
    addons = resolve_addons_root(target)
    if not str(pack_path).strip():
        bundled = discover_bundled_pack()
        if bundled['state'] != 'READY':
            raise ValueError('BUNDLE_'+bundled['state'])
        pack_path = bundled['path']
    validate_install_pack(pack_path)
    local = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local')))
    paths = {'S01': Path(source_s01)} if str(source_s01).strip() else {}
    if str(source_s08).strip():
        paths['S08'] = Path(source_s08)
    for key, value in (source_extra or {}).items():
        if str(value).strip():
            paths[key] = Path(value)
    result = CheckedPackEngine(target_root=addons, pack_path=Path(pack_path), source_selections=paths,
        progress=progress, backup_path=backup_path, expected_inventory=expected_inventory,
        expected_mode=expected_mode, session_parent=local / 'DBM-RV-Patcher' / 'sessions',
        check_only=check_only, fault=fault_from_name(test_fault), expected_pack_sha256=expected_pack_sha256).run().as_dict()
    result.update(engine_version=ENGINE_VERSION, wrapper_version=WRAPPER_VERSION,
                  build_id=BUILD_ID, selected_addons_root=str(addons))
    core.write_json(Path(result['session_dir']) / 'summary.json', result)
    return result

def exception_result(exc):
    reason = 'ACCESS_DENIED' if isinstance(exc, PermissionError) or getattr(exc, 'winerror', None) == 5 else getattr(exc,'reason',None) or str(exc)
    return {'outcome':'INVALID_SELECTION','reason_code':reason,
            'target_write_count':0,'details':{'failure_detail':getattr(exc,'detail',None) or str(exc)}}

def outcome_message(result, language=None):
    language=language or i18n.detect_language()
    tr=lambda key,**kw:i18n.text(key,language,**kw)
    d=result.get('details',{});outcome=result.get('outcome');mode=d.get('mode');identity=d.get('content_identity') or {}
    lines=[tr({'READY':'ready','SUCCESS':'success','ALREADY_PATCHED':'already','BACKUP_FAILED':'backup_failed','ROLLBACK_FAILED':'rollback_failed'}.get(outcome,'error'))]
    if identity:lines.append(tr('target_identity',version=identity.get('version','?').replace('-TEST',' TEST'),build=identity.get('build_id','?'),files=identity.get('files','?'),roots=identity.get('roots','?')))
    if mode=='FRESH_INSTALL':lines.append(tr('fresh'))
    if mode:lines.extend([tr('mode',mode=tr('mode_'+mode)),tr('found',count=len(d.get('existing_roots',[])))])
    if outcome == 'READY' and d.get('requires_admin'):lines.append(tr('admin_needed'))
    elif outcome == 'READY' and d.get('access_probe',{}).get('status') == 'DENIED':lines.append(tr('ACCESS_DENIED'))
    if d.get('ignored_regular_files'):lines.append(tr('preserved' if d.get('preserved_regular_files_verified') else 'preservation_pending'))
    code=result.get('reason_code')
    if code:lines.extend([i18n.error_text(code,language),tr('technical_code',code=code)])
    if d.get('failure_detail'):lines.append(tr('detail',detail=d['failure_detail']))
    if result.get('rollback_status')=='ROLLBACK_VERIFIED':lines.append(tr('restored'))
    backup=result.get('backup_root') or (d.get('backup_planned_path') if mode!='ALREADY_PATCHED' else None)
    if backup:lines.append(tr('backup_path',path=backup))
    if result.get('session_dir'):lines.append(tr('log_path',path=result['session_dir']))
    return '\n'.join(lines)

from wrapper.dark_ui import App, run_gui

def ui_self_test(language=None, scale=1.0, screenshot=None, page=2):
    """Programmatic Tk contract test, including in the shipped executable."""
    import tkinter as tk
    from unittest.mock import patch
    import customtkinter as ctk
    ctk.set_appearance_mode('dark')
    root = ctk.CTk()
    root.withdraw()
    app = App(root)
    if language:app.set_language(language)
    results = {'mode_choice_first': app.screen == 0}
    app.values[1].set('stale.zip');app.choose_mode('update');root.update()
    results['update_mode_no_archives'] = app.screen==2 and not app.values[1].get() and all(not w.winfo_manager() for w in app.source_fields)
    app.choose_mode('full');root.update()
    results['full_mode_downloads'] = app.screen==1 and all(w.winfo_manager()=='pack' for w in app.source_fields)
    original_language=app.language
    app.language_control.configure(command=app.set_language)
    app.set_language('EN');results['manual_EN']=app.check_button.cget('text')=='Check'
    app.set_language('RU');results['manual_RU']=app.check_button.cget('text')=='Проверить'
    app.set_language(original_language)
    results['no_pack_panel']=not hasattr(app,'other_pack_button') and not hasattr(app,'choose_other_pack')
    from wrapper import dialogs
    for dialog_language in ('RU','EN'):
        for approve in (True,False):
            def auto_answer(dialog,yes,cancel,approve=approve,language=dialog_language):
                dialog.geometry('700x440+10000+10000')
                results[language+'_confirmation_buttons']=yes.cget('text')==i18n.text('confirm_yes',language) and cancel.cget('text')==i18n.text('confirm_no',language)
                dialog.after(50,(yes if approve else cancel).invoke)
            confirmed=dialogs.confirm(root,i18n.text('confirm_title',dialog_language),i18n.text('confirm',dialog_language,count=1,roots='DBM-Core',backup='C:\\Disposable\\Backup'),dialog_language,auto_answer)
            results[dialog_language+'_confirmation_'+str(approve)]=confirmed==approve
    if screenshot:
        from wrapper.visual_validation import capture_own_window
        app.show(page);root.geometry('800x1000+10000+10000');root.deiconify();root.update()
        ctk.set_widget_scaling(scale);ctk.set_window_scaling(scale)
        if scale!=1:root.geometry('620x420+10000+10000')
        root.update()
        # Allow Tk canvas paints to settle before an off-screen PrintWindow.
        import time
        until=time.monotonic()+0.5
        while time.monotonic()<until:root.update();time.sleep(0.02)
        buttons=(app.next_button,) if page==1 else (app.check_button,app.apply_button,app.back_button,app.close_button)
        results['footer_visible']=all(b.winfo_ismapped() and 0<=b.winfo_rooty()-root.winfo_rooty() and b.winfo_rooty()-root.winfo_rooty()+b.winfo_height()<=root.winfo_height() for b in buttons)
        capture_own_window(root,screenshot)
        app.show(1)
    with patch.object(webbrowser, 'open') as opener:
        for button in app.link_buttons:
            button.invoke()
        results['six_exact_links'] = [c.args[0] for c in opener.call_args_list] == [u for s in SOURCE_LINKS for u in s[2:]]
    app.next_button.invoke()
    results['selection_navigation'] = app.screen == 2
    results['apply_initially_disabled'] = str(app.apply_button.cget('state')) == 'disabled'
    app.finish({'outcome': 'READY', 'details': {'mode': 'FRESH_INSTALL'}}, True)
    results['ready_enables_apply'] = str(app.apply_button.cget('state')) == 'normal'
    app.finish({'outcome': 'BASELINE_MISMATCH'}, True)
    results['failed_check_disables_apply'] = app.checked is None and str(app.apply_button.cget('state')) == 'disabled'
    with patch.object(app.ui, 'run_engine') as engine:
        app.start(False)
        results['failed_check_blocks_handler'] = not engine.called and not app.busy
    app.finish({'outcome': 'READY', 'details': {'mode': 'FRESH_INSTALL'}}, True)
    app.values[0].set('changed')
    results['changed_path_invalidates_check'] = app.checked is None and str(app.apply_button.cget('state')) == 'disabled'
    app.finish({'outcome': 'READY', 'details': {'mode': 'FRESH_INSTALL'}}, True)
    app.source_s18.set('third-donor-changed.zip')
    results['third_donor_invalidates_check'] = app.checked is None and str(app.apply_button.cget('state')) == 'disabled'
    results['three_donor_inputs'] = len(app.inputs) == 8 and app.extra_sources.get('S18') is app.source_s18
    results['third_donor_localized'] = app.tr('source_s18') != 'source_s18' and app.tr('source_s18_title') != 'source_s18_title'
    app.back_button.invoke()
    results['back_navigation'] = app.screen == 0
    app.busy = True
    app.show(2)
    results['navigation_blocked_during_transaction'] = app.screen == 0
    for code in ('DBM_REPARSE_ROOT_REJECTED', 'DBM_TARGET_ROOT_BLOCKED_BY_FILE', 'DBM_SPECIAL_ROOT_REJECTED'):
        result = {'outcome': 'UNSAFE_PATH', 'reason_code': code, 'details': {'failure_detail': 'C:\\Test\\Interface\\AddOns\\DBM-Core'}}
        app.finish(result, True)
        results[code + '_visible_code_path'] = code in app.result_var.get() and result['details']['failure_detail'] in app.result_var.get() and app.checked is None
    # Exercise the real App.start worker's CHECK-to-APPLY handoff.
    from threading import Event
    completed = Event()
    details = {'mode': 'REPLACE_EXISTING_DBM', 'existing_roots': ['DBM-Core'],
               'backup_planned_path': r'\\?\C:\Disposable\Interface\DBM-RV-Patcher-Backup\20261015-201344-dde948dbfa95',
               'inventory_digest_sha256': 'checked-inventory',
               'content_identity': {'pack_sha256': 'checked-pack'}}
    def capture_engine(**kwargs):
        results['gui_forwards_exact_approved_backup'] = kwargs['backup_path'] == details['backup_planned_path']
        results['gui_forwards_checked_inventory'] = kwargs['expected_inventory'] == 'checked-inventory'
        results['gui_forwards_checked_pack'] = kwargs['expected_pack_sha256'] == 'checked-pack'
        completed.set()
        return {'outcome': 'SUCCESS', 'details': {}}
    app.finish({'outcome': 'READY', 'details': details}, True)
    app.pack_ready = True
    with patch.object(dialogs, 'confirm', return_value=True), patch.object(app.ui, 'run_engine', side_effect=capture_engine):
        app.start(False)
        results['gui_apply_worker_completed'] = completed.wait(5)
    root.destroy()
    return {'outcome': 'PASS' if all(results.values()) else 'FAIL', 'tests': results, 'wrapper_version': WRAPPER_VERSION}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--headless-check', action='store_true')
    mode.add_argument('--headless-apply', action='store_true')
    mode.add_argument('--ui-smoke', action='store_true')
    mode.add_argument('--ui-self-test', action='store_true')
    parser.add_argument('--target', default='')
    parser.add_argument('--resume-check', action='store_true', help='Restore selections and run CHECK only; never APPLY')
    parser.add_argument('--source-s01', default='')
    parser.add_argument('--source-s08', default='')
    parser.add_argument('--source-s18', default='')
    parser.add_argument('--pack', default='')
    parser.add_argument('--source-extra', action='append', default=[], help='ID=archive.zip')
    # A headless APPLY can now carry the exact CHECK snapshot forward; GUI
    # already supplied these fields directly. This is for frozen EXE UAT too.
    parser.add_argument('--approved-backup-path', default=None, help='Exact backup path approved during CHECK; same policy as GUI')
    parser.add_argument('--expected-inventory', default=None)
    parser.add_argument('--expected-pack-sha256', default=None)
    parser.add_argument('--expected-mode', default=None,
                        choices=('FRESH_INSTALL', 'REPLACE_EXISTING_DBM', 'ALREADY_PATCHED', 'UPDATE_INSTALLED_PRODUCT'))
    parser.add_argument('--result-json')
    parser.add_argument('--test-fault', default='none', choices=('none', 'target_changed_after_staging', 'backup_failure', 'mid_commit_failure', 'post_commit_corruption'))
    parser.add_argument('--ui-language',choices=('RU','EN'))
    parser.add_argument('--ui-test-scale',type=float,default=1.0,choices=(1.0,1.25,1.5,2.0))
    parser.add_argument('--ui-test-screenshot')
    parser.add_argument('--ui-test-page',type=int,choices=(1,2),default=2)
    args = parser.parse_args(argv)
    if args.ui_self_test:
        result = ui_self_test(args.ui_language,args.ui_test_scale,args.ui_test_screenshot,args.ui_test_page)
        if args.result_json:
            Path(args.result_json).write_text(json.dumps(result, indent=2), encoding='utf-8')
        return 0 if result['outcome'] == 'PASS' else 2
    if not (args.headless_check or args.headless_apply):
        return run_gui(args.ui_smoke, args if args.resume_check else None)
    try:
        extra = dict(item.split('=', 1) for item in args.source_extra)
        if args.source_s18:extra['S18'] = args.source_s18
        result = run_engine(target=args.target, source_s01=args.source_s01, source_s08=args.source_s08, pack_path=args.pack, source_extra=extra, check_only=args.headless_check, test_fault=args.test_fault,
                            backup_path=args.approved_backup_path, expected_inventory=args.expected_inventory, expected_mode=args.expected_mode, expected_pack_sha256=args.expected_pack_sha256)
    except Exception as exc:
        result = exception_result(exc)
    if args.result_json:
        Path(args.result_json).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if result.get('outcome') in {'SUCCESS', 'READY', 'ALREADY_PATCHED'} else 2

if __name__ == '__main__':
    raise SystemExit(main())
