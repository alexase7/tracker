import tkinter as tk
from tkinter import ttk
import json
from pathlib import Path


class UIHelpers:
    """Helper mixin. Expects self.app to be a tk.Tk instance."""

    def _tree_move_selection(self, tree: ttk.Treeview, delta: int):
        items = tree.get_children()
        if not items:
            return

        sel = tree.selection()
        if sel:
            current = sel[0]
            try:
                idx = items.index(current)
            except ValueError:
                idx = 0
        else:
            idx = -1 if delta > 0 else len(items)

        idx = max(0, min(len(items) - 1, idx + delta))
        target = items[idx]
        tree.selection_set(target)
        tree.focus(target)
        tree.see(target)
        try:
            tree.focus_set()
        except Exception:
            pass

    def _post_combobox(self, combo: ttk.Combobox):
        try:
            self.app.tk.call("ttk::combobox::Post", combo)
        except Exception:
            try:
                combo.event_generate("<Down>")
            except Exception:
                pass

    def _unpost_combobox(self, combo: ttk.Combobox):
        try:
            self.app.tk.call("ttk::combobox::Unpost", combo)
        except Exception:
            pass

    def _ensure_combo_dropdown(self, combo: ttk.Combobox):
        try:
            if self.app.focus_get() is not combo:
                return
        except Exception:
            pass

        try:
            self.app.tk.call("ttk::combobox::Post", combo)
        except Exception:
            try:
                combo.event_generate("<Down>")
            except Exception:
                return

        def _restore():
            try:
                combo.focus_set()
                combo.icursor(tk.END)
            except Exception:
                pass

        try:
            combo.after(1, _restore)
        except Exception:
            _restore()

    # ---------------- persistent UI state (tree column widths) ----------------
    def _ui_state_path(self) -> Path:
        """Store UI state next to this module (runtime-created file)."""
        return Path(__file__).with_name("ui_state.json")

    def _ui_state_load(self) -> dict:
        if hasattr(self, "_ui_state_cache") and isinstance(getattr(self, "_ui_state_cache"), dict):
            return self._ui_state_cache

        p = self._ui_state_path()
        if not p.exists():
            self._ui_state_cache = {}
            return self._ui_state_cache

        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}

        self._ui_state_cache = data
        return self._ui_state_cache

    def _ui_state_save(self) -> None:
        p = self._ui_state_path()
        data = self._ui_state_load()
        try:
            tmp = p.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(p)
        except Exception:
            # best-effort only
            pass

    def _tree_get_widths(self, tree: ttk.Treeview, cols: list[str]) -> dict:
        widths: dict[str, int] = {}
        for c in cols:
            try:
                widths[c] = int(tree.column(c, "width"))
            except Exception:
                pass
        return widths

    def _tree_apply_widths(self, tree: ttk.Treeview, widths: dict, cols: list[str]) -> None:
        for c in cols:
            if c in widths:
                try:
                    tree.column(c, width=int(widths[c]))
                except Exception:
                    pass

    def persist_tree_columns(self, tree: ttk.Treeview, key: str, cols: list[str]) -> None:
        """Load+persist Treeview column widths under `key`.

        This will create/update `ui_state.json` at runtime.
        """
        state = self._ui_state_load()
        widths = state.get(key)
        if isinstance(widths, dict):
            self._tree_apply_widths(tree, widths, cols)

        # Keep per-key debounce timers (avoid scheduling on a widget being destroyed)
        if not hasattr(self, "_ui_state_after_ids"):
            self._ui_state_after_ids = {}

        def _cancel_pending():
            aid = self._ui_state_after_ids.pop(key, None)
            if aid is None:
                return
            try:
                self.app.after_cancel(aid)
            except Exception:
                pass

        def _do_save_safe():
            # Only run if both app and tree still exist
            try:
                if not bool(self.app.winfo_exists()):
                    return
            except Exception:
                return
            try:
                if not bool(tree.winfo_exists()):
                    return
            except Exception:
                return

            try:
                st = self._ui_state_load()
                st[key] = self._tree_get_widths(tree, cols)
                self._ui_state_save()
            except Exception:
                pass

        def _schedule_save(_e=None):
            # If we are tearing down, do nothing.
            try:
                if not bool(self.app.winfo_exists()):
                    return
            except Exception:
                return
            try:
                if not bool(tree.winfo_exists()):
                    return
            except Exception:
                return

            _cancel_pending()
            try:
                self._ui_state_after_ids[key] = self.app.after(250, _do_save_safe)
            except Exception:
                _do_save_safe()

        # Ensure pending callback is canceled when the widget is destroyed
        tree.bind("<Destroy>", lambda _e: _cancel_pending(), add=True)

        # Save during resize drag + on release + fallback triggers
        tree.bind("<B1-Motion>", _schedule_save, add=True)
        tree.bind("<ButtonRelease-1>", _schedule_save, add=True)
        tree.bind("<FocusOut>", _schedule_save, add=True)
        tree.bind("<Configure>", _schedule_save, add=True)