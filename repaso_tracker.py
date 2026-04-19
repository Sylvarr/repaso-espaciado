#!/usr/bin/env python3
"""
Tracker de repaso espaciado interactivo
"""

import json
import sys
import os
import re
import shutil
import subprocess
from datetime import date, timedelta, datetime
from collections import defaultdict

try:
    import typer
    import questionary
except ImportError:
    print("Faltan dependencias. Por favor instala: pip install typer questionary rich")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    from rich import box
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.columns import Columns
    from rich.align import Align
    RICH = True
    console = Console()
except ImportError:
    RICH = False
    console = None

app = typer.Typer(help="Tracker de repaso espaciado con CLI interactivo", add_completion=False)

_DATA_DIR = os.path.expanduser("~/.local/share/repaso")
os.makedirs(_DATA_DIR, exist_ok=True)
DATA_FILE = os.environ.get("REPASO_DATA_FILE") or os.path.join(_DATA_DIR, "repaso_data.json")
BAK_FILE  = DATA_FILE + ".bak"

INTERVALS = [1, 7, 21, 45]
FACTOR_FACIL   = 1.5
FACTOR_DIFICIL = 0.5

DEFAULT_ASIGS = {
    "bd":   "Bases de datos",
    "prog": "Programación",
    "si":   "Sistemas informáticos",
    "lm":   "Lenguajes de marcas",
    "ed":   "Entornos de desarrollo",
    "it":   "Itinerario empleabilidad",
}

# ─────────────────────────────────────────────────────────────────────────────
#  I/O
# ─────────────────────────────────────────────────────────────────────────────

def load():
    if not os.path.exists(DATA_FILE):
        return [], [], {"asigs": DEFAULT_ASIGS.copy()}
    with open(DATA_FILE, "r") as f:
        raw = json.load(f)
    if isinstance(raw, list):
        return raw, [], {"asigs": DEFAULT_ASIGS.copy()}
    meta = raw.get("meta", {})
    if "asigs" not in meta:
        meta["asigs"] = DEFAULT_ASIGS.copy()
    active = raw.get("active", [])
    for e in active:
        if "next_date" not in e:
            done = e.get("repasos", 0)
            if done >= len(INTERVALS): e["next_date"] = None
            else: e["next_date"] = add_days(e["last_date"], INTERVALS[done])
            
    return active, raw.get("archived", []), meta

def save(entries, archived, meta=None):
    if meta is None: meta = {}
    if os.path.exists(DATA_FILE):
        shutil.copy2(DATA_FILE, BAK_FILE)
    with open(DATA_FILE, "w") as f:
        json.dump({"active": entries, "archived": archived, "meta": meta},
                  f, indent=2, ensure_ascii=False)

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_today():
    now = datetime.now()
    if now.hour < 4:
        return (now - timedelta(days=1)).date()
    return now.date()

def add_days(date_str, n):
    return str(date.fromisoformat(date_str) + timedelta(days=max(1, int(n))))

def days_diff(date_str):
    return (date.fromisoformat(date_str) - get_today()).days

def get_next_repaso(entry):
    return entry.get("next_date")

def format_rep(r):
    return f"{r}/4" if r <= 4 else f"{r}/4+"

def is_afianzado(entry):
    return get_next_repaso(entry) is None

def update_streak(meta):
    today     = str(get_today())
    last_done = meta.get("last_done_date")
    streak    = meta.get("streak", 0)
    if last_done == today: pass
    elif last_done == str(get_today() - timedelta(days=1)): streak += 1
    else: streak = 1
    meta["last_done_date"] = today
    meta["streak"]         = streak
    return meta

def notify(title, body, urgency="normal"):
    import platform
    sistema = platform.system()
    try:
        if sistema == "Linux":
            subprocess.run(
                ["notify-send", "-u", urgency, "-i", "appointment-soon", title, body],
                check=False
            )
        elif sistema == "Darwin":  # macOS
            # osascript está disponible en todos los Mac sin instalar nada
            script = f'display notification "{body}" with title "{title}"'
            subprocess.run(["osascript", "-e", script], check=False)
    except FileNotFoundError:
        pass  # silencioso si el comando no está disponible

