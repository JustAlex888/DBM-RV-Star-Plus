"""RU/EN visible resources. Technical codes, paths and product names stay literal."""
import ctypes,sys

# key: (Russian, English). English is the fallback for unsupported locales.
RESOURCES={
'language':('Язык','Language'),
'confirm_yes':('Продолжить','Continue'),'confirm_no':('Отмена','Cancel'),
'prepare':('Подготовка к установке','Prepare installation'),
'prepare_desc':('Наш пакет обновления входит в установочный комплект.\nСкачайте три оригинальных ZIP по кнопкам ниже.','Our update is included in this installation bundle.\nDownload only the three original ZIPs using the buttons below.'),
'source_title':('DBM-RV от Aleksart163','DBM-RV by Aleksart163'),
'source_desc':('Основной исходный продукт, с которым работает патч.','The original DBM-RV used by this patch.'),
'dungeons_desc':('Дополнительный исходный пакет для модулей WoD и BfA.','Original source for the WoD and BfA dungeon modules.'),
'official':('Официальная страница:','Official page:'),'open_page':('Открыть страницу','Open page'),
'download_label':('Прямая загрузка ZIP:','Original ZIP:'),'download':('Скачать ZIP','Download ZIP'),
'keep_zip':('ZIP распаковывать не нужно.','Keep the original ZIP unopened.'),
'prepare_info':('ⓘ   На следующем экране укажите папку WoW\n     и три оригинальных ZIP.','ⓘ   On the next screen, select your WoW folder\n     and the three original ZIPs.'),
'exit':('Выход','Exit'),'next':('Я скачал необходимые файлы','I have downloaded the files'),
'selection':('Выбор путей и файлов','Select paths and files'),
'selection_desc':('Укажите папку WoW и три оригинальных ZIP.','Select your WoW folder and the three original ZIPs.'),
'wow_folder':('Папка WoW или Interface\\AddOns','WoW folder or Interface\\AddOns'),
'source_s01':('ZIP-файл DBM-RV от Aleksart','Original DBM-RV ZIP by Aleksart'),
'source_s08':('ZIP-файл DBM-Dungeons','Original DBM-Dungeons ZIP'),
'browse':('Выбрать…','Browse…'),'zip':('ZIP…','ZIP…'),'zip_dialog':('Выберите ZIP-файл','Select an original ZIP file'),
'result':('РЕЗУЛЬТАТ','RESULT'),
'close_wow':('ⓘ  Закройте World of Warcraft перед установкой.','ⓘ  Close World of Warcraft before installation.'),
'initial':('Нажмите «Проверить». Установка пока не изменяется.\nРезервная копия будет создана только при наличии старого DBM.','Click Check. No installation files are changed yet.\nA backup is created when an existing managed DBM is found.'),
'back':('Назад','Back'),'check':('Проверить','Check'),'apply':('Применить','Apply'),'close':('Закрыть','Close'),
'check_started':('… Проверка исходников','… Checking originals'),
'apply_started':('… Установка DBM RV*+ — не закрывайте программу','… Installing DBM RV*+ — keep this program open'),
'check_note':('Проверка не изменяет AddOns.','Check does not change AddOns.'),
'apply_note':('Завершённые этапы сохраняются в журнале.','Completed steps are recorded in the log.'),
'confirm_title':('Замена управляемого DBM','Replace managed DBM'),
'confirm':('Будут сохранены в резервной копии и заменены только управляемые папки ({count}):\n{roots}\n\nРезервная копия:\n{backup}\n\nНезависимые аддоны остаются на месте. Продолжить?','Only the managed folders will be backed up and replaced ({count}):\n{roots}\n\nBackup:\n{backup}\n\nIndependent addons remain in place. Continue?'),
'ready':('Проверка пройдена. Можно применить установку.','Check passed. You can apply the installation.'),
'success':('DBM RV*+ успешно установлен.\nМожно закрыть установщик и запустить World of Warcraft.\nВсе установленные файлы проверены.','DBM RV*+ installed successfully.\nYou can close the installer and start World of Warcraft.\nAll installed files have been verified.'),
'already':('Уже установлена точная ожидаемая сборка. Ничего не изменено.','The exact expected build is already installed. Nothing changed.'),
'stopped':('Операция остановлена. Смотрите результат ниже.','Operation stopped. See the result below.'),
'error':('Проверка или установка остановлена из-за ошибки.','Check or installation stopped because of an error.'),
'backup_failed':('Резервная копия не подтверждена. Установка не изменена.','The backup could not be verified. Installation files were not changed.'),
'rollback_failed':('Восстановление не подтверждено. Не запускайте WoW; сохраните резервную копию и журнал.','Recovery could not be verified. Do not start WoW; keep the backup and log.'),
'fresh':('Предыдущая управляемая установка DBM не обнаружена. Резервная копия не требуется.','No previous managed DBM installation was found. No backup is required.'),
'target_identity':('Целевая сборка: {version} / {build}\nФайлов: {files}; управляемых папок: {roots}','Target build: {version} / {build}\nFiles: {files}; managed folders: {roots}'),
'mode':('Режим: {mode}','Mode: {mode}'),
'mode_FRESH_INSTALL':('Чистая установка','Fresh installation'),
'mode_REPLACE_EXISTING_DBM':('Замена управляемого DBM','Replace managed DBM'),
'mode_ALREADY_PATCHED':('Точная сборка уже установлена','Exact build already installed'),
'found':('Обнаружено управляемых папок: {count}','Managed folders found: {count}'),
'preserved':('Независимые DBM-аддоны и обычные файлы сохранены без изменений.','Independent DBM addons and regular files were preserved unchanged.'),
'preservation_pending':('Сохранность независимых файлов пока не подтверждена; смотрите журнал.','Preservation of independent files is not yet confirmed; see the log.'),
'restored':('Исходные управляемые папки полностью восстановлены и проверены.','The original managed folders were fully restored and verified.'),
'backup_path':('Резервная копия: {path}','Backup: {path}'),
'log_path':('Журнал: {path}','Log: {path}'),
'technical_code':('Технический код: {code}','Technical code: {code}'),
'detail':('Подробности: {detail}','Details: {detail}'),
'SELECT_WOW_ROOT':('Выберите папку WoW или Interface\\AddOns.','Select your WoW folder or Interface\\AddOns.'),
'ADDONS_ROOT_NOT_FOUND':('Папка Interface\\AddOns не найдена по выбранному пути.','Interface\\AddOns was not found at the selected path.'),
'BUNDLE_MISSING':('Установочный комплект неполный. Распакуйте весь исходный архив вместе с папкой UpdatePacks.','The installation bundle is incomplete. Extract the entire original archive, including UpdatePacks.'),
'BUNDLE_AMBIGUOUS':('В UpdatePacks несколько ZIP. Используйте полный исходный комплект с одним пакетом.','UpdatePacks contains multiple ZIPs. Use the original complete bundle with one update.'),
'BUNDLE_INVALID':('Пакет внутри комплекта повреждён или непригоден. Заново распакуйте проверенный установочный архив.','The included update is damaged or invalid. Extract the verified installation archive again.'),
'PACK_CHANGED_SINCE_USER_CHECK':('Пакет изменился после проверки. Установка остановлена; повторите проверку.','The update changed after Check. Installation stopped; run Check again.'),
'TARGET_CHANGED_SINCE_USER_CHECK':('Файлы игры или независимых аддонов изменились после проверки. Повторите проверку.','Game or independent addon files changed after Check. Run Check again.'),
'DBM_REPARSE_ROOT_REJECTED':('Обнаружена ссылка или reparse-объект DBM. Установщик не следует по ссылкам и ничего не изменяет.','A DBM link or reparse object was found. The installer does not follow links or change this object.'),
'REPARSE_PATH_REJECTED':('Выбранный путь содержит ссылку или reparse-объект. Установка остановлена.','The selected path contains a link or reparse object. Installation stopped.'),
'DBM_TARGET_ROOT_BLOCKED_BY_FILE':('Обычный файл занимает имя обязательной папки DBM. Установщик не удаляет этот файл.','A regular file occupies a required DBM folder name. The installer does not delete that file.'),
'DBM_SPECIAL_ROOT_REJECTED':('Обнаружен специальный объект DBM. Установка остановлена.','A special DBM object was found. Installation stopped.'),
'PACK_CANNOT_MANAGE_INDEPENDENT_DIAGNOSTICS':('Пакет пытается изменить независимый диагностический аддон. Установка запрещена.','The update attempts to change an independent diagnostic addon. Installation is blocked.'),
'SOURCE_S01_NOT_SELECTED':('Выберите оригинальный ZIP DBM-RV от Aleksart.','Select the original DBM-RV ZIP by Aleksart.'),
'SOURCE_S08_NOT_SELECTED':('Выберите оригинальный ZIP DBM-Dungeons.','Select the original DBM-Dungeons ZIP.'),
'source_invalid':('Оригинальный ZIP не соответствует закреплённой версии или повреждён. Скачайте его по кнопке установщика.','The original ZIP is damaged or does not match the pinned revision. Download it using the installer button.'),
'pack_invalid':('Пакет обновления не прошёл проверку целостности. Установка остановлена.','The included update failed integrity checks. Installation stopped.'),
'INPUTS_VERIFIED':('✓ Исходники проверены. Управляемых папок: {count}','✓ Originals verified. Managed folders: {count}'),
'BUILDING_CLEAN_BASE':('… Подготавливается чистая база DBM-RV','… Preparing the clean DBM-RV base'),
'CLEAN_BASE_BUILT':('✓ Чистая база подготовлена','✓ Clean base prepared'),
'APPLYING_PROJECT_TRANSFORMATIONS':('… Подготавливаются модули и изменения DBM RV*+','… Preparing DBM RV*+ modules and updates'),
'STAGING_BUILT':('✓ Установочные файлы подготовлены','✓ Installation files prepared'),
'STAGING_VERIFIED':('✓ Полное установочное дерево проверено','✓ Complete installation tree verified'),
'PRECOMMIT_RECHECKED':('✓ Исходники и установленный DBM повторно проверены','✓ Originals and installed DBM checked again'),
'BACKUP_IN_PROGRESS':('… Создаётся резервная копия управляемых папок DBM','… Backing up managed DBM folders'),
'BACKUP_COPIED':('✓ Резервная копия создана','✓ Backup created'),
'BACKUP_VERIFIED':('✓ Резервная копия проверена: {count}/{count} папок','✓ Backup verified: {count}/{count} folders'),
'BACKUP_NOT_REQUIRED':('✓ Резервная копия не требуется','✓ No backup required'),
'COMMIT_IN_PROGRESS':('… Подготавливается установка управляемого DBM','… Preparing the managed DBM installation'),
'OLD_DBM_DISPLACED':('✓ Место для управляемого DBM подготовлено','✓ Managed DBM destination prepared'),
'INSTALLING_CLEAN_TARGET':('… Устанавливается DBM RV*+','… Installing DBM RV*+'),
'COMMIT_COMPLETE':('✓ Целевая сборка установлена','✓ Target build installed'),
'VERIFYING_COMPLETE_TARGET':('… Проверяются все установленные файлы','… Verifying all installed files'),
'COMMIT_VERIFIED':('✓ Проверка результата завершена','✓ Result verification complete'),
'SUCCESS':('✓ УСТАНОВКА УСПЕШНО ЗАВЕРШЕНА','✓ INSTALLATION COMPLETED SUCCESSFULLY'),
'ROLLBACK_IN_PROGRESS':('… Восстанавливаются исходные управляемые папки','… Restoring the original managed folders'),
'ROLLBACK_VERIFIED':('✓ Исходные папки восстановлены и проверены','✓ Original folders restored and verified'),
}
TABLES={lang:{key:pair[i] for key,pair in RESOURCES.items()} for i,lang in enumerate(('RU','EN'))}
RESOURCES.update({
'admin_title':('Нужны права администратора','Administrator permission required'),
'admin_needed':('Для установки в эту папку нужны права администратора. Нажмите «Применить»: установщик предложит перезапуск через стандартный запрос Windows. Выбранные файлы сохранятся.','This folder requires administrator permission. Click Apply to restart through the standard Windows prompt. Your selected files will be kept.'),
'admin_confirm':('Windows ограничивает изменение выбранной папки игры. Перезапустить установщик с правами администратора?\n\nПодтвердите запрос Windows. Все выбранные пути сохранятся; после перезапуска установщик повторит проверку. Установка начнётся только после повторного нажатия «Применить».','Windows restricts changes to the selected game folder. Restart the installer as administrator?\n\nApprove the Windows prompt. Your selections will be kept and Check will run again. Installation starts only when you click Apply again.'),
'admin_cancelled':('Запрос прав администратора отменён. Файлы игры не изменялись. Выбранные пути сохранены; можно повторить попытку.','Administrator permission was cancelled. Game files were not changed. Your selections are kept; you can try again.'),
'admin_failed':('Не удалось перезапустить установщик с правами администратора. Выбранные пути сохранены. Закройте установщик и выберите для EXE «Запуск от имени администратора».','The installer could not restart as administrator. Your selections are kept. Close it and use Run as administrator on the EXE.'),
'ADMIN_REQUIRED':('Windows не разрешает изменить папку игры без прав администратора. Запустите установщик от имени администратора и повторите проверку.','Windows requires administrator permission to change this game folder. Run the installer as administrator and repeat Check.'),
'ACCESS_DENIED':('Windows запретила доступ к папке игры. Закройте WoW. Если установщик уже запущен от имени администратора, проверьте разрешения папки и блокировку защитой Windows.','Windows denied access to the game folder. Close WoW. If the installer is already running as administrator, check folder permissions and Windows protection.'),
'source_s18_title':('DBM — исторические модули 2018','DBM — historical modules (2018)'),
'source_s18_desc':('Исторические версии модулей, необходимые для этой сборки.','Historical module versions required for this build.'),
'source_s18':('ZIP-файл DBM 2018','Original DBM 2018 ZIP'),
})
TABLES={lang:{key:pair[i] for key,pair in RESOURCES.items()} for i,lang in enumerate(('RU','EN'))}
RU_TO_KEY={pair[0]:key for key,pair in RESOURCES.items()}

def detect_language(lang_id=None):
    if lang_id is None:
        try:lang_id=ctypes.windll.kernel32.GetUserDefaultUILanguage() if sys.platform=='win32' else 0x409
        except (AttributeError,OSError):lang_id=0x409
    return 'RU' if (lang_id & 0x3ff)==0x19 else 'EN'

def text(key,language='EN',**values):
    return TABLES.get(language,TABLES['EN']).get(key,TABLES['EN'].get(key,key)).format(**values)

def error_text(code,language):
    if code in RESOURCES:return text(code,language)
    if str(code).startswith('SOURCE_'):return text('source_invalid',language)
    if str(code).startswith(('PACK_','BUNDLED_')):return text('pack_invalid',language)
    return text('error',language)

def progress_text(event,language):
    state=event['state']
    if state=='FRESH_INSTALL':return '✓ '+text('fresh',language)
    if state not in RESOURCES:return ''
    return text(state,language,count=event.get('root_count',0))
