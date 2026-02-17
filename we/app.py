import tkinter as tk
from tkinter import ttk

from .config import BG
from .theme import apply_theme
from .db import DB
from .tabs_ingredients import IngredientsTab
from .tabs_products import ProductsTab


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Wareneinsatz Tracker")
        self.geometry("1100x700")
        self.resizable(True, True)

        apply_theme(self)

        self.db = DB()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._root_container = tk.Frame(self, bg=BG, bd=0, highlightthickness=0)
        self._root_container.pack(fill="both", expand=True)

        self.notebook = ttk.Notebook(self._root_container, style="Custom.TNotebook")
        self.notebook.pack(fill="both", expand=True)

        self.tab_prod = tk.Frame(self.notebook, bg=BG, bd=0, highlightthickness=0)
        self.tab_ing = tk.Frame(self.notebook, bg=BG, bd=0, highlightthickness=0)

        self.notebook.add(self.tab_prod, text="Produkte")
        self.notebook.add(self.tab_ing, text="Zutaten")

        # Zutaten Tab fertig
        self.ingredients_tab = IngredientsTab(self, self.tab_ing, self.db, on_any_change=self.refresh_all)

        self.products_tab = ProductsTab(self, self.tab_prod, self.db, on_any_change=self.refresh_all)

        self.refresh_all()

    def refresh_all(self):
        self.ingredients_tab.refresh()
        self.products_tab.refresh()

    def on_close(self):
        try:
            self.db.close()
        finally:
            self.destroy()