def cprint(text, style=""):
    if RICH: console.print(text, style=style)
    else: print(re.sub(r'\[/?[^\]]*\]', '', text))

_ASIG_COLOR_PALETTE = ["cyan", "green", "yellow", "magenta", "blue", "red", "bright_cyan", "bright_green"]
_asig_color_cache: dict = {}

def asig_color(asig: str) -> str:
    """Devuelve un color Rich consistente para una asignatura dada."""
    if asig not in _asig_color_cache:
        idx = len(_asig_color_cache) % len(_ASIG_COLOR_PALETTE)
        _asig_color_cache[asig] = _ASIG_COLOR_PALETTE[idx]
    return _asig_color_cache[asig]

# ─────────────────────────────────────────────────────────────────────────────
#  Comandos Interactivos (Typer + Questionary)
# ─────────────────────────────────────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        cmd_check()

@app.command(name="check")
def cmd_check():
    """Ver avisos del día y próximos (comando por defecto si no escribes nada)."""
    entries, archived, meta = load()
    today  = str(get_today())
    streak = meta.get("streak", 0)

    due = [(e, nr, days_diff(nr := get_next_repaso(e))) for e in entries if (nr := get_next_repaso(e)) and days_diff(nr) <= 0]
    due.sort(key=lambda x: x[2])

    upcoming = [(e, nr, days_diff(nr)) for e in entries if (nr := get_next_repaso(e)) and 1 <= days_diff(nr) <= 3]
    upcoming.sort(key=lambda x: x[2])
    
    if meta.get("last_notify_date") != today:
        if not due:
            notify("DAW — Sin repasos", "¡Al día! Céntrate en avanzar temario.")
        else:
            c_hoy = sum(1 for _, _, d in due if d == 0)
            c_tarde = sum(1 for _, _, d in due if d < 0)
            msg = []
            if c_hoy: msg.append(f"{c_hoy} para hoy")
            if c_tarde: msg.append(f"{c_tarde} atrasados")
            urgency = "critical" if c_tarde else "normal"
            notify("DAW — Repasos Pendientes", " y ".join(msg).capitalize(), urgency)
            
        meta["last_notify_date"] = today
        save(entries, archived, meta)

    if RICH:
        from rich.console import Group
        streak_text = f" 🔥 [bold yellow]¡Racha de {streak} días![/]" if streak > 1 else ""
        header = Panel(f"[bold cyan]TRACKER DE REPASO — {today}[/]{streak_text}", border_style="cyan")
        
        if not due:
            tarde_txt = ""
            if upcoming:
                tarde_txt += "\n\n[dim]Próximamente:\n" + "\n".join(f"• {e['asig']} T{e['tema']:02d} — {'mañana' if diff==1 else f'en {diff} días'}" for e, nr, diff in upcoming) + "[/]"
            body = Panel("[bold green]✓ Sin repasos pendientes. ¡Céntrate en el tema nuevo![/]\n" + tarde_txt, border_style="green")
            console.print(Group(header, body))
        else:
            hoy   = [(e, nr, d) for e, nr, d in due if d == 0]
            tarde = [(e, nr, d) for e, nr, d in due if d < 0]
            
            body_items = []
            if hoy:
                t = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta", expand=True)
                t.add_column("Asignatura")
                t.add_column("Tema", justify="center")
                t.add_column("Repaso", justify="center")
                t.add_column("Progreso", justify="left")
                t.add_column("ID", style="dim")
                for e, _, _ in hoy:
                    rep = e.get('repasos',0)+1
                    total = max(4, rep)
                    filled = min(rep, total)
                    bar = "█" * filled + "░" * (total - filled)
                    color = asig_color(e["asig"])
                    t.add_row(
                        Text(e["asig"], style=f"bold {color}"),
                        f"T{e['tema']:02d}",
                        format_rep(rep),
                        f"[{color}][{bar}][/]",
                        e["id"]
                    )
                body_items.append(t)
                
            tarde_txt = ""
            if tarde:
                tarde_txt = "[bold red]ATRASADOS:[/]\n" + "\n".join(f"[red]• {e['asig']} T{e['tema']:02d} — (+{abs(d)}d)[/]" for e, _, d in tarde)
            if upcoming:
                tarde_txt += "\n\n[dim]Próximamente:\n" + "\n".join(f"• {e['asig']} T{e['tema']:02d} — {'mañana' if diff==1 else f'en {diff} días'}" for e, nr, diff in upcoming) + "[/]"
                
            if tarde_txt:
                body_items.append(Panel(tarde_txt, title="Pendientes & Próximos", border_style="dim"))
                
            console.print(Group(header, *body_items))
        
    else:
        print(f"\n{'='*55}\n  TRACKER DE REPASO — {today}\n{'='*55}")
        if streak > 1: print(f"\n  🔥 Racha: {streak} días seguidos estudiando")
        if not due:
            print("\n  ✓ Sin repasos pendientes.\n")
        else:
            for e, nr, d in due:
                rep = e.get('repasos', 0) + 1
                total = max(4, rep)
                bar = "█" * min(rep, total) + "░" * (total - min(rep, total))
                print(f"  ★ {e['asig']} T{e['tema']:02d}  rep {format_rep(rep)}  [{bar}]")

