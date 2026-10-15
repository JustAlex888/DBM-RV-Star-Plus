"""Application-owned confirmation: both captions and buttons follow RU/EN."""
import customtkinter as ctk
from wrapper import i18n

def confirm(parent,title,message,language,on_open=None):
    dialog=ctk.CTkToplevel(parent);dialog.title(title);dialog.geometry('700x440')
    dialog.configure(fg_color='#15191d');dialog.transient(parent)
    answer={'value':False}
    def finish(value):answer['value']=value;dialog.destroy()
    dialog.protocol('WM_DELETE_WINDOW',lambda:finish(False))
    body=ctk.CTkTextbox(dialog,wrap='word',fg_color='#1d2228',text_color='#f1f4f7',font=('Segoe UI',16))
    body.pack(fill='both',expand=True,padx=20,pady=20);body.insert('1.0',message);body.configure(state='disabled')
    bar=ctk.CTkFrame(dialog,fg_color='transparent');bar.pack(fill='x',padx=20,pady=(0,20))
    cancel=ctk.CTkButton(bar,text=i18n.text('confirm_no',language),command=lambda:finish(False))
    cancel.pack(side='right')
    yes=ctk.CTkButton(bar,text=i18n.text('confirm_yes',language),command=lambda:finish(True))
    yes.pack(side='right',padx=12)
    if on_open:on_open(dialog,yes,cancel)
    dialog.grab_set();parent.wait_window(dialog)
    return answer['value']
