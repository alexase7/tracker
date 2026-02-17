def money(x: float) -> str:
    return f"{x:.2f} €"


def safe_float(s):
    try:
        return float(str(s).replace(",", "."))
    except (TypeError, ValueError):
        return None