"""Dark two-screen view. All transaction work belongs to the pinned engine."""
import ctypes
import os
import queue
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog
import customtkinter as ctk
from wrapper import i18n
from wrapper import dialogs

BG = '#15191d'
CARD = '#1d2228'
BORDER = '#343c44'
BLUE = '#155cdb'
TEXT = '#f1f4f7'
MUTED = '#b9c0c9'

class App:
    def __init__(self, root):
        from wrapper import installer_ui as ui
        self.ui, self.root = ui, root
        self.language = i18n.detect_language()
        self.text_bindings = []
        self.history_events = []
        self.current_note = "initial"
        self.busy, self.checked, self.screen = False, None, 1
        self.events = queue.Queue()
        self.values = [tk.StringVar() for _ in range(4)]
        self.pack_identity = tk.StringVar(value="Содержимое DBM: выберите ZIP-пакет обновления")
        self.pack_status = tk.StringVar(value='Проверка комплектного пакета…')
        self.pack_ready = False
        self.pack_origin = 'bundled'
        self.source_s18 = tk.StringVar()
        self.extra_sources = {'S18': self.source_s18}
        self.extra_source_widgets = []
        self.result_var = tk.StringVar()
        self.history, self.pending, self.last_event = [], [], 0
        root.title('DBM-RV Patcher — 0.2.5 Modular TEST')
        root.configure(fg_color=BG)
        # Canonical portrait composition; fit to available logical desktop height.
        dpi = ctypes.windll.user32.GetDpiForWindow(root.winfo_id()) if os.name == 'nt' else 96
        self.height = min(1000, int(root.winfo_screenheight() * 96 / max(dpi, 96)) - 90)
        self.height = max(640, self.height)
        self.width = max(640, round(self.height * .8))
        root.geometry(f'{self.width}x{self.height}')
        root.minsize(620, 360)
        self.unit = self.height / 1000
        language_bar = ctk.CTkFrame(root, fg_color=BG, corner_radius=0)
        language_bar.pack(fill='x', padx=20, pady=(8,0))
        self.label(language_bar, 'language', 15).pack(side='left')
        self.language_control = ctk.CTkSegmentedButton(language_bar, values=['RU','EN'], command=self.set_language, width=130)
        self.language_control.set(self.language)
        self.language_control.pack(side='right')
        self.preparation = ctk.CTkFrame(root, fg_color=BG, corner_radius=0)
        self.selection = ctk.CTkFrame(root, fg_color=BG, corner_radius=0)
        self.link_buttons, self.inputs = [], []
        self.build_preparation()
        self.build_selection()
        for var in self.values:
            var.trace_add('write', self.invalidate)
        self.values[3].trace_add('write', self.preview_pack)
        self.source_s18.trace_add('write', self.invalidate)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.show(1)
        self.autoload_pack()
        root.after(70, self.poll)

    def n(self, size):
        return max(1, round(size * self.unit))

    def tr(self, key, **values):
        return i18n.text(key, getattr(self, 'language', 'EN'), **values)

    def localized_widget(self, widget, raw):
        key = raw if raw in i18n.RESOURCES else i18n.RU_TO_KEY.get(raw)
        if key:
            widget.configure(text=self.tr(key))
            self.text_bindings.append((widget,key))
        return widget

    def label(self, parent, text='', size=18, bold=False, color=TEXT, **kw):
        widget=ctk.CTkLabel(parent, text=text, text_color=color,
            font=('Segoe UI', self.n(size), 'bold' if bold else 'normal'), anchor='w', justify='left', **kw)
        return self.localized_widget(widget,text)

    def button(self, parent, text, command, primary=False, width=130):
        widget=ctk.CTkButton(parent, text=text, command=command, width=self.n(width), height=self.n(43),
            corner_radius=self.n(7), border_width=1, border_color='#4384ec' if primary else BORDER,
            fg_color=BLUE if primary else '#252c33', hover_color='#2374ee' if primary else '#34404c',
            text_color=TEXT, text_color_disabled='#707b87', font=('Segoe UI', self.n(17)))
        return self.localized_widget(widget,text)

    def set_language(self, language):
        if self.busy or language not in ('RU','EN'):return
        self.language=language
        self.language_control.set(language)
        for widget,key in self.text_bindings:
            if widget.winfo_exists():widget.configure(text=self.tr(key))
        self.history=[i18n.progress_text(event,language) for event in self.history_events]
        self.history=[line for line in self.history if line]
        if hasattr(self,'last_result'):
            self.render_result(self.last_result)
        else:
            self.result_var.set(self.tr(self.current_note))
        if not self.pack_ready:self.result_var.set(self.tr('BUNDLE_'+getattr(self,'bundle_state','INVALID')))
        self.render_log()

    def card(self, parent):
        return ctk.CTkFrame(parent, fg_color=CARD, corner_radius=self.n(12), border_width=1, border_color=BORDER)

    def emblem(self, parent, index):
        import math
        badge = ctk.CTkFrame(parent, width=self.n(74), height=self.n(74), fg_color='transparent')
        badge.pack(side='left', padx=(0, self.n(12)))
        badge.pack_propagate(False)
        canvas = tk.Canvas(badge, background=CARD, highlightthickness=0, borderwidth=0)
        canvas.pack(fill='both', expand=True)
        def draw(event):
            canvas.delete('all')
            w, h = event.width, event.height
            side = min(w, h)
            def box(a,b,c,d):
                return tuple(v * side for v in (a,b,c,d))
            if index == 0:
                canvas.create_oval(*box(.05,.05,.94,.94), fill='#15212b', outline='#328fea', width=max(2, side*.06))
                canvas.create_arc(*box(.05,.05,.94,.94), start=15, extent=145, style='arc', outline='#53bdff', width=max(2,side*.05))
                canvas.create_text(side*.5,side*.5,text='RV',fill=TEXT,font=('Segoe UI',-round(side*.40),'bold'))
            else:
                canvas.create_oval(*box(.03,.03,.97,.97),fill='#131c24',outline='')
                canvas.create_arc(*box(.19,.13,.81,.80),start=0,extent=180,fill='#687780',outline='#3b4850',width=side*.025)
                canvas.create_rectangle(*box(.19,.45,.81,.85),fill='#63717a',outline='#3b4850')
                canvas.create_arc(*box(.32,.26,.68,.70),start=0,extent=180,fill='#b97d25',outline='')
                canvas.create_rectangle(*box(.32,.48,.68,.82),fill='#b97d25',outline='')
                canvas.create_rectangle(*box(.40,.45,.60,.82),fill='#ffba46',outline='')
                for y in (.49,.61,.73):
                    canvas.create_line(*box(.19,y,.32,y),fill='#303e47',width=max(1,side*.025))
                    canvas.create_line(*box(.68,y,.81,y),fill='#303e47',width=max(1,side*.025))
                for angle in (35,65,95,125,155):
                    theta=math.radians(angle)
                    canvas.create_line(side*(.5+.30*math.cos(theta)),side*(.45-.32*math.sin(theta)),side*(.5+.18*math.cos(theta)),side*(.45-.19*math.sin(theta)),fill='#303e47',width=max(1,side*.025))
                canvas.create_rectangle(*box(.13,.82,.88,.89),fill='#879199',outline='#38444d')
        canvas.bind('<Configure>', draw)

    def header(self, parent, title, subtitle):
        self.label(parent, title, 31, True).pack(anchor='w', padx=self.n(30), pady=(self.n(28), self.n(10)))
        self.label(parent, subtitle, 19, color=MUTED).pack(anchor='w', padx=self.n(30), pady=(0, self.n(28)))

    def build_preparation(self):
        page = self.preparation
        p = ctk.CTkScrollableFrame(page, fg_color=BG, corner_radius=0)
        p.pack(fill='both',expand=True)
        self.preparation_body=p
        self.header(p, 'prepare', 'prepare_desc')
        for i, (title, description, project, download) in enumerate(self.ui.SOURCE_LINKS):
            card = self.card(p)
            card.pack(fill='x', padx=self.n(20), pady=(0, self.n(22)))
            top = ctk.CTkFrame(card, fg_color='transparent')
            top.pack(fill='x', padx=self.n(20), pady=(self.n(18), self.n(20)))
            # Code-native emblems, not additional AI-generated visual references.
            self.emblem(top, i)
            titles = ctk.CTkFrame(top, fg_color='transparent')
            titles.pack(side='left', fill='x', expand=True)
            self.label(titles, title, 23, True).pack(anchor='w')
            self.label(titles, 'source_s18_desc' if i == 2 else ('Основной исходный продукт, с которым работает патч.' if i == 0 else 'Дополнительный исходный пакет для модулей WoD и BfA.'), 16, color=MUTED).pack(anchor='w', pady=(self.n(8), 0))
            for caption, url, button_label in [('Официальная страница:', project, 'Открыть страницу'), ('Прямая загрузка ZIP:', download, 'Скачать ZIP')]:
                row = ctk.CTkFrame(card, fg_color='transparent')
                row.pack(fill='x', padx=self.n(20), pady=self.n(7))
                button = self.button(row, button_label, lambda u=url: webbrowser.open(u), width=160)
                button.pack(side='right', padx=(self.n(10), 0))
                self.link_buttons.append(button)
                self.label(row, caption, 16).pack(side='left', padx=(0, self.n(8)))
                short = url.replace('https://', '')
                if '/archive/' in short:
                    short = '…/archive/' + url.split('/archive/')[1][:7] + '…zip'
                link = self.label(row, short, 15, color='#81b4fb')
                link.pack(side='left', fill='x', expand=True)
                link.bind('<Button-1>', lambda e, u=url: webbrowser.open(u))
            self.label(card, 'ZIP распаковывать не нужно.', 16, color=MUTED).pack(anchor='w', padx=self.n(20), pady=(self.n(5), self.n(17)))
        info = ctk.CTkFrame(p, fg_color='#1d2935', border_color='#3a526a', border_width=1, corner_radius=self.n(11))
        info.pack(fill='x', padx=self.n(20))
        self.label(info, 'prepare_info', 18, color='#dde5ed').pack(anchor='w', padx=self.n(22), pady=self.n(23))
        bar = ctk.CTkFrame(page, fg_color='transparent')
        # Reserve footer space before the content cards consume the viewport.
        bar.pack(side='bottom', before=p._parent_frame, fill='x', padx=self.n(20), pady=self.n(20))
        self.button(bar, 'Выход', self.close, width=110).pack(side='right')
        self.next_button = self.button(bar, 'Я скачал необходимые файлы', lambda: self.show(2), True, 280)
        self.next_button.pack(side='right', padx=self.n(15))

    def build_selection(self):
        p = self.selection
        body = ctk.CTkScrollableFrame(p, fg_color=BG, corner_radius=0)
        body.pack(fill='both', expand=True)
        self.selection_body = body
        self.header(body, 'selection', 'selection_desc')
        card = self.card(body)
        card.pack(fill='x', padx=self.n(20))
        for index, text in enumerate(('Папка WoW или Interface\\AddOns', 'ZIP-файл DBM-RV от Aleksart', 'ZIP-файл DBM-Dungeons', 'source_s18')):
            self.label(card, text, 20).pack(anchor='w', padx=self.n(20), pady=(self.n(12), self.n(4)))
            row = ctk.CTkFrame(card, fg_color='transparent')
            row.pack(fill='x', padx=self.n(20), pady=(0, self.n(9)))
            def browse(i=index):
                chosen = filedialog.askdirectory(parent=self.root, title=self.tr('wow_folder')) if i == 0 else filedialog.askopenfilename(parent=self.root, title=self.tr('zip_dialog'), filetypes=[('ZIP', '*.zip')])
                if chosen:
                    (self.values[i] if i < 3 else self.source_s18).set(chosen)
            button = self.button(row, 'Выбрать…' if index == 0 else 'ZIP…', browse, width=120)
            button.pack(side='right', padx=(self.n(14), 0))
            entry = ctk.CTkEntry(row, textvariable=(self.values[index] if index < 3 else self.source_s18), height=self.n(40), corner_radius=self.n(6),
                fg_color='#22282e', border_color='#48525d', border_width=1, text_color=TEXT, font=('Segoe UI', self.n(17)))
            entry.pack(side='left', fill='x', expand=True)
            self.inputs.extend((entry, button))
        ctk.CTkFrame(body, height=1, fg_color=BORDER).pack(fill='x', padx=self.n(20), pady=self.n(23))
        self.label(body, 'РЕЗУЛЬТАТ', 21, True).pack(anchor='w', padx=self.n(20), pady=(0, self.n(18)))
        self.panel = ctk.CTkFrame(body, fg_color='#1d2a36', border_color='#38536d', border_width=1, corner_radius=self.n(10))
        self.panel.pack(fill='both', expand=True, padx=self.n(20), pady=(0, self.n(9)))
        self.headline = self.label(self.panel, 'ⓘ  Закройте World of Warcraft перед установкой.', 20, True, color='#dfebf7', wraplength=self.width-self.n(95))
        self.headline.pack(fill='x', padx=self.n(22), pady=(self.n(22), self.n(10)))
        self.log = ctk.CTkTextbox(self.panel, fg_color='transparent', text_color='#d5dee7', border_width=0,
            font=('Segoe UI', self.n(16)), height=self.n(100), wrap='word', activate_scrollbars=True)
        self.log.pack(fill='both', expand=True, padx=self.n(18), pady=(0, self.n(10)))
        self.log.configure(state='disabled')
        self.result_var.set(self.tr('initial'))
        self.result_var.trace_add('write', lambda *a: self.render_log())
        self.render_log()
        bar = ctk.CTkFrame(p, fg_color='transparent')
        # Dynamic S02 fields must never push Check/Apply outside the window.
        bar.pack(side='bottom', before=p.winfo_children()[0], fill='x', padx=self.n(20), pady=(0, self.n(20)))
        self.back_button = self.button(bar, 'Назад', lambda: self.show(1), width=105)
        self.check_button = self.button(bar, 'Проверить', lambda: self.start(True), True, 135)
        self.apply_button = self.button(bar, 'Применить', lambda: self.start(False), width=130)
        self.close_button = self.button(bar, 'Закрыть', self.close, width=120)
        for b in (self.back_button, self.check_button, self.apply_button):
            b.pack(side='left', padx=(0, self.n(10)))
        self.close_button.pack(side='right')
        self.apply_button.configure(state='disabled')

    def autoload_pack(self):
        result=self.ui.discover_bundled_pack()
        self.bundle_state=result['state']
        if result['state']=='READY':self.values[3].set(result['path'])
        else:
            self.pack_ready=False
            self.result_var.set(self.tr('BUNDLE_'+result['state']))
            self.check_button.configure(state='disabled')

    def render_log(self):
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.insert('end', '\n'.join(self.history) + ('\n\n' if self.history else '') + self.result_var.get())
        self.log.configure(state='disabled')
        # Keep full history accessible; latest state is visible without another Check.
        self.log.see('end')

    def show(self, screen):
        if self.busy:
            return
        self.preparation.pack_forget()
        self.selection.pack_forget()
        (self.preparation if screen == 1 else self.selection).pack(fill='both', expand=True)
        self.screen = screen

    def close(self):
        if not self.busy:
            self.root.destroy()

    def preview_pack(self, *unused):
        path=self.values[3].get()
        self.extra_sources={'S18': self.source_s18}
        try:
            self.ui.validate_install_pack(path)
            self.pack_ready=True
            self.bundle_state='READY'
            self.check_button.configure(state='normal')
        except Exception:
            self.pack_ready=False
            self.bundle_state='INVALID'
            self.result_var.set(self.tr('BUNDLE_INVALID'))
            self.check_button.configure(state='disabled')

    def invalidate(self, *unused):
        self.checked = None
        self.apply_button.configure(state='disabled')

    def render_result(self,result):
        outcome=result.get('outcome')
        key={'SUCCESS':'success','READY':'ready','ALREADY_PATCHED':'already'}.get(outcome,'stopped')
        self.headline.configure(text=('✓  ' if outcome in ('SUCCESS','READY','ALREADY_PATCHED') else '⚠  ')+self.tr(key),
            text_color='#aee6bf' if outcome in ('SUCCESS','READY','ALREADY_PATCHED') else '#ffc998')
        self.result_var.set(self.ui.outcome_message(result,getattr(self,'language','EN')))

    def finish(self, result, check_only):
        self.busy=False
        self.last_result=result
        for widget in self.inputs+[self.back_button,self.check_button,self.close_button]+([self.language_control] if hasattr(self,'language_control') else []):
            if widget.winfo_exists():widget.configure(state='normal')
        self.render_result(result)
        self.checked=result if check_only and result.get('outcome')=='READY' else None
        self.apply_button.configure(state='normal' if self.checked else 'disabled')
        if not self.pack_ready:self.check_button.configure(state='disabled')

    def start(self, check_only):
        if self.busy or not getattr(self, 'pack_ready', True) or (not check_only and self.checked is None):
            return
        approved = self.checked if not check_only else None
        if approved and approved['details']['mode'] != 'FRESH_INSTALL':
            d = approved['details']
            if not dialogs.confirm(self.root,self.tr('confirm_title'), self.tr('confirm',count=len(d['existing_roots']),roots=', '.join(d['existing_roots']),backup=d['backup_planned_path']),getattr(self,'language','EN')):
                return
        # Snapshot every Tcl StringVar on the MAIN UI thread. Reading even a
        # read-only Tk variable from the background worker is not thread-safe.
        values = [v.get() for v in self.values]
        source_extra_snapshot = {sid: v.get() for sid, v in self.extra_sources.items()}
        self.busy, self.checked = True, None
        self.history = []
        self.history_events = []
        for widget in self.inputs + [self.back_button, self.check_button, self.apply_button, self.close_button] + ([self.language_control] if hasattr(self,'language_control') else []):
            if widget.winfo_exists():
                widget.configure(state='disabled')
        self.headline.configure(text=self.tr('check_started' if check_only else 'apply_started'), text_color='#91bcff')
        self.current_note='check_note' if check_only else 'apply_note'
        self.result_var.set(self.tr(self.current_note))
        def worker():
            try:
                d = approved['details'] if approved else {}
                result = self.ui.run_engine(target=values[0], source_s01=values[1], source_s08=values[2], pack_path=values[3], source_extra=source_extra_snapshot, check_only=check_only,
                    backup_path=d.get('backup_planned_path'), expected_inventory=d.get('inventory_digest_sha256'), expected_mode=d.get('mode'),
                    progress=lambda e: self.events.put(('progress', e, check_only)),
                    expected_pack_sha256=(d.get('content_identity') or {}).get('pack_sha256'))
            except Exception as exc:
                result = self.ui.exception_result(exc)
            self.events.put(('result', result, check_only))
        threading.Thread(target=worker, daemon=False).start()

    def progress(self,event):
        line=i18n.progress_text(event,getattr(self,'language','EN'))
        if line and (not self.history or self.history[-1]!=line):
            self.history_events.append(dict(event))
            self.history.append(line)
            self.render_log()
            if line.startswith('…'):self.headline.configure(text=line,text_color='#91bcff')

    def poll(self):
        try:
            while True:
                self.pending.append(self.events.get_nowait())
        except queue.Empty:
            pass
        # UI-only dwell. Engine never waits for presentation or screenshots.
        if self.pending and time.monotonic() - self.last_event >= .35:
            kind, data, check_only = self.pending.pop(0)
            if kind == 'progress':
                self.progress(data)
            else:
                self.finish(data, check_only)
            self.last_event = time.monotonic()
        self.root.after(70, self.poll)

def run_gui(smoke=False):
    ctk.set_appearance_mode('dark')
    root = ctk.CTk()
    App(root)
    if smoke:
        root.after(1000, root.destroy)
    root.mainloop()
    return 0