@app.command(name="add")
def cmd_add():
    """Registrar un nuevo tema de estudio."""
    entries, archived, meta = load()
    asigs = meta["asigs"]
    
    choices = [questionary.Choice(title=f"{name} ({key})", value=key) for key, name in asigs.items()]
    asig_key = questionary.select("¿Qué asignatura has estudiado?", choices=choices).ask()
    if not asig_key: return

    tema_str = questionary.text("Número de tema:", validate=lambda t: True if t.isdigit() else "Por favor, introduce un número.").ask()
    if not tema_str: return
    tema = int(tema_str)

    eid   = f"{asig_key}_t{tema}"
    today = str(get_today())
    existing = next((e for e in entries if e["id"] == eid), None)

    if existing:
        if not questionary.confirm(f"'{asigs[asig_key]} Tema {tema}' ya existe. ¿Reiniciar desde cero?").ask():
            cprint("  Cancelado.", "dim")
            return
        existing.update({"study_date": today, "last_date": today, "repasos": 0, "next_date": add_days(today, INTERVALS[0]), "_prev": None})
    else:
        entries.append({"id": eid, "asig": asigs[asig_key], "tema": int(tema),
                        "study_date": today, "last_date": today,
                        "repasos": 0, "next_date": add_days(today, INTERVALS[0]), "_prev": None})

    save(entries, archived, meta)
    cprint(f"\n  ✓ Registrado: [bold]{asigs[asig_key]} Tema {tema}[/]", "green")
    print()

