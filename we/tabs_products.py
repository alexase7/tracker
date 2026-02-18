import tkinter as tk
from tkinter import ttk, messagebox

import webbrowser

from .config import PAGE_SIZE
from .ui_helpers import UIHelpers
from .utils import money, safe_float


class ProductsTab(UIHelpers):
    def __init__(self, app, parent, db, on_any_change):
        self.app = app
        self.parent = parent
        self.db = db
        self.on_any_change = on_any_change

        self.prod_filter = ""
        self.prod_offset = 0
        self.prod_sort_col = "name"
        self.prod_sort_desc = False
        self._products_rows = []

        self._all_ingredient_names = []

        # combobox popdown flags (used so Enter can select from dropdown)
        self._ing_popdown_open = False
        self._slot_popdown_open = False

        self._build()

    # ---------------- build UI ----------------
    def _build(self):
        outer = tk.Frame(self.parent, bg=self.app["bg"], bd=0, highlightthickness=0)
        outer.pack(fill="both", expand=True)
        outer_inner = ttk.Frame(outer, padding=10)
        outer_inner.pack(fill="both", expand=True)

        # --- subtle credit icon (top-right) ---
        self._credit_label = tk.Label(
            self.app,
            text="ⓘ",
            fg="#777777",
            bg=self.app["bg"],
            font=("TkDefaultFont", 16, "bold")
        )
        self._credit_label.place(relx=1.0, rely=0.0, anchor="ne", x=-8, y=2)

        self._credit_label.bind("<Enter>", self._show_credit_tooltip)
        self._credit_label.bind("<Leave>", self._hide_credit_tooltip)
        self._credit_label.bind("<Button-1>", self._open_github)
        self._credit_label.configure(cursor="hand2")

        self.prod_paned = ttk.Panedwindow(
            outer_inner,
            orient="horizontal",
            style="Custom.Panedwindow",
        )
        self.prod_paned.pack(fill="both", expand=True)

        # ensure credit label stays above all content
        try:
            self._credit_label.lift()
            self._credit_label.tkraise()
        except Exception:
            pass

        left = ttk.Frame(self.prod_paned)
        right = ttk.Frame(self.prod_paned)

        try:
            left.configure(borderwidth=0, relief="flat")
            right.configure(borderwidth=0, relief="flat")
        except Exception:
            pass

        self.prod_paned.add(left, weight=1)
        self.prod_paned.add(right, weight=2)

        try:
            self.prod_paned.configure(sashrelief="flat")
        except Exception:
            pass

        def _init_sash():
            try:
                w = max(800, self.app.winfo_width())
                self.prod_paned.sashpos(0, int(w * 0.40))
            except Exception:
                pass

        self.app.after(80, _init_sash)

        # ---------------- Left side ----------------
        topL = ttk.Frame(left)
        topL.pack(fill="x")

        ttk.Label(topL, text="Produktname").grid(row=0, column=0, sticky="w")
        self.prod_name = tk.StringVar()
        self.prod_name_entry = ttk.Entry(topL, textvariable=self.prod_name, width=30)
        self.prod_name_entry.grid(row=1, column=0, rowspan=2, pady=5, sticky="we")

        topL.columnconfigure(0, weight=1)

        ttk.Button(topL, text="Produkt löschen", command=self.delete_selected_product).grid(
            row=1, column=1, padx=(10, 0), pady=(5, 2), sticky="we"
        )
        ttk.Button(topL, text="Produkt hinzufügen / updaten", command=self.add_or_update_product).grid(
            row=2, column=1, padx=(10, 0), pady=(2, 5), sticky="we"
        )

        # Search + paging
        search_row = ttk.Frame(left)
        search_row.pack(fill="x", pady=(0, 4))

        ttk.Label(search_row, text="Suche:").pack(side="left")

        self.prod_search_var = tk.StringVar()
        self.prod_search_entry = ttk.Entry(search_row, textvariable=self.prod_search_var)
        self.prod_search_entry.pack(side="left", padx=(6, 10), fill="x", expand=True)
        self.prod_search_entry.bind("<KeyRelease>", lambda _e: self._on_prod_search_changed())
        self.prod_search_entry.bind("<Down>", self._kb_products_from_search_down)
        self.prod_search_entry.bind("<Up>", self._kb_products_from_search_up)
        self.prod_search_entry.bind("<Return>", self._kb_focus_products_tree_from_search)

        right_controls = ttk.Frame(search_row)
        right_controls.pack(side="right")

        self.prod_page_label = ttk.Label(right_controls, text="")
        self.prod_page_label.pack(side="left", padx=(0, 6))

        ttk.Button(right_controls, text="◀", width=3, command=lambda: self._page_prod(-1)).pack(side="left")
        ttk.Button(right_controls, text="▶", width=3, command=lambda: self._page_prod(+1)).pack(
            side="left", padx=(4, 0)
        )

        cols = ("name", "cost", "profit", "margin")
        self.prod_tree = ttk.Treeview(left, columns=cols, show="headings", height=20, selectmode="browse")

        self.prod_tree.heading("name", text="Produkt", command=lambda: self.sort_products_by("name"))
        self.prod_tree.heading("cost", text="Kosten (WE)", command=lambda: self.sort_products_by("cost"))
        self.prod_tree.heading("profit", text="Gewinn (€)", command=lambda: self.sort_products_by("profit"))
        self.prod_tree.heading("margin", text="Marge (%)", command=lambda: self.sort_products_by("margin"))

        self.prod_tree.column("name", width=220)
        self.prod_tree.column("cost", width=110, anchor="e")
        self.prod_tree.column("profit", width=110, anchor="e")
        self.prod_tree.column("margin", width=90, anchor="e")

        self.prod_tree.pack(fill="both", expand=True)
        self.prod_tree.bind("<<TreeviewSelect>>", self.on_select_product)
        # Persist column widths
        self.persist_tree_columns(self.prod_tree, "tree.prod", ["name", "cost", "profit", "margin"])

        # IMPORTANT: no Up/Down bindings on Treeview itself -> avoid double-step.
        self.prod_tree.bind("<Return>", self._kb_focus_recipe_from_product_tree)
        self.prod_tree.bind("<Next>", self._kb_products_pagedown)    # PageDown
        self.prod_tree.bind("<Prior>", self._kb_products_pageup)     # PageUp
        self.prod_tree.bind("<Delete>", self._kb_delete_selected_product)
        self.prod_tree.bind("<BackSpace>", self._kb_delete_selected_product)

        # Quick jump to recipe area (products -> recipe)
        self.prod_tree.bind("<Right>", self._kb_focus_recipe_from_product_tree)

        # Keyboard on product-name entry
        self.prod_name_entry.bind("<Return>", self._kb_prodname_return)
        self.prod_name_entry.bind("<Down>", self._kb_prodname_down)
        self.prod_name_entry.bind("<Up>", self._kb_prodname_up)
        self.prod_name_entry.bind("<Control-BackSpace>", self._kb_delete_selected_product)
        self.prod_name_entry.bind("<Command-BackSpace>", self._kb_delete_selected_product)
        self.prod_name_entry.bind("<Control-d>", self._kb_delete_selected_product)
        self.prod_name_entry.bind("<Command-d>", self._kb_delete_selected_product)
        self.prod_name_entry.bind("<Escape>", self._kb_clear_product_name)

        # From product name entry, jump to recipe with Ctrl/Cmd+Right (keeps normal cursor movement)
        self.prod_name_entry.bind("<Control-Right>", self._kb_focus_recipe_from_product_tree)
        self.prod_name_entry.bind("<Command-Right>", self._kb_focus_recipe_from_product_tree)

        # ---------------- Right side (recipe) ----------------
        ttk.Label(right, text="Rezept").pack(anchor="w")

        self.recipe_ing = tk.StringVar()
        self.recipe_qty = tk.StringVar()

        self.add_mode = tk.StringVar(value="ING")
        self.slot_name_var = tk.StringVar(value="SPIRIT")

        mode_row = ttk.Frame(right)
        mode_row.pack(fill="x", pady=(8, 6))
        ttk.Label(mode_row, text="Hinzufügen als:").pack(side="left")
        ttk.Radiobutton(
            mode_row, text="Zutat", variable=self.add_mode, value="ING", command=self.on_add_mode_changed
        ).pack(side="left", padx=(10, 0))
        ttk.Radiobutton(
            mode_row, text="Template-Slot", variable=self.add_mode, value="SLOT", command=self.on_add_mode_changed
        ).pack(side="left", padx=(10, 0))

        recipe_top = ttk.Frame(right)
        recipe_top.pack(fill="x", pady=(0, 8))

        self.ing_combo = ttk.Combobox(recipe_top, textvariable=self.recipe_ing, state="normal", width=30)
        self.ing_combo.grid(row=0, column=0, padx=(0, 10))
        self.ing_combo.bind("<KeyRelease>", self.on_ingredient_combo_typed)
        self.ing_combo.bind("<<ComboboxSelected>>", self.on_ingredient_selected)

        self.slot_entry = ttk.Entry(recipe_top, textvariable=self.slot_name_var, width=18)
        self.slot_entry.grid(row=0, column=1, padx=(0, 10))

        self.recipe_qty_entry = ttk.Entry(recipe_top, textvariable=self.recipe_qty, width=12)
        self.recipe_qty_entry.grid(row=0, column=2, padx=(0, 10))

        self.recipe_unit_label = ttk.Label(recipe_top, text="Einheit: –")
        self.recipe_unit_label.grid(row=0, column=3, sticky="w")

        recipe_btns = ttk.Frame(recipe_top)
        recipe_btns.grid(row=0, column=4, padx=(10, 0), sticky="e")

        ttk.Button(recipe_btns, text="Rezept-Position löschen", command=self.delete_selected_recipe_item).pack(
            side="top", fill="x", pady=(0, 4)
        )
        ttk.Button(recipe_btns, text="Zum Rezept hinzufügen", command=self.add_recipe_item).pack(side="top", fill="x")

        # Enter/Tab behavior (fast)
        self.ing_combo.bind("<Return>", self._recipe_enter_from_ingredient)
        self.slot_entry.bind("<Return>", self._recipe_enter_from_slotname)
        self.recipe_qty_entry.bind("<Return>", self._kb_recipe_qty_return)

        self.ing_combo.bind("<Tab>", self._kb_to_qty)
        self.slot_entry.bind("<Tab>", self._kb_to_qty)
        self.recipe_qty_entry.bind("<Tab>", self._kb_qty_tab_add)

        # Arrow nav from fields into recipe list
        # IMPORTANT: do NOT return "break" on Down for combobox, otherwise ttk cannot move selection in popdown.
        self.ing_combo.bind("<Down>", self._kb_ing_combo_down)
        self.ing_combo.bind("<Up>", self._kb_ing_combo_up)

        self.slot_entry.bind("<Down>", self._kb_recipe_tree_down_from_field)
        self.slot_entry.bind("<Up>", self._kb_recipe_tree_up_from_field)

        self.recipe_qty_entry.bind("<Down>", self._kb_recipe_tree_down_from_field)
        self.recipe_qty_entry.bind("<Up>", self._kb_recipe_tree_up_from_field)

        # Left/Right quick navigation inside recipe input
        # Ingredient/slot -> Right to qty
        self.ing_combo.bind("<Right>", self._kb_recipe_right_to_qty)
        self.slot_entry.bind("<Right>", self._kb_recipe_right_to_qty)

        # Ingredient/slot -> Left to products list (only when caret is at start)
        self.ing_combo.bind("<Left>", self._kb_left_from_ing_to_products)
        self.slot_entry.bind("<Left>", self._kb_left_from_ing_to_products)

        # Qty -> Left back to ingredient/slot (only when caret is at start)
        self.recipe_qty_entry.bind("<Left>", self._kb_left_from_qty_to_ing)

        # Qty -> Down OR Right into recipe positions (Right only when caret at end)
        self.recipe_qty_entry.bind("<Right>", self._kb_right_from_qty_to_recipe_tree)

        # Keep an explicit shortcut to go back to the ingredient/slot field from qty if needed
        self.recipe_qty_entry.bind("<Shift-Left>", self._kb_recipe_left_to_ing)

        cols2 = ("ingredient", "qty", "unit", "unit_price", "line_cost")
        self.recipe_tree = ttk.Treeview(right, columns=cols2, show="headings", height=14, selectmode="browse")
        for c, t, w, a in [
            ("ingredient", "Zutat / Slot", 280, "w"),
            ("qty", "Menge", 90, "e"),
            ("unit", "Einheit", 70, "center"),
            ("unit_price", "Preis/Einheit", 150, "e"),
            ("line_cost", "Kosten", 110, "e"),
        ]:
            self.recipe_tree.heading(c, text=t)
            self.recipe_tree.column(c, width=w, anchor=a)
        self.recipe_tree.pack(fill="both", expand=True)
        # Persist column widths
        self.persist_tree_columns(self.recipe_tree, "tree.recipe", ["ingredient", "qty", "unit", "unit_price", "line_cost"])

        # From recipe list, jump back to product list (Left)
        self.recipe_tree.bind("<Left>", self._kb_focus_products_tree)
        self.recipe_tree.bind("<Up>", self._kb_recipe_tree_up)
        self.recipe_tree.bind("<Down>", self._kb_recipe_tree_down)

        # Quick jump back to product list with Ctrl/Cmd+Left from fields
        for w in (self.ing_combo, self.slot_entry, self.recipe_qty_entry):
            w.bind("<Control-Left>", self._kb_focus_products_tree)
            w.bind("<Command-Left>", self._kb_focus_products_tree)

        # Slot selection panel (hidden unless SLOT mode)
        self.slot_panel = ttk.Frame(right)
        self.slot_panel.pack(fill="x", pady=(10, 0))

        ttk.Label(self.slot_panel, text="Template-Slot belegen:").grid(row=0, column=0, sticky="w")
        self.slot_pick = tk.StringVar(value="SPIRIT")
        self.slot_pick_combo = ttk.Combobox(self.slot_panel, textvariable=self.slot_pick, state="readonly", width=18)
        self.slot_pick_combo.grid(row=1, column=0, padx=(0, 10), pady=4, sticky="w")
        self.slot_pick_combo.bind("<<ComboboxSelected>>", lambda _e: self._load_slot_selection_for_selected_product())
        # Slot panel -> recipe list (Up)
        self.slot_pick_combo.bind("<Up>", self._kb_slotpanel_up_to_recipe)

        self.slot_ing_pick = tk.StringVar()
        self.slot_ing_combo = ttk.Combobox(self.slot_panel, textvariable=self.slot_ing_pick, state="normal", width=30)
        self.slot_ing_combo.grid(row=1, column=1, padx=(0, 10), pady=4, sticky="we")
        self.slot_ing_combo.bind("<KeyRelease>", self.on_slot_ingredient_typed)
        self.slot_ing_combo.bind("<Down>", self._kb_slot_combo_down)
        self.slot_ing_combo.bind("<Up>", self._kb_slot_combo_up)

        self.slot_set_btn = ttk.Button(self.slot_panel, text="Setzen", command=self.set_slot_selection)
        self.slot_set_btn.grid(row=1, column=2, pady=4, sticky="e")
        self.slot_panel.columnconfigure(1, weight=1)

        self.slot_ing_combo.bind("<Return>", lambda _e: (self.set_slot_selection(), "break")[1])
        self.slot_pick_combo.bind("<Return>", lambda _e: (self.set_slot_selection(), "break")[1])
        self.slot_ing_combo.bind("<Shift-Tab>", self._kb_slotpanel_up_to_recipe)
        self.slot_pick_combo.bind("<Shift-Tab>", self._kb_slotpanel_up_to_recipe)
        # Slot panel: keep Left/Right inside the slot panel (do not jump into recipe-position fields)
        self.slot_pick_combo.bind("<Right>", self._kb_slotpanel_right_from_pick)
        self.slot_pick_combo.bind("<Left>", self._kb_slotpanel_left_from_pick)
        self.slot_ing_combo.bind("<Left>", self._kb_slotpanel_left_from_ing)
        self.slot_ing_combo.bind("<Right>", self._kb_slotpanel_right_from_ing)

        self.cost_label = ttk.Label(right, text="Kosten: –", font=("TkDefaultFont", 11, "bold"))
        self.cost_label.pack(anchor="e", pady=(10, 0))

        # Selling price / margin panel
        price_row = ttk.Frame(right)
        price_row.pack(fill="x", pady=(8, 0))

        ttk.Label(price_row, text="Verkaufspreis (€):").pack(side="left")
        self.sale_price_var = tk.StringVar()
        self.sale_price_entry = ttk.Entry(price_row, textvariable=self.sale_price_var, width=12)
        self.sale_price_entry.pack(side="left", padx=(8, 12))

        self.profit_label = ttk.Label(right, text="Gewinn: –")
        self.profit_label.pack(anchor="e", pady=(6, 0))

        self.margin_label = ttk.Label(right, text="Marge: –")
        self.margin_label.pack(anchor="e", pady=(2, 0))

        self.sale_price_entry.bind("<Return>", lambda _e: (self.save_sale_price(), "break")[1])
        self.sale_price_entry.bind("<FocusOut>", lambda _e: self.save_sale_price())

        self.on_add_mode_changed()

    # ---------------- keyboard helpers ----------------
    def _select_first_in_tree(self, tree: ttk.Treeview):
        items = tree.get_children()
        if not items:
            return
        first = items[0]
        tree.selection_set(first)
        tree.focus(first)
        tree.see(first)
        try:
            tree.focus_set()
        except Exception:
            pass

    def _kb_products_from_search_down(self, _e=None):
        self._tree_move_selection(self.prod_tree, +1)
        return "break"

    def _kb_products_from_search_up(self, _e=None):
        self._tree_move_selection(self.prod_tree, -1)
        return "break"

    def _kb_focus_products_tree_from_search(self, _e=None):
        self._select_first_in_tree(self.prod_tree)
        return "break"

    def _kb_focus_recipe_from_product_tree(self, _e=None):
        if self.add_mode.get() == "SLOT":
            try:
                self.slot_entry.focus_set()
            except Exception:
                pass
        else:
            try:
                self.ing_combo.focus_set()
                self.ing_combo.icursor(tk.END)
            except Exception:
                pass
        return "break"

    def _kb_products_pagedown(self, _e=None):
        self._page_prod(+1)
        self._select_first_in_tree(self.prod_tree)
        return "break"

    def _kb_products_pageup(self, _e=None):
        self._page_prod(-1)
        self._select_first_in_tree(self.prod_tree)
        return "break"

    def _kb_prodname_return(self, _e=None):
        self.add_or_update_product()

        def _focus_recipe():
            try:
                self._kb_focus_recipe_from_product_tree()
            except Exception:
                pass

        try:
            self.app.after_idle(_focus_recipe)
        except Exception:
            _focus_recipe()

        return "break"

    def _kb_prodname_down(self, _e=None):
        self._tree_move_selection(self.prod_tree, +1)
        return "break"

    def _kb_prodname_up(self, _e=None):
        self._tree_move_selection(self.prod_tree, -1)
        return "break"

    def _kb_clear_product_name(self, _e=None):
        self.prod_name.set("")
        try:
            self.prod_name_entry.focus_set()
        except Exception:
            pass
        return "break"

    def _kb_delete_selected_product(self, _e=None):
        self.delete_selected_product()
        return "break"

    def _kb_focus_products_tree(self, _e=None):
        try:
            self.prod_tree.focus_set()
        except Exception:
            pass
        return "break"

    def _kb_to_qty(self, _e=None):
        try:
            self.recipe_qty_entry.focus_set()
        except Exception:
            pass
        return "break"

    def _kb_qty_tab_add(self, _e=None):
        self.add_recipe_item()
        try:
            self.recipe_qty_entry.focus_set()
        except Exception:
            pass
        return "break"

    def _kb_recipe_qty_return(self, _e=None):
        self.add_recipe_item()
        return "break"

    def _kb_recipe_tree_down_from_field(self, _e=None):
        self._tree_move_selection(self.recipe_tree, +1)
        return "break"

    def _kb_recipe_tree_up_from_field(self, _e=None):
        self._tree_move_selection(self.recipe_tree, -1)
        return "break"

    def _kb_ing_combo_down(self, _e=None):
        # open dropdown but DO NOT "break" -> allow ttk to move selection with arrows
        self._ing_popdown_open = True
        try:
            self._post_combobox(self.ing_combo)
        except Exception:
            pass
        return None

    def _kb_ing_combo_up(self, _e=None):
        # If dropdown is open, let ttk handle Up to move inside the popdown.
        if getattr(self, "_ing_popdown_open", False):
            return None
        return self._kb_recipe_tree_up_from_field(_e)

    def _kb_recipe_right_to_qty(self, _e=None):
        # Move to qty field (works even if the combobox has text)
        try:
            self.recipe_qty_entry.focus_set()
            self.recipe_qty_entry.icursor(tk.END)
        except Exception:
            pass
        return "break"

    def _kb_recipe_left_to_ing(self, _e=None):
        # Move back to ingredient/slot field depending on mode
        try:
            if self.add_mode.get() == "SLOT":
                self.slot_entry.focus_set()
                self.slot_entry.icursor(tk.END)
            else:
                self.ing_combo.focus_set()
                self.ing_combo.icursor(tk.END)
        except Exception:
            pass
        return "break"

    def _kb_left_from_ing_to_products(self, e=None):
        """From ingredient/slot input: Left at start jumps to products list."""
        try:
            w = e.widget
            pos = int(w.index("insert"))
        except Exception:
            return None

        if pos <= 0:
            return self._kb_focus_products_tree(e)

        return None

    def _kb_left_from_qty_to_ing(self, e=None):
        """From qty input: Left at start jumps back to ingredient/slot field."""
        try:
            w = e.widget
            pos = int(w.index("insert"))
        except Exception:
            return None

        if pos <= 0:
            return self._kb_recipe_left_to_ing(e)

        return None

    def _kb_right_from_qty_to_recipe_tree(self, e=None):
        """From qty input: Right at end jumps into recipe list (positions)."""
        try:
            w = e.widget
            txt = w.get() or ""
            pos = int(w.index("insert"))
        except Exception:
            return None

        # only jump if caret is at end, otherwise allow normal cursor movement
        if pos < len(txt):
            return None

        try:
            items = self.recipe_tree.get_children()
        except Exception:
            items = ()

        if items:
            sel = self.recipe_tree.selection()
            if not sel:
                # select last (natural after typing qty)
                last = items[-1]
                self.recipe_tree.selection_set(last)
                self.recipe_tree.focus(last)
                self.recipe_tree.see(last)
            try:
                self.recipe_tree.focus_set()
            except Exception:
                pass
        else:
            try:
                self.recipe_tree.focus_set()
            except Exception:
                pass

        return "break"

    def _kb_left_from_recipe_field_to_tree(self, e=None):
        """From recipe input fields: if caret is at position 0, jump back to recipe list."""
        w = None
        try:
            w = e.widget
        except Exception:
            w = None

        # Determine caret position; if we can't, do nothing special.
        pos = None
        try:
            # ttk.Entry / ttk.Combobox support index('insert')
            pos = int(w.index("insert"))
        except Exception:
            pos = None

        # Only jump if caret is at the far left (start of text)
        if pos is not None and pos <= 0:
            try:
                items = self.recipe_tree.get_children()
            except Exception:
                items = ()

            if items:
                # Keep current selection if any; otherwise select last row (natural when coming from fields)
                sel = self.recipe_tree.selection()
                if not sel:
                    last = items[-1]
                    self.recipe_tree.selection_set(last)
                    self.recipe_tree.focus(last)
                    self.recipe_tree.see(last)

                try:
                    self.recipe_tree.focus_set()
                except Exception:
                    pass
            else:
                # Empty recipe: just focus the list anyway
                try:
                    self.recipe_tree.focus_set()
                except Exception:
                    pass

            return "break"

        # caret not at start -> allow normal left-arrow editing
        return None

    def _kb_recipe_tree_up(self, _e=None):
        # Move up inside recipe list; when at the top, jump to qty input.
        try:
            items = self.recipe_tree.get_children()
        except Exception:
            items = ()

        if not items:
            try:
                self.recipe_qty_entry.focus_set()
                self.recipe_qty_entry.icursor(tk.END)
            except Exception:
                pass
            return "break"

        sel = self.recipe_tree.selection()
        if not sel:
            # No selection -> go to qty input (user likely wants to edit/add)
            try:
                self.recipe_qty_entry.focus_set()
                self.recipe_qty_entry.icursor(tk.END)
            except Exception:
                pass
            return "break"

        current = sel[0]
        try:
            idx = list(items).index(current)
        except ValueError:
            idx = 0

        if idx <= 0:
            # At first row -> jump to qty input
            try:
                self.recipe_qty_entry.focus_set()
                self.recipe_qty_entry.icursor(tk.END)
            except Exception:
                pass
            return "break"

        # Otherwise move selection one row up
        self._tree_move_selection(self.recipe_tree, -1)
        return "break"

    def _kb_recipe_tree_down(self, _e=None):
        try:
            items = self.recipe_tree.get_children()
        except Exception:
            items = ()

        if not items:
            return "break"

        sel = self.recipe_tree.selection()
        if not sel:
            first = items[0]
            self.recipe_tree.selection_set(first)
            self.recipe_tree.focus(first)
            self.recipe_tree.see(first)
            try:
                self.recipe_tree.focus_set()
            except Exception:
                pass
            return "break"

        self._tree_move_selection(self.recipe_tree, +1)
        return "break"

    def _accept_ing_combo_selection(self):
        """Accept current/first suggestion from ingredient combobox."""
        try:
            values = list(self.ing_combo.cget("values") or [])
        except Exception:
            values = []

        if not values:
            return False

        # If there is a highlighted item (after arrow navigation), take that.
        idx = -1
        try:
            idx = int(self.ing_combo.current())
        except Exception:
            idx = -1

        pick = None
        if 0 <= idx < len(values):
            pick = values[idx]
        else:
            # Otherwise take the first suggestion.
            pick = values[0]

        if not pick:
            return False

        self.recipe_ing.set(pick)
        self._ing_popdown_open = False
        try:
            self._unpost_combobox(self.ing_combo)
        except Exception:
            pass

        self.on_ingredient_selected()
        return True

    def _kb_slot_combo_down(self, _e=None):
        self._slot_popdown_open = True
        try:
            self._post_combobox(self.slot_ing_combo)
        except Exception:
            pass
        return None

    def _kb_slot_combo_up(self, _e=None):
        # If dropdown is open, let ttk handle Up to move inside the popdown.
        if getattr(self, "_slot_popdown_open", False):
            return None
        return self._kb_slotpanel_up_to_recipe(_e)

    def _kb_slotpanel_up_to_recipe(self, _e=None):
        """Move from slot panel back into the recipe list with Up/Shift-Tab."""
        try:
            items = self.recipe_tree.get_children()
        except Exception:
            items = ()

        if items:
            sel = self.recipe_tree.selection()
            if sel:
                # move one up from current selection
                self._tree_move_selection(self.recipe_tree, -1)
            else:
                # select the last row (natural when coming from below)
                last = items[-1]
                self.recipe_tree.selection_set(last)
                self.recipe_tree.focus(last)
                self.recipe_tree.see(last)

            try:
                self.recipe_tree.focus_set()
            except Exception:
                pass
        else:
            # if recipe is empty, go back to the main recipe input
            try:
                if self.add_mode.get() == "SLOT":
                    self.slot_entry.focus_set()
                else:
                    self.ing_combo.focus_set()
            except Exception:
                pass

        return "break"

    def _kb_slotpanel_right_from_pick(self, e=None):
        """From slot-pick combobox: Right at end jumps to slot-ingredient combobox."""
        try:
            w = e.widget
        except Exception:
            return None

        try:
            txt = w.get() or ""
            pos = int(w.index("insert"))
        except Exception:
            return None

        # Only jump if caret is at the end (otherwise allow normal cursor movement)
        if pos >= len(txt):
            try:
                self.slot_ing_combo.focus_set()
                self.slot_ing_combo.icursor(0)
            except Exception:
                pass
            return "break"
        return None

    def _kb_slotpanel_left_from_pick(self, e=None):
        """From slot-pick combobox: keep Left inside panel (avoid jumping to recipe fields)."""
        try:
            w = e.widget
            pos = int(w.index("insert"))
        except Exception:
            # If we can't read caret, still prevent focus-jump
            return "break"

        # If at start, consume so focus doesn't jump elsewhere
        if pos <= 0:
            return "break"
        return None

    def _kb_slotpanel_left_from_ing(self, e=None):
        """From slot-ingredient combobox: Left at start jumps back to slot-pick combobox."""
        try:
            w = e.widget
        except Exception:
            return None

        try:
            pos = int(w.index("insert"))
        except Exception:
            return None

        if pos <= 0:
            try:
                self.slot_pick_combo.focus_set()
                # caret at end feels natural when going back
                try:
                    t = self.slot_pick_combo.get() or ""
                    self.slot_pick_combo.icursor(len(t))
                except Exception:
                    pass
            except Exception:
                pass
            return "break"
        return None

    def _kb_slotpanel_right_from_ing(self, e=None):
        """From slot-ingredient combobox: Right at end jumps to Setzen button."""
        try:
            w = e.widget
        except Exception:
            return None

        try:
            txt = w.get() or ""
            pos = int(w.index("insert"))
        except Exception:
            return None

        if pos >= len(txt):
            try:
                self.slot_set_btn.focus_set()
            except Exception:
                pass
            return "break"
        return None

    # ---------------- public refresh ----------------
    def refresh(self):
        self._all_ingredient_names = self.db.list_ingredient_names()
        self.ing_combo["values"] = self._all_ingredient_names
        self.slot_ing_combo["values"] = self._all_ingredient_names

        self.refresh_products()

        pid = self._get_selected_product_id()
        if pid is not None:
            self.refresh_recipe(pid)
            self._refresh_slot_lists(pid)
            self.load_sale_price_for_product(pid)
            self._update_margin_display(pid)

    # ---------------- sorting ----------------
    def sort_products_by(self, col: str):
        if getattr(self, "prod_sort_col", "name") == col:
            self.prod_sort_desc = not getattr(self, "prod_sort_desc", False)
        else:
            self.prod_sort_col = col
            self.prod_sort_desc = False
        self.refresh_products()

    def _product_sort_key(self, row, col: str):
        _pid, name, cost, sale_price, profit, margin = row
        if col == "name":
            return (name or "").lower()
        if col == "cost":
            return float(cost or 0.0)
        if col == "profit":
            return float(profit) if profit is not None else float("-inf")
        if col == "margin":
            return float(margin) if margin is not None else float("-inf")
        return (name or "").lower()

    # ---------------- products list ----------------
    def _on_prod_search_changed(self):
        self.prod_filter = (self.prod_search_var.get() or "").strip()
        self.prod_offset = 0
        self.refresh_products()

    def _page_prod(self, direction: int):
        rows = getattr(self, "_products_rows", [])
        f = (self.prod_filter or "").strip().lower()
        if f:
            rows = [r for r in rows if f in (r[1] or "").lower()]
        total = len(rows)
        if total <= PAGE_SIZE:
            self.prod_offset = 0
        else:
            self.prod_offset = max(0, min(self.prod_offset + direction * PAGE_SIZE, max(0, total - PAGE_SIZE)))
        self.refresh_products()

    def refresh_products(self):
        sel = self.prod_tree.selection()
        selected_pid = int(sel[0]) if sel else None

        products = self.db.list_products()

        costs = {pid: 0.0 for pid, _, _ in products}
        cur = self.db.conn.cursor()

        cur.execute(
            """
            SELECT pi.product_id, SUM(pi.qty * (i.pack_price / i.pack_qty))
            FROM product_items pi
            JOIN ingredients i ON i.id = pi.ingredient_id
            GROUP BY pi.product_id;
            """
        )
        for pid, s in cur.fetchall():
            costs[int(pid)] += float(s or 0.0)

        cur.execute(
            """
            SELECT sl.product_id, SUM(sl.qty * (i.pack_price / i.pack_qty))
            FROM product_slot_lines sl
            JOIN product_slot_selection ss
              ON ss.product_id = sl.product_id AND ss.slot_name = sl.slot_name
            JOIN ingredients i ON i.id = ss.ingredient_id
            GROUP BY sl.product_id;
            """
        )
        for pid, s in cur.fetchall():
            costs[int(pid)] += float(s or 0.0)

        rows_all = []
        for pid, name, sale_price in products:
            cost = float(costs.get(pid, 0.0))
            if sale_price is None:
                profit = None
                margin = None
            else:
                sp = float(sale_price)
                profit = sp - cost
                margin = (profit / sp * 100.0) if sp > 0 else 0.0
            rows_all.append((pid, name, cost, sale_price, profit, margin))

        self._products_rows = rows_all
        rows = list(rows_all)

        f = (self.prod_filter or "").strip().lower()
        if f:
            rows = [r for r in rows if f in (r[1] or "").lower()]

        sort_col = getattr(self, "prod_sort_col", "name")
        desc = getattr(self, "prod_sort_desc", False)
        rows.sort(key=lambda r: self._product_sort_key(r, sort_col), reverse=desc)

        total = len(rows)
        if total <= PAGE_SIZE:
            self.prod_offset = 0
        else:
            self.prod_offset = max(0, min(self.prod_offset, max(0, total - PAGE_SIZE)))

        page = rows[self.prod_offset : self.prod_offset + PAGE_SIZE]

        for r in self.prod_tree.get_children():
            self.prod_tree.delete(r)

        for pid, name, cost, _sale_price, profit, margin in page:
            profit_txt = money(profit) if profit is not None else "–"
            margin_txt = f"{margin:.1f} %" if margin is not None else "–"
            self.prod_tree.insert("", "end", iid=str(pid), values=(name, money(cost), profit_txt, margin_txt))

        if selected_pid is not None and self.prod_tree.exists(str(selected_pid)):
            self.prod_tree.selection_set(str(selected_pid))
            self.prod_tree.focus(str(selected_pid))
            self.prod_tree.see(str(selected_pid))
        else:
            items = self.prod_tree.get_children()
            if items:
                first = items[0]
                self.prod_tree.selection_set(first)
                self.prod_tree.focus(first)
                self.prod_tree.see(first)

        start = self.prod_offset + 1 if total else 0
        end = min(self.prod_offset + PAGE_SIZE, total)
        self.prod_page_label.config(text=f"{start}–{end} von {total}")

    def add_or_update_product(self):
        name = self.prod_name.get().strip()
        if not name:
            messagebox.showerror("Fehler", "Bitte Produktname angeben.")
            return

        self.db.upsert_product(name)
        self.refresh_products()
        self._select_product_by_name(name)

    def _select_product_by_name(self, name: str):
        for iid in self.prod_tree.get_children():
            if self.prod_tree.item(iid, "values")[0] == name:
                self.prod_tree.selection_set(iid)
                self.prod_tree.focus(iid)
                self.prod_tree.see(iid)
                self.on_select_product(None)
                return

    def delete_selected_product(self):
        pid = self._get_selected_product_id()
        if pid is None:
            messagebox.showinfo("Info", "Bitte ein Produkt auswählen.")
            return

        pname = self.prod_tree.item(str(pid), "values")[0]
        if not messagebox.askyesno("Bestätigen", f"Produkt '{pname}' wirklich löschen?"):
            return

        self.db.delete_product(pid)
        self.prod_name.set("")
        self.refresh_products()
        self.on_select_product(None)

    def _get_selected_product_id(self):
        sel = self.prod_tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except Exception:
            return None

    def on_select_product(self, _):
        pid = self._get_selected_product_id()
        if pid is None:
            self.recipe_tree.delete(*self.recipe_tree.get_children())
            self.cost_label.config(text="Kosten: –")
            self.recipe_unit_label.config(text="Einheit: –")
            self.slot_pick_combo["values"] = []
            self.slot_pick.set("")
            self.slot_ing_pick.set("")
            self.sale_price_var.set("")
            self.profit_label.config(text="Gewinn: –")
            self.margin_label.config(text="Marge: –")
            return

        name = self.db.get_product_name(pid)
        if name:
            self.prod_name.set(name)

        self.refresh_recipe(pid)
        self._refresh_slot_lists(pid)
        self.load_sale_price_for_product(pid)
        self._update_margin_display(pid)

    # ---------------- sale price / margin ----------------
    def load_sale_price_for_product(self, pid: int):
        price = self.db.get_sale_price(pid)
        if price is None:
            self.sale_price_var.set("")
        else:
            self.sale_price_var.set(f"{float(price):.2f}")

    def save_sale_price(self):
        pid = self._get_selected_product_id()
        if pid is None:
            return

        txt = (self.sale_price_var.get() or "").strip()
        if txt == "":
            self.db.set_sale_price(pid, None)
            self._update_margin_display(pid)
            self.refresh_products()
            return

        val = safe_float(txt)
        if val is None or val < 0:
            return

        self.db.set_sale_price(pid, float(val))
        self.sale_price_var.set(f"{float(val):.2f}")
        self._update_margin_display(pid)
        self.refresh_products()

    def _update_margin_display(self, pid: int):
        cost = self.db.compute_product_cost(pid)
        price = self.db.get_sale_price(pid)

        if price is None:
            self.profit_label.config(text="Gewinn: –")
            self.margin_label.config(text="Marge: –")
            return

        profit = float(price) - cost
        margin_pct = (profit / float(price) * 100.0) if float(price) > 0 else 0.0

        self.profit_label.config(text=f"Gewinn: {money(profit)}")
        self.margin_label.config(text=f"Marge: {margin_pct:.1f} %")

    # ---------------- autocomplete / ingredient resolve ----------------
    def _resolve_ingredient_name(self, typed_name: str):
        t = (typed_name or "").strip().lower()
        if not t:
            return None

        names = self._all_ingredient_names or []
        for n in names:
            if n.lower() == t:
                return n

        matches = [n for n in names if t in n.lower()]
        if len(matches) == 1:
            return matches[0]
        return None

    def on_ingredient_combo_typed(self, event=None):
        if event is not None and getattr(event, "keysym", "") in {"Up", "Down", "Return", "Tab", "Escape"}:
            return

        typed_raw = self.recipe_ing.get() or ""
        typed = typed_raw.strip().lower()
        names = self._all_ingredient_names or []
        if not names:
            return

        if not typed:
            self.ing_combo["values"] = names
            self._ing_popdown_open = False
            self._unpost_combobox(self.ing_combo)
        else:
            filtered = [n for n in names if n.lower().startswith(typed)]
            self.ing_combo["values"] = filtered
            if filtered:
                self._ing_popdown_open = True
                self.app.after_idle(lambda: self._ensure_combo_dropdown(self.ing_combo))
            else:
                self._ing_popdown_open = False
                self._unpost_combobox(self.ing_combo)

    def on_slot_ingredient_typed(self, event=None):
        if event is not None and getattr(event, "keysym", "") in {"Up", "Down", "Return", "Tab", "Escape"}:
            return

        typed_raw = self.slot_ing_pick.get() or ""
        typed = typed_raw.strip().lower()
        names = self._all_ingredient_names or []
        if not names:
            return

        if not typed:
            self.slot_ing_combo["values"] = names
            self._slot_popdown_open = False
            self._unpost_combobox(self.slot_ing_combo)
        else:
            filtered = [n for n in names if n.lower().startswith(typed)]
            self.slot_ing_combo["values"] = filtered
            if filtered:
                self._slot_popdown_open = True
                self.app.after_idle(lambda: self._ensure_combo_dropdown(self.slot_ing_combo))
            else:
                self._slot_popdown_open = False
                self._unpost_combobox(self.slot_ing_combo)

    def on_ingredient_selected(self, _event=None):
        self._ing_popdown_open = False
        name = (self.recipe_ing.get() or "").strip()
        if not name:
            self.recipe_unit_label.config(text="Einheit: –")
            return
        unit = self.db.get_ingredient_unit_by_name(name)
        self.recipe_unit_label.config(text=f"Einheit: {unit}" if unit else "Einheit: –")

    # ---------------- mode toggle ----------------
    def on_add_mode_changed(self):
        mode = self.add_mode.get()
        if mode == "SLOT":
            self.slot_entry.grid()
            try:
                self.ing_combo.configure(state="disabled")
            except Exception:
                pass
            self.recipe_unit_label.config(text="Einheit: (vom Slot)")
            self.slot_panel.pack(fill="x", pady=(10, 0))
        else:
            self.slot_entry.grid_remove()
            try:
                self.ing_combo.configure(state="normal")
            except Exception:
                pass
            self.on_ingredient_selected()
            self.slot_panel.pack_forget()

    # ---------------- slot selection ----------------
    def _refresh_slot_lists(self, pid=None):
        if pid is None:
            return
        slots = self.db.list_distinct_slots(pid)
        self.slot_pick_combo["values"] = slots
        if slots:
            if self.slot_pick.get() not in slots:
                self.slot_pick.set(slots[0])
            self.load_slot_selection(pid)
        else:
            self.slot_pick.set("")
            self.slot_ing_pick.set("")

    def _load_slot_selection_for_selected_product(self):
        pid = self._get_selected_product_id()
        if pid is None:
            return
        self.load_slot_selection(pid)

    def load_slot_selection(self, pid: int):
        slot = (self.slot_pick.get() or "").strip()
        if not slot:
            self.slot_ing_pick.set("")
            return
        name = self.db.get_slot_selection_name(pid, slot)
        self.slot_ing_pick.set(name or "")

    def set_slot_selection(self):
        pid = self._get_selected_product_id()
        if pid is None:
            messagebox.showerror("Fehler", "Bitte zuerst ein Produkt auswählen.")
            return

        slot = (self.slot_pick.get() or "").strip()
        ing_typed = (self.slot_ing_pick.get() or "").strip()
        ing_name = self._resolve_ingredient_name(ing_typed) or ing_typed

        if not slot:
            messagebox.showerror("Fehler", "Bitte einen Slot auswählen.")
            return
        if not ing_name:
            messagebox.showerror("Fehler", "Bitte eine Zutat auswählen/tippen für den Slot.")
            return

        ing_id = self.db.get_ingredient_id_by_name(ing_name)
        if ing_id is None:
            messagebox.showerror("Fehler", "Zutat nicht gefunden.")
            return

        self.db.set_slot_selection(pid, slot, ing_id)
        self.refresh_products()
        self.refresh_recipe(pid)
        self.load_slot_selection(pid)

    # ---------------- enter helpers (recipe) ----------------
    def _recipe_enter_from_ingredient(self, _event=None):
        # If suggestions are open / available, Enter should accept the suggestion first.
        if getattr(self, "_ing_popdown_open", False):
            if self._accept_ing_combo_selection():
                try:
                    self.recipe_qty_entry.focus_set()
                except Exception:
                    pass
                return "break"
            return None

        # If typed text has matches, accept the first match.
        typed = (self.recipe_ing.get() or "").strip()
        try:
            values = list(self.ing_combo.cget("values") or [])
        except Exception:
            values = []

        if typed and values:
            # If not an exact match to one of the values, accept first suggestion.
            if all((v or "").strip().lower() != typed.lower() for v in values):
                if self._accept_ing_combo_selection():
                    try:
                        self.recipe_qty_entry.focus_set()
                    except Exception:
                        pass
                    return "break"

        qty_txt = (self.recipe_qty.get() or "").strip()
        if qty_txt == "":
            try:
                self.recipe_qty_entry.focus_set()
            except Exception:
                pass
            return "break"

        self.add_recipe_item()
        return "break"

    def _recipe_enter_from_slotname(self, _event=None):
        qty_txt = (self.recipe_qty.get() or "").strip()
        if qty_txt == "":
            try:
                self.recipe_qty_entry.focus_set()
            except Exception:
                pass
            return "break"
        self.add_recipe_item()
        return "break"

    # ---------------- recipe actions ----------------
    def add_recipe_item(self):
        pid = self._get_selected_product_id()
        if pid is None:
            messagebox.showerror("Fehler", "Bitte zuerst ein Produkt auswählen.")
            return

        qty = safe_float(self.recipe_qty.get())
        if qty is None or qty <= 0:
            messagebox.showerror("Fehler", "Menge muss > 0 sein.")
            return

        mode = self.add_mode.get()

        if mode == "SLOT":
            slot = (self.slot_name_var.get() or "").strip()
            if not slot:
                messagebox.showerror("Fehler", "Bitte Slot-Name angeben (z.B. SPIRIT).")
                return
            self.db.add_slot_line(pid, slot, qty)
            self._refresh_slot_lists(pid)
        else:
            ing_typed = (self.recipe_ing.get() or "").strip()
            ing_name = self._resolve_ingredient_name(ing_typed) or ing_typed
            if not ing_name:
                messagebox.showerror("Fehler", "Bitte Zutat auswählen (oder tippen).")
                return

            ing_id = self.db.get_ingredient_id_by_name(ing_name)
            if ing_id is None:
                messagebox.showerror("Fehler", "Zutat nicht gefunden.")
                return

            self.db.add_product_item(pid, ing_id, qty)

        # Clear qty always
        self.recipe_qty.set("")

        # After adding, jump back to the main input so the next item can be entered quickly.
        if mode == "SLOT":
            # Keep slot name (often reused), but focus qty again
            try:
                self.recipe_qty_entry.focus_set()
                self.recipe_qty_entry.icursor(tk.END)
            except Exception:
                pass
        else:
            # Clear ingredient field and focus it
            self.recipe_ing.set("")
            self._ing_popdown_open = False
            try:
                # restore full list
                self.ing_combo["values"] = self._all_ingredient_names or []
                self._unpost_combobox(self.ing_combo)
                self.ing_combo.focus_set()
                self.ing_combo.icursor(tk.END)
            except Exception:
                pass

        self.refresh_products()
        self.refresh_recipe(pid)

    def delete_selected_recipe_item(self):
        pid = self._get_selected_product_id()
        if pid is None:
            return

        sel = self.recipe_tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Bitte eine Rezept-Position auswählen.")
            return

        iid = sel[0]
        if iid.startswith("ing:"):
            item_id = int(iid.split(":", 1)[1])
            self.db.delete_product_item(item_id)
        elif iid.startswith("slot:"):
            line_id = int(iid.split(":", 1)[1])
            self.db.delete_slot_line(line_id)
        else:
            return

        self.refresh_products()
        self.refresh_recipe(pid)
        self._refresh_slot_lists(pid)

    def refresh_recipe(self, pid: int):
        self.recipe_tree.delete(*self.recipe_tree.get_children())

        total = 0.0

        for pi_id, iname, qty, unit, pack_qty, pack_price in self.db.list_product_items(pid):
            unit_price = (pack_price / pack_qty) if pack_qty else 0.0
            line_cost = unit_price * qty
            total += line_cost
            self.recipe_tree.insert(
                "",
                "end",
                iid=f"ing:{pi_id}",
                values=(iname, f"{qty:g}", unit, f"{unit_price:.4f} €/{unit}", money(line_cost)),
            )

        for sl_id, slot_name, qty in self.db.list_slot_lines(pid):
            r = self.db.get_slot_selection_price_unit(pid, slot_name)
            if r:
                sel_name, unit, pack_qty, pack_price = r
                unit_price = (pack_price / pack_qty) if pack_qty else 0.0
                line_cost = unit_price * qty
                total += line_cost
                label = f"{slot_name} → {sel_name}"
                self.recipe_tree.insert(
                    "",
                    "end",
                    iid=f"slot:{sl_id}",
                    values=(label, f"{qty:g}", unit, f"{unit_price:.4f} €/{unit}", money(line_cost)),
                )
            else:
                label = f"{slot_name} → (nicht gesetzt)"
                self.recipe_tree.insert(
                    "",
                    "end",
                    iid=f"slot:{sl_id}",
                    values=(label, f"{qty:g}", "–", "–", money(0.0)),
                )

        self.cost_label.config(text=f"Kosten: {money(total)}")

        if self.add_mode.get() == "SLOT":
            self.recipe_unit_label.config(text="Einheit: (vom Slot)")
        else:
            self.on_ingredient_selected()

        self._update_margin_display(pid)
    # ---------------- credit tooltip ----------------
    def _show_credit_tooltip(self, event=None):
        try:
            if hasattr(self, "_credit_tooltip") and self._credit_tooltip:
                return

            self._credit_tooltip = tk.Toplevel(self.app)
            self._credit_tooltip.wm_overrideredirect(True)
            self._credit_tooltip.attributes("-topmost", True)

            label = tk.Label(
                self._credit_tooltip,
                text="made by alexase7",
                bg="#222222",
                fg="#ffffff",
                padx=8,
                pady=4,
                font=("TkDefaultFont", 9)
            )
            label.pack()

            x = self._credit_label.winfo_rootx()
            y = self._credit_label.winfo_rooty() + self._credit_label.winfo_height() + 4
            self._credit_tooltip.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _hide_credit_tooltip(self, event=None):
        try:
            if hasattr(self, "_credit_tooltip") and self._credit_tooltip:
                self._credit_tooltip.destroy()
                self._credit_tooltip = None
        except Exception:
            pass

    def _open_github(self, event=None):
        try:
            webbrowser.open("https://github.com/alexase7")
        except Exception:
            pass