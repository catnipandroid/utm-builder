#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UTM Builder GUI (Tkinter)
- macOS-friendly single-file app
- Generates UTM-tagged URLs (GA/GA4)
- Presets, history, validation, clipboard copy

Run:
  python utm_builder.py
Optional packaging (after installing pyinstaller):
  pyinstaller --noconfirm --onefile --windowed utm_builder.py

Author: ChatGPT
"""
import json
import os
import sys
import webbrowser
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse, quote_plus

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

APP_TITLE = "UTM 생성기 - By 재현"
PRESETS_PATH = os.path.expanduser("~/.utm_builder_presets.json")
HISTORY_LIMIT = 20

REQUIRED_KEYS = ["utm_source", "utm_medium", "utm_campaign"]

GA4_OPTIONAL_KEYS = [
    # GA4-extended UTMs (optional)
    "utm_id",
    "utm_source_platform",
    "utm_creative_format",
    "utm_marketing_tactic",
]

def load_presets():
    if os.path.exists(PRESETS_PATH):
        try:
            with open(PRESETS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_presets(presets):
    try:
        with open(PRESETS_PATH, "w", encoding="utf-8") as f:
            json.dump(presets, f, ensure_ascii=False, indent=2)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save presets:\n{e}")

def normalize_pair(k, v, force_lower=False, space_mode="underscore"):
    def transform(s):
        if s is None:
            return s
        s = s.strip()
        if force_lower:
            s = s.lower()
        if space_mode == "underscore":
            s = s.replace(" ", "_")
        elif space_mode == "dash":
            s = s.replace(" ", "-")
        # "keep" leaves spaces which will be URL-encoded
        return s
    return transform(k), transform(v)

def build_utm_url(base_url, pairs, *, force_lower, space_mode, merge_existing=True, override_existing=True):
    if not base_url:
        raise ValueError("Base URL is required.")
    parsed = urlparse(base_url if "://" in base_url else "https://" + base_url)
    if not parsed.netloc:
        raise ValueError("Base URL seems invalid. Example: https://example.com/landing")
    # collect existing query params
    existing = {}
    if merge_existing and parsed.query:
        for k, v in parse_qsl(parsed.query, keep_blank_values=True):
            existing[k] = v

    # apply transforms & build new utm dict
    utm = {}
    for k, v in pairs.items():
        if not v:
            continue
        nk, nv = normalize_pair(k, v, force_lower, space_mode)
        if not nk or nv is None or nv == "":
            continue
        if override_existing or nk not in existing:
            utm[nk] = nv

    # merge
    final = existing.copy()
    final.update(utm)

    # reconstruct URL
    new_query = urlencode(final, doseq=True, quote_via=quote_plus)
    rebuilt = parsed._replace(query=new_query)
    return urlunparse(rebuilt)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("920x680")
        self.minsize(780, 580)
        self.presets = load_presets()
        self.history = []

        self._build_ui()

    def _build_ui(self):
        # Top frame: Base URL
        top = ttk.LabelFrame(self, text="1) 랜딩페이지 URL")
        top.pack(fill="x", padx=12, pady=(12, 8))

        self.base_var = tk.StringVar()
        ttk.Label(top, text="URL 원본").grid(row=0, column=0, padx=8, pady=8, sticky="w")
        self.base_entry = ttk.Entry(top, textvariable=self.base_var, width=90)
        self.base_entry.grid(row=0, column=1, padx=8, pady=8, sticky="we")
        top.grid_columnconfigure(1, weight=1)

        # Middle frame: UTM core
        mid = ttk.LabelFrame(self, text="2) UTM 파라미터 입력하기")
        mid.pack(fill="x", padx=12, pady=8)

        self.vars_core = {
            "utm_source": tk.StringVar(),
            "utm_medium": tk.StringVar(),
            "utm_campaign": tk.StringVar(),
            "utm_term": tk.StringVar(),
            "utm_content": tk.StringVar(),
        }

        row = 0
        for key, label in [
            ("utm_source", "utm_source*"),
            ("utm_medium", "utm_medium*"),
            ("utm_campaign", "utm_campaign*"),
            ("utm_term", "utm_term"),
            ("utm_content", "utm_content"),
        ]:
            ttk.Label(mid, text=label).grid(row=row, column=0, padx=8, pady=6, sticky="w")
            ttk.Entry(mid, textvariable=self.vars_core[key], width=40).grid(row=row, column=1, padx=8, pady=6, sticky="we")
            row += 1
        mid.grid_columnconfigure(1, weight=1)

        # Advanced GA4 optional
        self.adv_frame = ttk.LabelFrame(self, text="3) UTM 파라미터 - 안붙여도 됩니다!(옵션임)")
        self.adv_frame.pack(fill="x", padx=12, pady=8)

        self.vars_adv = {k: tk.StringVar() for k in GA4_OPTIONAL_KEYS}
        row = 0
        for k in GA4_OPTIONAL_KEYS:
            ttk.Label(self.adv_frame, text=k).grid(row=row, column=0, padx=8, pady=4, sticky="w")
            ttk.Entry(self.adv_frame, textvariable=self.vars_adv[k], width=40).grid(row=row, column=1, padx=8, pady=4, sticky="we")
            row += 1
        self.adv_frame.grid_columnconfigure(1, weight=1)

        # Options frame
        opts = ttk.LabelFrame(self, text="4) 생성기 옵션")
        opts.pack(fill="x", padx=12, pady=8)

        self.force_lower = tk.BooleanVar(value=True)
        self.merge_existing = tk.BooleanVar(value=True)
        self.override_existing = tk.BooleanVar(value=True)
        self.space_mode = tk.StringVar(value="underscore")

        ttk.Checkbutton(opts, text="강제 소문자 입력", variable=self.force_lower).grid(row=0, column=0, padx=8, pady=6, sticky="w")
        ttk.Checkbutton(opts, text="현재 쿼리에 적용할 것인지 여부", variable=self.merge_existing).grid(row=0, column=1, padx=8, pady=6, sticky="w")
        ttk.Checkbutton(opts, text="중복 키 포함 여부", variable=self.override_existing).grid(row=0, column=2, padx=8, pady=6, sticky="w")

        ttk.Label(opts, text="공백 처리: ").grid(row=1, column=0, padx=8, pady=6, sticky="e")
        for i, (label, val) in enumerate([("underscore _", "underscore"), ("dash -", "dash"), ("keep (encode)", "keep")]):
            ttk.Radiobutton(opts, text=label, value=val, variable=self.space_mode).grid(row=1, column=1+i, padx=6, pady=6, sticky="w")

        # Presets frame
        presets_frame = ttk.LabelFrame(self, text="5) 프레셋")
        presets_frame.pack(fill="x", padx=12, pady=8)

        self.preset_combo = ttk.Combobox(presets_frame, values=sorted(self.presets.keys()), state="readonly", width=40)
        self.preset_combo.grid(row=0, column=0, padx=8, pady=8, sticky="w")
        ttk.Button(presets_frame, text="프리셋 정보 불러오기", command=self.on_load_preset).grid(row=0, column=1, padx=6, pady=8)
        ttk.Button(presets_frame, text="프리셋 저장", command=self.on_save_preset).grid(row=0, column=2, padx=6, pady=8)
        ttk.Button(presets_frame, text="프리셋 삭제", command=self.on_delete_preset).grid(row=0, column=3, padx=6, pady=8)
        presets_frame.grid_columnconfigure(4, weight=1)

        # Output frame
        out = ttk.LabelFrame(self, text="6) 아웃풋")
        out.pack(fill="both", expand=True, padx=12, pady=(8, 12))

        self.output_var = tk.StringVar()
        self.output_entry = ttk.Entry(out, textvariable=self.output_var, width=100)
        self.output_entry.grid(row=0, column=0, columnspan=5, padx=8, pady=8, sticky="we")
        out.grid_columnconfigure(0, weight=1)

        ttk.Button(out, text="UTM 생성하기", command=self.on_generate).grid(row=1, column=0, padx=8, pady=6, sticky="w")
        ttk.Button(out, text="복사", command=self.on_copy).grid(row=1, column=1, padx=8, pady=6, sticky="w")
        ttk.Button(out, text="브라우저에서 열어보기", command=self.on_open).grid(row=1, column=2, padx=8, pady=6, sticky="w")
        ttk.Button(out, text="초기화", command=self.on_reset).grid(row=1, column=3, padx=8, pady=6, sticky="w")
        ttk.Button(out, text="CSV로 내보내기", command=self.on_export_history).grid(row=1, column=4, padx=8, pady=6, sticky="e")

        ttk.Label(out, text="히스토리(최신순)").grid(row=2, column=0, columnspan=5, padx=8, pady=(8, 4), sticky="w")
        self.history_list = tk.Listbox(out, height=8)
        self.history_list.grid(row=3, column=0, columnspan=5, padx=8, pady=(0, 8), sticky="nsew")
        out.grid_rowconfigure(3, weight=1)

        self.history_list.bind("<Double-1>", self.on_history_double_click)

        # Footer
        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Label(footer, text="Tip: Required fields marked with *").pack(side="left")
        ttk.Button(footer, text="종료하기", command=self.destroy).pack(side="right")

        # macOS menu-ish shortcuts
        self.bind_all("<Command-c>", lambda e: self.on_copy())
        self.bind_all("<Command-Return>", lambda e: self.on_generate())

    def _collect_pairs(self):
        pairs = {}
        for k, var in self.vars_core.items():
            v = var.get().strip()
            if v:
                pairs[k] = v
        for k, var in self.vars_adv.items():
            v = var.get().strip()
            if v:
                pairs[k] = v
        return pairs

    def _validate_required(self, pairs):
        missing = [rk for rk in REQUIRED_KEYS if not pairs.get(rk)]
        return missing

    def on_generate(self):
        base = self.base_var.get().strip()
        pairs = self._collect_pairs()

        missing = self._validate_required(pairs)
        if missing:
            if not base:
                # If even base is empty, point it out clearly
                messagebox.showwarning("Missing", f"Base URL + required fields are needed:\n- Base URL\n- " + ", ".join(REQUIRED_KEYS))
                return
            else:
                if not messagebox.askyesno("Proceed?", f"Missing required fields: {', '.join(missing)}\nGenerate anyway?"):
                    return
        try:
            url = build_utm_url(
                base,
                pairs,
                force_lower=self.force_lower.get(),
                space_mode=self.space_mode.get(),
                merge_existing=self.merge_existing.get(),
                override_existing=self.override_existing.get(),
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate URL:\n{e}")
            return

        self.output_var.set(url)
        self._add_history(url)

    def on_copy(self):
        url = self.output_var.get().strip()
        if not url:
            self.on_generate()
            url = self.output_var.get().strip()
        if not url:
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(url)
            self.update()  # now it stays on macOS after app closes
            messagebox.showinfo("Copied", "URL copied to clipboard.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy:\n{e}")

    def on_open(self):
        url = self.output_var.get().strip()
        if not url:
            self.on_generate()
            url = self.output_var.get().strip()
        if not url:
            return
        try:
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open browser:\n{e}")

    def on_reset(self):
        self.base_var.set("")
        for var in self.vars_core.values():
            var.set("")
        for var in self.vars_adv.values():
            var.set("")
        self.output_var.set("")

    def on_save_preset(self):
        name = simpledialog.askstring("Preset name", "Enter a name for this preset:")
        if not name:
            return
        pairs = self._collect_pairs()
        self.presets[name] = pairs
        save_presets(self.presets)
        self.preset_combo.configure(values=sorted(self.presets.keys()))
        self.preset_combo.set(name)
        messagebox.showinfo("Saved", f"Preset '{name}' saved.")

    def on_load_preset(self):
        name = self.preset_combo.get().strip()
        if not name or name not in self.presets:
            messagebox.showwarning("No preset", "Select a preset to load.")
            return
        pairs = self.presets[name]
        # clear first
        for var in self.vars_core.values():
            var.set("")
        for var in self.vars_adv.values():
            var.set("")
        # apply
        for k, v in pairs.items():
            if k in self.vars_core:
                self.vars_core[k].set(v)
            elif k in self.vars_adv:
                self.vars_adv[k].set(v)
        messagebox.showinfo("Loaded", f"Preset '{name}' loaded.")

    def on_delete_preset(self):
        name = self.preset_combo.get().strip()
        if not name or name not in self.presets:
            messagebox.showwarning("No preset", "Select a preset to delete.")
            return
        if messagebox.askyesno("Delete", f"Delete preset '{name}'?"):
            del self.presets[name]
            save_presets(self.presets)
            self.preset_combo.configure(values=sorted(self.presets.keys()))
            self.preset_combo.set("")
            messagebox.showinfo("Deleted", f"Preset '{name}' deleted.")

    def _add_history(self, url):
        # De-dup & push to top
        if url in self.history:
            self.history.remove(url)
        self.history.insert(0, url)
        del self.history[HISTORY_LIMIT:]
        self._refresh_history_listbox()

    def _refresh_history_listbox(self):
        self.history_list.delete(0, tk.END)
        for u in self.history:
            self.history_list.insert(tk.END, u)

    def on_history_double_click(self, _event=None):
        sel = self.history_list.curselection()
        if not sel:
            return
        url = self.history_list.get(sel[0])
        self.output_var.set(url)

    def on_export_history(self):
        if not self.history:
            messagebox.showwarning("Empty", "No history to export.")
            return
        path = filedialog.asksaveasfilename(
            title="Export history to CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")]
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("url\n")
                for u in self.history:
                    # quote for CSV-safe with simple replace (no csv module needed)
                    f.write('"{}"\n'.format(u.replace('"', '""')))
            messagebox.showinfo("Exported", f"History exported to:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export history:\n{e}")

def main():
    # High DPI on mac (Tk 8.6+)
    if sys.platform == "darwin":
        try:
            from ctypes import cdll
            appservices = cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
            # No-op; just ensure framework loads (some Tk builds need it)
        except Exception:
            pass

    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()