@app.command(name="done")
def cmd_done(eid: str = typer.Argument(None, help="ID del tema (opcional)")):
    """Marcar un repaso pendiente como completado."""
    entries, archived, meta = load()
    
    if not eid:
        due = [(e, nr, days_diff(nr := get_next_repaso(e))) for e in entries if (nr := get_next_repaso(e))]
        if not due:
            cprint("\n  No hay temas activos pendientes de repaso.\n", "yellow")
            return
            
        asigs_with_due = {}
        for e, nr, d in due:
            if e["asig"] not in asigs_with_due: asigs_with_due[e["asig"]] = []
            asigs_with_due[e["asig"]].append((e, nr, d))
            
        sorted_asigs = sorted(asigs_with_due.items(), key=lambda item: min(d for _, _, d in item[1]))
        asig_choices = []
        for asig, items in sorted_asigs:
            urgentes = sum(1 for _, _, d in items if d <= 0)
            tag = f" ({urgentes} para hoy/atrasados)" if urgentes > 0 else ""
            asig_choices.append(questionary.Choice(f"{asig}{tag}", value=asig))
            
        selected_asig = questionary.select("Selecciona la asignatura:", choices=asig_choices).ask()
        if not selected_asig: return
        
        tema_choices = []
        items = asigs_with_due[selected_asig]
        items.sort(key=lambda x: x[2])
        for e, nr, d in items:
            rep = e.get('repasos',0)+1
            title = f"T{e['tema']:02d} — rep {format_rep(rep)} "
            if d < 0: title += f"(ATRASADO {abs(d)}d)"
            elif d == 0: title += "(HOY)"
            else: title += f"(en {d} días)"
            
            tema_choices.append(questionary.Choice(title=title, value=e["id"]))
            
        eid = questionary.select("¿Qué repaso has completado?", choices=tema_choices).ask()
        if not eid: return

    entry = next((e for e in entries if e["id"] == eid), None)
    if not entry:
        cprint(f"\n  No encontrado: {eid}\n", "red")
        return

    nr = get_next_repaso(entry)
    if nr and days_diff(nr) > 0:
        if not questionary.confirm(f"Este repaso toca el {nr} (en {days_diff(nr)} días). ¿Continuar?").ask():
            cprint("  Cancelado.\n", "dim")
            return

    dif_choice = questionary.select(
        "¿Qué nivel de dificultad tuvo?",
        choices=[
            questionary.Choice("Normal (intervalo estándar)", value="normal"),
            questionary.Choice("Fácil (multiplica x1.5)", value="facil"),
            questionary.Choice("Difícil (multiplica x0.5)", value="dificil")
        ]
    ).ask()
    if not dif_choice: return
    
    score_str = questionary.text("Puntuación del test (ej. 8/10) [Enter si no hiciste test]:").ask()
    if score_str is None: return
    
    score_val = None
    if score_str.strip():
        try:
            s = score_str.strip()
            if "/" in s:
                num, den = s.split("/")
                score_val = (float(num.strip()) / float(den.strip())) * 100
            elif "%" in s:
                score_val = float(s.replace("%", "").strip())
            else:
                score_val = float(s)
                if score_val <= 10: score_val *= 10
            score_val = max(0, min(100, score_val))
        except ValueError:
            cprint("  ⚠️ Formato de puntuación no reconocido. Se omitirá.", "yellow")

    today = str(get_today())
    entry["_prev"] = {
        "repasos": entry.get("repasos", 0), 
        "last_date": entry.get("last_date"), 
        "next_date": entry.get("next_date"),
        "history": list(entry.get("history", [])),
        "scores": list(entry.get("scores", [])),
        "dates": list(entry.get("dates", []))
    }
    
    history = entry.get("history", [])
    history.append(dif_choice)
    entry["history"] = history
    
    if score_val is not None:
        scores = entry.get("scores", [])
        scores.append(score_val)
        entry["scores"] = scores
    
    dates = entry.get("dates", [])
    dates.append(today)
    entry["dates"] = dates

    new_repasos = entry.get("repasos", 0) + 1
    entry["repasos"] = new_repasos
    entry["last_date"] = today

    if new_repasos >= len(INTERVALS) and dif_choice != "dificil":
        entry["next_date"] = None
    else:
        base_idx = new_repasos if new_repasos < len(INTERVALS) else -1
        base = INTERVALS[base_idx]
        
        ef = max(0.5, 1.0 + (history.count("facil") * 0.15) - (history.count("dificil") * 0.15))
        intervalo = max(1, round(base * ef))
        entry["next_date"] = add_days(today, intervalo)

    meta = update_streak(meta)
    save(entries, archived, meta)

    cprint(f"\n  ✓ Repaso {format_rep(new_repasos)} registrado — {entry['asig']} Tema {entry['tema']} [{dif_choice.upper()}]", "bold green")
    nr2 = get_next_repaso(entry)
    if nr2: cprint(f"  Próximo repaso: {nr2} (en {days_diff(nr2)} días)")
    else: cprint("  ¡AFIANZADO! 🎉", "bold yellow")
    print()

