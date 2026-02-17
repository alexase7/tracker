import tkinter as tk
from tkinter import ttk, messagebox

from .config import PAGE_SIZE
from .ui_helpers import UIHelpers
from .utils import money, safe_float


class IngredientsTab(UIHelpers):
    def __init__(self, app, parent, db, on_any_change):
        self.app = app
        self.parent = parent
        self.db = db
        self.on_any_change = on_any_change  # callback to refresh products costs
        self.ing_filter = ""
        self.ing_offset = 0
        self._ingredients_rows = []
        # "secret" buffer: remember last used unit but keep the Unit entry visually empty if desired
        self._unit_buffer = "ml"
        self._suppress_on_select = False
        self._suppress_autoselect_once = False
        self._allowed_units = {"ml", "g", "stk"}
        self._build()

    def _build(self):
        top_outer = tk.Frame(self.parent, bg=self.app["bg"], bd=0, highlightthickness=0)
        top_outer.pack(fill="both", expand=True)

        top = ttk.Frame(top_outer, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Zutat").grid(row=0, column=0, sticky="w")
        ttk.Label(top, text="Einheit (ml/g/Stk)").grid(row=0, column=1, sticky="w")
        ttk.Label(top, text="Packungsmenge").grid(row=0, column=2, sticky="w")
        ttk.Label(top, text="Packungspreis (€)").grid(row=0, column=3, sticky="w")

        self.ing_name = tk.StringVar()
        self.ing_unit = tk.StringVar(value="ml")
        self.ing_pack_qty = tk.StringVar()
        self.ing_pack_price = tk.StringVar()

        self.ing_name_entry = ttk.Entry(top, textvariable=self.ing_name, width=28)
        self.ing_name_entry.grid(row=1, column=0, padx=(0, 10), pady=5, sticky="we")

        self.ing_unit_entry = ttk.Entry(top, textvariable=self.ing_unit, width=16)
        self.ing_unit_entry.grid(row=1, column=1, padx=(0, 10), pady=5, sticky="we")

        self.ing_pack_qty_entry = ttk.Entry(top, textvariable=self.ing_pack_qty, width=16)
        self.ing_pack_qty_entry.grid(row=1, column=2, padx=(0, 10), pady=5, sticky="we")

        self.ing_pack_price_entry = ttk.Entry(top, textvariable=self.ing_pack_price, width=16)
        self.ing_pack_price_entry.grid(row=1, column=3, padx=(0, 10), pady=5, sticky="we")

        ttk.Button(top, text="Zutat hinzufügen / updaten", command=self.add_or_update).grid(
            row=1, column=4, padx=(0, 10), pady=5
        )
        ttk.Button(top, text="Zutat löschen", command=self.delete_selected).grid(row=1, column=5, pady=5)

        # Search + paging
        search_row = ttk.Frame(top_outer, padding=(10, 0, 10, 6))
        search_row.pack(fill="x")

        ttk.Label(search_row, text="Suche:").pack(side="left")
        self.ing_search_var = tk.StringVar()
        self.ing_search_entry = ttk.Entry(search_row, textvariable=self.ing_search_var, width=30)
        self.ing_search_entry.pack(side="left", padx=(8, 12))
        self.ing_search_entry.bind("<KeyRelease>", lambda _e: self._on_search_changed())
        # keyboard: from search into list
        self.ing_search_entry.bind("<Down>", lambda _e: (self._tree_move_selection(self.ing_tree, +1), "break")[1])
        self.ing_search_entry.bind("<Up>", lambda _e: (self._tree_move_selection(self.ing_tree, -1), "break")[1])
        self.ing_search_entry.bind("<Return>", self._focus_ingredients_tree_from_search)

        self.ing_page_label = ttk.Label(search_row, text="")
        self.ing_page_label.pack(side="right")
        ttk.Button(search_row, text="Weiter ▶", command=lambda: self._page(+1)).pack(side="right", padx=(6, 0))
        ttk.Button(search_row, text="◀ Zurück", command=lambda: self._page(-1)).pack(side="right")

        mid = ttk.Frame(top_outer, padding=(10, 0, 10, 10))
        mid.pack(fill="both", expand=True)

        cols = ("name", "unit", "pack_qty", "pack_price", "unit_price")
        self.ing_tree = ttk.Treeview(mid, columns=cols, show="headings", height=18, selectmode="browse")
        self.ing_tree.heading("name", text="Name")
        self.ing_tree.heading("unit", text="Einheit")
        self.ing_tree.heading("pack_qty", text="Packungsmenge")
        self.ing_tree.heading("pack_price", text="Packungspreis")
        self.ing_tree.heading("unit_price", text="Preis pro Einheit")

        self.ing_tree.column("name", width=260)
        self.ing_tree.column("unit", width=90, anchor="center")
        self.ing_tree.column("pack_qty", width=130, anchor="e")
        self.ing_tree.column("pack_price", width=130, anchor="e")
        self.ing_tree.column("unit_price", width=180, anchor="e")

        self.ing_tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.ing_tree.yview)
        self.ing_tree.configure(yscroll=sb.set)
        sb.pack(side="right", fill="y")
        self.ing_tree.bind("<<TreeviewSelect>>", self.on_select)
        # Persist column widths
        self.persist_tree_columns(self.ing_tree, "tree.ingredients", ["name", "unit", "pack_qty", "pack_price", "unit_price"])

        # Keyboard
        for w in [self.ing_name_entry, self.ing_unit_entry, self.ing_pack_qty_entry, self.ing_pack_price_entry]:
            w.bind("<Return>", lambda _e: (self.add_or_update(), "break")[1])
            w.bind("<Down>", lambda _e: (self._tree_move_selection(self.ing_tree, +1), "break")[1])
            w.bind("<Up>", lambda _e: (self._tree_move_selection(self.ing_tree, -1), "break")[1])

        # Left/Right: move between form fields (only when caret is at edge)
        self._form_fields = [
            self.ing_name_entry,
            self.ing_unit_entry,
            self.ing_pack_qty_entry,
            self.ing_pack_price_entry,
        ]

        def _form_move(current_widget, direction: int):
            try:
                idx = self._form_fields.index(current_widget)
            except ValueError:
                return "break"

            nxt = idx + direction
            if nxt < 0 or nxt >= len(self._form_fields):
                return "break"

            target = self._form_fields[nxt]
            try:
                target.focus_set()
                # place caret at end for fast overwrite
                target.icursor(tk.END)
            except Exception:
                pass
            return "break"

        def _on_left(event):
            w = event.widget
            # if user is editing in the middle, keep normal cursor movement
            try:
                if w.selection_present():
                    return None
            except Exception:
                pass
            try:
                if w.index(tk.INSERT) == 0:
                    return _form_move(w, -1)
            except Exception:
                return _form_move(w, -1)
            return None

        def _on_right(event):
            w = event.widget
            try:
                if w.selection_present():
                    return None
            except Exception:
                pass
            try:
                if w.index(tk.INSERT) == len(w.get()):
                    return _form_move(w, +1)
            except Exception:
                return _form_move(w, +1)
            return None

        for w in self._form_fields:
            w.bind("<Left>", _on_left)
            w.bind("<Right>", _on_right)

        # Enter on list -> focus form, PageUp/PageDown -> paging
        self.ing_tree.bind("<Return>", self._focus_form_from_ingredients_tree)
        self.ing_tree.bind("<Next>", lambda _e: (self._page(+1), self._select_first_in_tree(), "break")[2])  # PageDown
        self.ing_tree.bind("<Prior>", lambda _e: (self._page(-1), self._select_first_in_tree(), "break")[2])  # PageUp

    def _select_first_in_tree(self):
        items = self.ing_tree.get_children()
        if not items:
            return
        first = items[0]
        self.ing_tree.selection_set(first)
        self.ing_tree.focus(first)
        self.ing_tree.see(first)
        try:
            self.ing_tree.focus_set()
        except Exception:
            pass

    def _focus_ingredients_tree_from_search(self, _event=None):
        self._select_first_in_tree()
        return "break"

    def _focus_form_from_ingredients_tree(self, _event=None):
        try:
            self.ing_name_entry.focus_set()
            self.ing_name_entry.icursor(tk.END)
        except Exception:
            pass
        return "break"

    def _clear_tree_selection(self):
        try:
            sel = self.ing_tree.selection()
            if sel:
                self.ing_tree.selection_remove(*sel)
        except Exception:
            pass
        try:
            self.ing_tree.focus("")
        except Exception:
            pass

    def refresh(self):
        self._ingredients_rows = self.db.list_ingredients()
        self._render()

    def _render(self):
        for r in self.ing_tree.get_children():
            self.ing_tree.delete(r)

        rows = list(self._ingredients_rows)
        f = (self.ing_filter or "").strip().lower()
        if f:
            rows = [r for r in rows if f in (r[1] or "").lower()]

        total = len(rows)
        if total <= PAGE_SIZE:
            self.ing_offset = 0
        else:
            self.ing_offset = max(0, min(self.ing_offset, max(0, total - PAGE_SIZE)))

        page = rows[self.ing_offset : self.ing_offset + PAGE_SIZE]
        for _id, name, unit, pack_qty, pack_price in page:
            unit_price = (pack_price / pack_qty) if pack_qty else 0.0
            self.ing_tree.insert(
                "",
                "end",
                iid=str(_id),
                values=(name, unit, f"{pack_qty:g}", money(pack_price), f"{unit_price:.4f} €/{unit}"),
            )

        # Ensure selection for keyboard navigation (can be suppressed once)
        items = self.ing_tree.get_children()
        if getattr(self, "_suppress_autoselect_once", False):
            # keep list unselected so the form stays empty for fast entry
            self._suppress_autoselect_once = False
        elif items and not self.ing_tree.selection():
            first = items[0]
            self.ing_tree.selection_set(first)
            self.ing_tree.focus(first)
            self.ing_tree.see(first)

        start = self.ing_offset + 1 if total else 0
        end = min(self.ing_offset + PAGE_SIZE, total)
        self.ing_page_label.config(text=f"{start}–{end} von {total}")

    def _on_search_changed(self):
        self.ing_filter = (self.ing_search_var.get() or "").strip()
        self.ing_offset = 0
        self._render()

    def _page(self, direction: int):
        rows = list(self._ingredients_rows)
        f = (self.ing_filter or "").strip().lower()
        if f:
            rows = [r for r in rows if f in (r[1] or "").lower()]
        total = len(rows)
        if total <= PAGE_SIZE:
            self.ing_offset = 0
        else:
            self.ing_offset = max(0, min(self.ing_offset + direction * PAGE_SIZE, max(0, total - PAGE_SIZE)))
        self._render()

    def on_select(self, _):
        if getattr(self, "_suppress_on_select", False):
            return
        sel = self.ing_tree.selection()
        if not sel:
            return
        iid = sel[0]
        vals = self.ing_tree.item(iid, "values")
        self.ing_name.set(vals[0])
        self.ing_unit.set((vals[1] or "").lower())
        self.ing_pack_qty.set(vals[2])
        self.ing_pack_price.set(vals[3].replace(" €", ""))

    def add_or_update(self):
        name = self.ing_name.get().strip()
        unit_raw = (self.ing_unit.get() or "").strip()
        if not unit_raw:
            unit = getattr(self, "_unit_buffer", "ml")
        else:
            unit = unit_raw.lower()

        if unit not in getattr(self, "_allowed_units", {"ml", "g", "stk"}):
            messagebox.showerror("Fehler", "Einheit muss ml, g oder Stk sein.")
            return

        # update buffer with normalized unit
        self._unit_buffer = unit

        pack_qty = safe_float(self.ing_pack_qty.get())
        pack_price = safe_float(self.ing_pack_price.get())

        if not name or not unit or pack_qty is None or pack_price is None:
            messagebox.showerror("Fehler", "Bitte Name, Einheit, Packungsmenge und Packungspreis korrekt ausfüllen.")
            return
        if pack_qty <= 0:
            messagebox.showerror("Fehler", "Packungsmenge muss > 0 sein.")
            return
        if pack_price < 0:
            messagebox.showerror("Fehler", "Packungspreis darf nicht negativ sein.")
            return

        self.db.upsert_ingredient(name, unit, pack_qty, pack_price)

        # Normalize the visible unit field (even if it will be cleared below)
        try:
            self.ing_unit.set(unit)
        except Exception:
            pass

        # After refresh(), Treeview auto-selection would refill the form via on_select.
        # Suppress that once so the form stays empty for fast repeated entry.
        self._suppress_on_select = True
        self._suppress_autoselect_once = True

        # Clear form for fast repeated entry
        self.ing_name.set("")
        self.ing_unit.set("")  # keep buffer, but clear visible field
        self.ing_pack_qty.set("")
        self.ing_pack_price.set("")

        # ensure list is unselected before/after refresh
        self._clear_tree_selection()
        self.refresh()
        # clear any selection/focus that might still exist so the form stays empty
        self._clear_tree_selection()

        self.on_any_change()
        try:
            self.ing_name_entry.focus_set()
        except Exception:
            pass

        # Re-enable selection-driven form fill AFTER pending selection events (if any)
        def _reenable():
            self._suppress_on_select = False

        try:
            self.app.after_idle(_reenable)
        except Exception:
            _reenable()

    def delete_selected(self):
        sel = self.ing_tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Bitte eine Zutat auswählen.")
            return
        ing_id = int(sel[0])
        name = self.ing_tree.item(sel[0], "values")[0]

        if not messagebox.askyesno("Bestätigen", f"Zutat '{name}' wirklich löschen?"):
            return

        if self.db.ingredient_is_used(ing_id):
            messagebox.showerror("Fehler", "Zutat ist in Produkten/Slots verwendet und kann nicht gelöscht werden.")
            return

        self.db.delete_ingredient(ing_id)
        self.refresh()
        self.on_any_change()
        try:
            self.ing_name_entry.focus_set()
        except Exception:
            pass