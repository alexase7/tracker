from tkinter import ttk
from .config import BG, PANEL, FIELD, FG, MUTED, SEL_BG


def apply_theme(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure("TPanedwindow", background=BG, relief="flat", borderwidth=0)
    style.configure("Custom.Panedwindow", background=BG, relief="flat", borderwidth=0)
    style.configure("Sash", background=BG, relief="flat", borderwidth=0)
    style.configure("Custom.Panedwindow.Sash", background=BG, relief="flat", borderwidth=0)

    style.configure("TFrame", background=BG, borderwidth=0)
    style.configure("TLabel", background=BG, foreground=FG)

    style.configure("TNotebook", background=BG, borderwidth=0, relief="flat")
    style.configure(
        "TNotebook.Tab",
        background=PANEL,
        foreground=FG,
        padding=(12, 8),
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "TNotebook.Tab",
        bordercolor=BG,
        lightcolor=BG,
        darkcolor=BG,
        focuscolor=BG,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", BG), ("active", PANEL)],
        foreground=[("selected", FG)],
        bordercolor=[("selected", BG), ("active", BG)],
        lightcolor=[("selected", BG), ("active", BG)],
        darkcolor=[("selected", BG), ("active", BG)],
    )

    style.configure(
        "TButton",
        padding=(10, 6),
        background=PANEL,
        foreground=FG,
        borderwidth=0,
        relief="flat",
    )
    style.map(
        "TButton",
        background=[("active", "#333333"), ("pressed", "#333333")],
        foreground=[("disabled", MUTED)],
    )

    style.configure(
        "TEntry",
        padding=(6, 4),
        fieldbackground=FIELD,
        background=FIELD,
        foreground=FG,
        insertcolor=FG,
        borderwidth=0,
        relief="flat",
    )

    style.configure(
        "TCombobox",
        padding=(6, 4),
        fieldbackground=FIELD,
        background=FIELD,
        foreground=FG,
        borderwidth=0,
        relief="flat",
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", FIELD), ("!readonly", FIELD)],
        foreground=[("readonly", FG), ("!readonly", FG)],
    )

    style.configure(
        "Treeview",
        background=PANEL,
        fieldbackground=PANEL,
        foreground=FG,
        rowheight=26,
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "Treeview.Heading",
        background=BG,
        foreground=FG,
        borderwidth=0,
        relief="flat",
    )
    style.map("Treeview", background=[("selected", SEL_BG)], foreground=[("selected", FG)])

    for sty in ("TEntry", "TCombobox"):
        style.configure(
            sty,
            bordercolor=FIELD,
            lightcolor=FIELD,
            darkcolor=FIELD,
            focuscolor=FIELD,
            highlightcolor=FIELD,
        )

    style.configure(
        "TRadiobutton",
        background=BG,
        foreground=FG,
        borderwidth=0,
        relief="flat",
        indicatorcolor=PANEL,
        focuscolor=BG,
    )

    style.configure(
        "TScrollbar",
        troughcolor=PANEL,
        background=PANEL,
        bordercolor=PANEL,
        lightcolor=PANEL,
        darkcolor=PANEL,
        arrowcolor=FG,
        relief="flat",
        borderwidth=0,
    )

    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    try:
        style.layout("Custom.TNotebook", [("Notebook.client", {"sticky": "nswe"})])
    except Exception:
        pass

    style.configure("Custom.TNotebook", background=BG, borderwidth=0, relief="flat", padding=0)
    for nb_style in ("TNotebook", "Custom.TNotebook"):
        style.configure(nb_style, bordercolor=BG, lightcolor=BG, darkcolor=BG, focuscolor=BG)

    try:
        style.layout("Custom.Panedwindow", style.layout("TPanedwindow"))
    except Exception:
        pass

    root.configure(bg=BG, highlightthickness=0, bd=0)