@app.command(name="undo")
def cmd_undo():
    """Deshacer el último repaso realizado."""
    entries, archived, meta = load()
    valid = [e for e in entries if e.get("_prev")]
    if not valid:
        cprint("\n  No hay temas con un estado previo para deshacer.\n", "yellow")
        return
    eid = questionary.select("Selecciona el tema para deshacer su último repaso:", choices=[questionary.Choice(f"{e['asig']} T{e['tema']}", e["id"]) for e in valid]).ask()
    if not eid: return

    entry = next((e for e in entries if e["id"] == eid), None)
    prev = entry["_prev"]
    entry["repasos"] = prev["repasos"]
    entry["last_date"] = prev["last_date"]
    entry["next_date"] = prev["next_date"]
    entry["history"] = prev.get("history", [])
    entry["scores"] = prev.get("scores", [])
    entry["dates"] = prev.get("dates", [])
    entry["_prev"] = None

    save(entries, archived, meta)
    cprint(f"\n  ↩ Undo aplicado — {entry['asig']} Tema {entry['tema']}", "yellow")
    print()

@app.command(name="history")
def cmd_history():
    """Ver el historial completo de repasos de un tema."""
    entries, _, meta = load()
    if not entries:
        cprint("\n  Sin temas registrados aún.\n", "yellow")
        return
    asigs = meta["asigs"]
    
    # Menú secuencial: primero asignatura
    asigs_with_entries = {}
    for e in entries:
        asigs_with_entries.setdefault(e["asig"], []).append(e)
    
    asig_choices = [questionary.Choice(f"{asig} ({len(lst)} temas)", asig)
                    for asig, lst in sorted(asigs_with_entries.items())]
    selected_asig = questionary.select("Selecciona la asignatura:", choices=asig_choices).ask()
    if not selected_asig: return
    
    # Luego el tema
    tema_choices = [questionary.Choice(f"T{e['tema']:02d} — {e.get('repasos', 0)} repasos", e["id"])
                    for e in sorted(asigs_with_entries[selected_asig], key=lambda x: x["tema"])]
    eid = questionary.select("Selecciona el tema:", choices=tema_choices).ask()
    if not eid: return
    
    entry = next((e for e in entries if e["id"] == eid), None)
    n_rep = entry.get("repasos", 0)
    hist  = entry.get("history", [])
    scrs  = entry.get("scores", [])
    dts   = entry.get("dates", [])
    
    if n_rep == 0:
        cprint(f"\n  {entry['asig']} T{entry['tema']:02d} — sin repasos hechos aún.\n", "yellow")
        return
    
    dif_colors = {"normal": "dim", "facil": "green", "dificil": "red"}
    dif_labels = {"normal": "NORMAL", "facil": "FÁCIL", "dificil": "DIFÍCIL"}
    
    if RICH:
        color = asig_color(entry['asig'])
        t = Table(
            title=f"{entry['asig']} — Tema {entry['tema']:02d}",
            box=box.SIMPLE, show_header=True, header_style="bold",
            title_style=f"bold {color}"
        )
        t.add_column("Rep",    justify="center", style="dim")
        t.add_column("Fecha",  justify="center")
        t.add_column("Dificultad", justify="center")
        t.add_column("Test",   justify="center")
        
        score_idx = 0
        for i in range(n_rep):
            fecha = dts[i] if i < len(dts) else "Desconocida"
            dif   = hist[i] if i < len(hist) else "normal"
            
            score_txt = "—"
            if i < len(scrs):
                score_txt = f"{scrs[score_idx]:.0f}%"
                score_idx += 1
            
            color = dif_colors.get(dif, "dim")
            label = dif_labels.get(dif, dif.upper())
            t.add_row(
                f"#{i+1}",
                fecha,
                Text(label, style=color),
                score_txt
            )
        
        nr = get_next_repaso(entry)
        estado = Text("AFIANZADO ✓", "bold green") if nr is None else Text(f"Próximo: {nr}", "yellow")
        console.print()
        console.print(t)
        console.print(f"  Estado actual: ", end=""); console.print(estado)
        print()
    else:
        print(f"\n[{entry['asig'].upper()} T{entry['tema']:02d}]")
        score_idx = 0
        for i in range(n_rep):
            fecha = dts[i] if i < len(dts) else "Desconocida"
            dif   = (hist[i] if i < len(hist) else "normal").upper()
            score_txt = f"{scrs[score_idx]:.0f}%" if score_idx < len(scrs) else "—"
            if score_idx < len(scrs): score_idx += 1
            print(f"  #{i+1} │ {fecha} │ {dif:8} │ {score_txt}")
        print()

