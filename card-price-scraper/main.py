"""
Card Price Scraper - GUI tool for fetching Pokemon, MTG, and One Piece card prices.
Requires Python 3.10+ on Windows (tkinter included by default).

Usage:
  python main.py
  or double-click run.bat
"""
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

# Ensure local imports work when launched via batch file
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers import pokemon, mtg, onepiece
from exporter import export_to_csv, export_new_csv


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

COLUMNS = [
    ("game", "ゲーム", 80),
    ("name", "カード名", 200),
    ("set", "セット名", 160),
    ("number", "No.", 60),
    ("rarity", "レアリティ", 90),
    ("price_type", "価格種別", 100),
    ("price_market_usd", "相場($)", 80),
    ("price_low_usd", "最安値($)", 80),
    ("price_eur", "相場(€)", 80),
    ("currency", "通貨", 60),
    ("source_url", "URL", 200),
]

COL_KEYS = [c[0] for c in COLUMNS]


# --------------------------------------------------------------------------- #
# Main Application
# --------------------------------------------------------------------------- #

class CardPriceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("カード相場スクレイパー")
        self.geometry("1100x680")
        self.resizable(True, True)
        self.configure(bg="#f4f4f4")

        self._results: list[dict] = []
        self._build_ui()

    # ---------------------------------------------------------------------- #
    # UI construction
    # ---------------------------------------------------------------------- #

    def _build_ui(self):
        # ── Top search bar ─────────────────────────────────────────────────
        top = tk.Frame(self, bg="#2c3e50", pady=8)
        top.pack(fill="x")

        tk.Label(top, text="カード相場スクレイパー", bg="#2c3e50", fg="white",
                 font=("Meiryo UI", 14, "bold")).pack(side="left", padx=12)

        # Game selector
        self._game_var = tk.StringVar(value="Pokemon")
        games = ["Pokemon", "MTG", "OnePiece", "全て"]
        game_menu = ttk.Combobox(top, textvariable=self._game_var, values=games,
                                  width=10, state="readonly")
        game_menu.pack(side="left", padx=6)

        # Search field
        self._query_var = tk.StringVar()
        tk.Label(top, text="検索:", bg="#2c3e50", fg="white").pack(side="left", padx=(12, 4))
        entry = tk.Entry(top, textvariable=self._query_var, width=30,
                         font=("Meiryo UI", 11))
        entry.pack(side="left", padx=4)
        entry.bind("<Return>", lambda _: self._start_search())

        # Pokemon API Key (optional)
        tk.Label(top, text="PokeAPIキー(任意):", bg="#2c3e50", fg="#aaa",
                 font=("Meiryo UI", 9)).pack(side="left", padx=(16, 2))
        self._api_key_var = tk.StringVar()
        tk.Entry(top, textvariable=self._api_key_var, width=22, show="*",
                 font=("Meiryo UI", 9)).pack(side="left", padx=2)

        search_btn = tk.Button(top, text="検索", command=self._start_search,
                               bg="#27ae60", fg="white", font=("Meiryo UI", 10, "bold"),
                               relief="flat", padx=12)
        search_btn.pack(side="left", padx=10)

        # ── Status bar ─────────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="カード名を入力して検索してください。")
        status_bar = tk.Label(self, textvariable=self._status_var, bg="#ecf0f1",
                               anchor="w", font=("Meiryo UI", 9))
        status_bar.pack(fill="x", side="bottom")

        # ── Bottom export bar ──────────────────────────────────────────────
        bottom = tk.Frame(self, bg="#f4f4f4", pady=6)
        bottom.pack(fill="x", side="bottom")

        self._append_var = tk.BooleanVar(value=False)
        tk.Checkbutton(bottom, text="既存ファイルに追記", variable=self._append_var,
                       bg="#f4f4f4").pack(side="left", padx=10)

        tk.Button(bottom, text="CSVエクスポート", command=self._export_csv,
                  bg="#2980b9", fg="white", font=("Meiryo UI", 10, "bold"),
                  relief="flat", padx=14).pack(side="left", padx=4)

        tk.Button(bottom, text="結果をクリア", command=self._clear_results,
                  bg="#95a5a6", fg="white", font=("Meiryo UI", 10),
                  relief="flat", padx=10).pack(side="left", padx=4)

        self._count_var = tk.StringVar(value="0件")
        tk.Label(bottom, textvariable=self._count_var, bg="#f4f4f4",
                 font=("Meiryo UI", 10)).pack(side="right", padx=12)

        # ── Progress bar ───────────────────────────────────────────────────
        self._progress = ttk.Progressbar(self, mode="indeterminate")
        self._progress.pack(fill="x", side="bottom")

        # ── Results table ──────────────────────────────────────────────────
        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        self._tree = ttk.Treeview(frame, columns=COL_KEYS, show="headings",
                                   selectmode="extended")

        for key, label, width in COLUMNS:
            self._tree.heading(key, text=label,
                                command=lambda k=key: self._sort_column(k))
            self._tree.column(key, width=width, minwidth=40)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        # Row color alternation
        self._tree.tag_configure("oddrow", background="#f9f9f9")
        self._tree.tag_configure("evenrow", background="#ffffff")

    # ---------------------------------------------------------------------- #
    # Search
    # ---------------------------------------------------------------------- #

    def _start_search(self):
        query = self._query_var.get().strip()
        if not query:
            messagebox.showwarning("入力エラー", "カード名を入力してください。")
            return

        game = self._game_var.get()
        self._set_status(f'"{query}" を検索中...')
        self._progress.start(10)

        thread = threading.Thread(target=self._fetch_thread,
                                  args=(query, game), daemon=True)
        thread.start()

    def _fetch_thread(self, query: str, game: str):
        results = []
        errors = []

        try:
            if game in ("Pokemon", "全て"):
                api_key = self._api_key_var.get().strip()
                self._set_status("Pokemon TCG API を検索中...")
                try:
                    results.extend(pokemon.search_cards(query, api_key=api_key))
                except Exception as e:
                    errors.append(f"Pokemon: {e}")

            if game in ("MTG", "全て"):
                self._set_status("Scryfall API (MTG) を検索中...")
                try:
                    results.extend(mtg.search_cards(query))
                except Exception as e:
                    errors.append(f"MTG: {e}")

            if game in ("OnePiece", "全て"):
                self._set_status("ワンピースカード (TCGPlayer/Cardmarket) を検索中...")
                try:
                    results.extend(onepiece.search_cards(query))
                except Exception as e:
                    errors.append(f"OnePiece: {e}")

        finally:
            self.after(0, self._display_results, results, errors)

    def _display_results(self, results: list[dict], errors: list[str]):
        self._progress.stop()

        self._results.extend(results)
        self._refresh_table()

        status_parts = [f"{len(results)}件取得"]
        if errors:
            status_parts.append(" / エラー: " + "; ".join(errors))
        self._set_status("  ".join(status_parts))

    def _refresh_table(self):
        self._tree.delete(*self._tree.get_children())
        for i, record in enumerate(self._results):
            values = [str(record.get(k, "") or "") for k in COL_KEYS]
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            self._tree.insert("", "end", values=values, tags=(tag,))
        self._count_var.set(f"{len(self._results)}件")

    # ---------------------------------------------------------------------- #
    # Table sorting
    # ---------------------------------------------------------------------- #

    def _sort_column(self, col: str):
        def sort_key(record):
            val = record.get(col, "")
            if val is None:
                return (1, 0)
            try:
                return (0, float(val))
            except (ValueError, TypeError):
                return (0, str(val).lower())

        self._results.sort(key=sort_key)
        self._refresh_table()

    # ---------------------------------------------------------------------- #
    # Export
    # ---------------------------------------------------------------------- #

    def _export_csv(self):
        if not self._results:
            messagebox.showinfo("データなし", "エクスポートするデータがありません。")
            return

        default_name = f"card_prices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV ファイル", "*.csv"), ("全てのファイル", "*.*")],
            initialfile=default_name,
            title="CSVファイルを保存",
        )
        if not filepath:
            return

        try:
            if self._append_var.get():
                export_to_csv(self._results, filepath)
            else:
                export_new_csv(self._results, filepath)

            messagebox.showinfo(
                "エクスポート完了",
                f"{len(self._results)}件のデータを保存しました:\n{filepath}"
            )
            self._set_status(f"CSVエクスポート完了: {filepath}")
        except Exception as e:
            messagebox.showerror("エクスポートエラー", str(e))

    def _clear_results(self):
        self._results.clear()
        self._refresh_table()
        self._set_status("結果をクリアしました。")

    # ---------------------------------------------------------------------- #
    # Helpers
    # ---------------------------------------------------------------------- #

    def _set_status(self, msg: str):
        self._status_var.set(f"  {msg}")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    app = CardPriceApp()
    app.mainloop()