@app.command(name="remove")
def cmd_remove():
    """Eliminar un tema registrado."""
    entries, archived, meta = load()
    entries_sorted = sorted(entries, key=lambda x: (x["asig"], x["tema"]))
    choices = []
    current_asig = None
    for e in entries_sorted:
        if e["asig"] != current_asig:
            current_asig = e["asig"]
            choices.append(questionary.Separator(f"\n── {current_asig} ──"))
        choices.append(questionary.Choice(f"Tema {e['tema']:02d} (rep {format_rep(e.get('repasos',0))})", e["id"]))
    if not choices: return
    eid = questionary.select("Selecciona el tema a eliminar:", choices=choices).ask()
    if not eid: return

    entry = next((e for e in entries if e["id"] == eid), None)
    if entry and questionary.confirm(f"Vas a eliminar {entry['asig']} T{entry['tema']}. ¿Seguro?").ask():
        entries.remove(entry)
        save(entries, archived, meta)
        cprint(f"\n  ✓ Eliminado.\n", "green")

@app.command(name="list")
def cmd_list():
    """Mostrar la lista de todos los temas registrados."""
    entries, _, meta = load()
    if not entries:
        print("\n  Sin temas registrados aún.\n")
        return
    asigs = meta["asigs"]
    by_asig = defaultdict(list)
    for e in entries: by_asig[e["asig"]].append(e)

    if RICH:
        tables = []
        for asig in sorted(asigs.values()):
            elist = sorted(by_asig.get(asig, []), key=lambda x: x["tema"])
            if not elist: continue
            color = asig_color(asig)

            pendientes = [e for e in elist if not is_afianzado(e)]
            n_afianzados = len(elist) - len(pendientes)

            t = Table(title=asig, box=box.SIMPLE, show_header=True, header_style="bold",
                      title_style=f"bold {color}", padding=(0, 1))
            t.add_column("Tema", justify="center", style="dim")
            t.add_column("Rep",  justify="center")
            t.add_column("Prog", justify="left")
            t.add_column("Cuándo", justify="right")

            for e in pendientes:
                nr    = get_next_repaso(e)
                diff  = days_diff(nr)
                rep   = e.get("repasos", 0) + 1
                total = max(4, rep)
                bar   = "█" * min(rep, total) + "░" * (total - min(rep, total))

                if diff < 0:
                    when = Text(f"ATRASADO +{abs(diff)}d", style="bold red")
                    bcol = "red"
                elif diff == 0:
                    when = Text("HOY", style="bold yellow")
                    bcol = "yellow"
                elif diff <= 3:
                    when = Text(f"en {diff}d", style="yellow")
                    bcol = "yellow"
                else:
                    when = Text(f"en {diff}d", style="dim")
                    bcol = "dim"

                t.add_row(
                    f"T{e['tema']:02d}",
                    format_rep(rep),
                    f"[{bcol}][{bar}][/]",
                    when
                )

            if n_afianzados:
                label = f"✓ {n_afianzados} afi." if n_afianzados == 1 else f"✓ {n_afianzados} afi."
                t.add_row("", "", "", Text(label, style="green dim"))

            tables.append(t)

        if tables:
            grid = Table.grid(padding=(1, 5))
            grid.add_column(justify="left", vertical="top")
            grid.add_column(justify="left", vertical="top")

            for i in range(0, len(tables), 2):
                left  = tables[i]
                right = tables[i+1] if i+1 < len(tables) else ""
                grid.add_row(left, right)

            console.print(grid)
            print()
    else:
        for asig in sorted(asigs.values()):
            elist = sorted(by_asig.get(asig, []), key=lambda x: x["tema"])
            if not elist: continue
            print(f"\n[{asig.upper()}]")
            n_af = 0
            for e in elist:
                nr = get_next_repaso(e)
                if nr is None:
                    n_af += 1
                    continue
                diff  = days_diff(nr)
                rep   = e.get("repasos", 0) + 1
                rep_s = format_rep(rep)
                total = max(4, rep)
                bar   = "█" * min(rep, total) + "░" * (total - min(rep, total))
                if diff < 0:    print(f"  T{e['tema']:02d}  {rep_s}  [{bar}]  ATRASADO +{abs(diff)}d")
                elif diff == 0: print(f"  T{e['tema']:02d}  {rep_s}  [{bar}]  HOY")
                else:           print(f"  T{e['tema']:02d}  {rep_s}  [{bar}]  en {diff}d")
            if n_af: print(f"  ✓ {n_af} afianzado{'s' if n_af>1 else ''}")
        print()

@app.command(name="stats")
def cmd_stats():
    """Mostrar estadísticas y gráfico de carga de repaso."""
    entries, _, meta = load()
    today = get_today()
    total = len(entries)
    afianzados = sum(1 for e in entries if is_afianzado(e))
    pendientes = sum(1 for e in entries if (nr := get_next_repaso(e)) and days_diff(nr) <= 0)
    pct = int(afianzados / total * 100) if total else 0
    streak = meta.get("streak", 0)

    if RICH:
        left_txt = f"\n[bold]Temas totales   :[/] {total}\n[bold]Afianzados      :[/] [green]{afianzados}[/] ({pct}%)\n[bold]Pendientes hoy  :[/] [red]{pendientes}[/]\n"
        if streak: left_txt += f"[bold]Racha actual    :[/] [yellow]🔥 {streak} días[/]\n"
        bar_width = 25
        filled = int(bar_width * afianzados / total) if total else 0
        left_txt += f"\n[bold]Progreso:[/] \n[{'█'*filled}{'░'*(bar_width-filled)}] {pct}%"
        
        carga = defaultdict(list)
        for e in entries:
            nr = get_next_repaso(e)
            if nr and 0 <= days_diff(nr) <= 6: carga[days_diff(nr)].append(e)

        dias_semana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        max_count = max((len(v) for v in carga.values()), default=1)
        right_txt = ""
        for d in range(7):
            fecha = today + timedelta(days=d)
            label = "Hoy" if d == 0 else dias_semana[fecha.weekday()]
            n = len(carga.get(d, []))
            bar_len = int(n / max_count * 15) if max_count else 0
            color = "bold red" if d == 0 and n > 0 else "yellow" if n > 3 else "cyan"
            right_txt += f"{label} {fecha.strftime('%d/%m')}  [{color}]{'▓'*bar_len:<15}[/] {n}\n"

        cols = Columns([
            Panel(left_txt, title="Estadísticas Generales", border_style="blue"),
            Panel(right_txt, title="Carga Próximos 7 Días", border_style="magenta")
        ], expand=True)
        
        weak_points = []
        risk_points = []
        for e in entries:
            c_dif = e.get("history", []).count("dificil")
            if c_dif > 0: weak_points.append((e, c_dif))
            
            scrs = e.get("scores", [])
            if scrs:
                avg = sum(scrs) / len(scrs)
                if avg < 60: risk_points.append((e, avg))
                
        weak_points.sort(key=lambda x: x[1], reverse=True)
        risk_points.sort(key=lambda x: x[1])
        
        if weak_points:
            wp_txt = "\n".join(f"[yellow]• {e['asig']} T{e['tema']:02d}[/] ([dim]{c}x difícil[/dim])" for e, c in weak_points[:5])
        else:
            wp_txt = "[green]✓ No hay puntos débiles detectados aún.[/green]"
        wp_panel = Panel(wp_txt, title="⚠️ Puntos Débiles (Percepción)", border_style="yellow")
            
        if risk_points:
            rp_txt = "\n".join(f"[bold red]• {e['asig']} T{e['tema']:02d}[/] ([dim]Media: {avg:.0f}%[/dim])" for e, avg in risk_points[:5])
        else:
            rp_txt = "[green]✓ No hay temas en riesgo real detectados.[/green]"
        rp_panel = Panel(rp_txt, title="🚨 Temas en Riesgo (Tests < 60%)", border_style="red")
        
        from rich.console import Group
        
        bottom_cols = Columns([wp_panel, rp_panel], expand=True)
        console.print(Panel(Group(cols, bottom_cols), title="[bold]📊 Dashboard de Repaso[/]", expand=True))

@app.command(name="subject")
def cmd_subject():
    """Gestionar asignaturas del curso actual."""
    entries, archived, meta = load()
    asigs = meta["asigs"]
    
    action = questionary.select(
        "¿Qué quieres hacer?",
        choices=["Ver asignaturas", "Añadir/Editar asignatura", "Eliminar asignatura"]
    ).ask()
    if not action: return
    
    if action == "Ver asignaturas":
        for k, v in asigs.items(): print(f"  {k:6} → {v}")
    elif action == "Añadir/Editar asignatura":
        clave = questionary.text("Clave corta (ej. 'prog'):").ask()
        if not clave: return
        nombre = questionary.text("Nombre completo (ej. 'Programación'):").ask()
        if nombre:
            asigs[clave.lower()] = nombre
            save(entries, archived, meta)
            cprint(f"✓ Guardado: {clave} -> {nombre}", "green")
    elif action == "Eliminar asignatura":
        clave = questionary.select("Selecciona la asignatura a eliminar:", choices=[questionary.Choice(f"{v} ({k})", k) for k, v in asigs.items()]).ask()
        if clave and questionary.confirm(f"Eliminar '{asigs[clave]}'?").ask():
            del asigs[clave]
            save(entries, archived, meta)
            cprint("✓ Eliminado", "green")

@app.command(name="archive")
def cmd_archive():
    """Archivar el curso activo actual."""
    entries, archived, meta = load()
    if not entries: 
        cprint("\n  No hay temas activos para archivar.\n", "yellow")
        return
    nombre = questionary.text("Nombre del curso a archivar (ej: DAW Año 1):").ask()
    if not nombre or not questionary.confirm(f"¿Archivar '{nombre}' con {len(entries)} temas?").ask(): return
    archived.append({
        "nombre": nombre, "fecha_archivo": str(get_today()),
        "temas": entries, "total": len(entries),
        "afianzados_al_archivar": sum(1 for e in entries if is_afianzado(e)),
        "asigs": meta.get("asigs", DEFAULT_ASIGS).copy()
    })
    save([], archived, meta)
    cprint("✓ Curso archivado. Tu entorno está limpio para el nuevo año.", "green")

@app.command(name="unarchive")
def cmd_unarchive():
    """Restaurar un curso archivado."""
    entries, archived, meta = load()
    if not archived: 
        cprint("\n  No hay cursos archivados.\n", "yellow")
        return
    choices = [questionary.Choice(f"{c['nombre']} ({c['total']} temas, {c['fecha_archivo']})", i) for i, c in enumerate(archived)]
    idx = questionary.select("Selecciona el curso a restaurar:", choices=choices).ask()
    if idx is None: return
    
    curso_restore = archived[idx]
    if questionary.confirm(f"¿Restaurar '{curso_restore['nombre']}'? El curso activo actual pasará al archivo.").ask():
        new_archived = list(archived)
        new_archived.pop(idx)
        if entries:
            nombre_actual = f"Activo {get_today()}"
            new_archived.append({
                "nombre": nombre_actual, "fecha_archivo": str(get_today()),
                "temas": entries, "total": len(entries),
                "afianzados_al_archivar": sum(1 for e in entries if is_afianzado(e)),
                "asigs": meta.get("asigs", DEFAULT_ASIGS).copy()
            })
        if "asigs" in curso_restore: meta["asigs"] = curso_restore["asigs"].copy()
        save(curso_restore.get("temas", []), new_archived, meta)
        cprint("✓ Restaurado correctamente.", "green")

@app.command(name="courses")
def cmd_courses():
    """Mostrar la lista de cursos archivados."""
    _, archived, _ = load()
    if not archived:
        cprint("\n  No hay cursos archivados.\n", "yellow")
        return
    for c in archived: 
        print(f" - {c['nombre']} ({c['total']} temas, afianzados: {c['afianzados_al_archivar']})")

if __name__ == "__main__":
    app()