# 📚 Repaso Tracker

CLI de repetición espaciada basado en el algoritmo **SM-2**, diseñado para estudiar de forma eficiente y con métricas reales de progreso.

## ✨ Características

- **Algoritmo SM-2 simplificado** con factor de dificultad acumulativo
- **Repasos dinámicos**: los temas difíciles generan repasos extras automáticamente
- **Registro de puntuaciones de test** (8/10, 85%, etc.) para métricas reales
- **Dashboard** con carga semanal, puntos débiles y temas en riesgo (nota < 60%)
- **Historial por tema**: ve cuándo repasaste cada cosa y con qué resultado
- **Colores por asignatura** y minibarra de progreso `[███░]`
- **Notificaciones de escritorio** (una vez al día, sin saturar)
- **Undo** del último repaso
- **Archivado de cursos** para empezar de cero cada año

## 🖥️ Compatibilidad

| Sistema | Estado | Notas |
|---------|--------|-------|
| **Linux** | ✅ Completo | Todas las funciones, incluidas notificaciones de escritorio |
| **macOS** | ✅ Completo | Sin notificaciones de escritorio (`notify-send` no disponible) |
| **Windows 10+ (Windows Terminal)** | ⚠️ Parcial | Funciona, pero sin notificaciones. Requiere Windows Terminal para ver bien los colores y los símbolos `█░` |
| **Windows (cmd.exe / PowerShell clásico)** | ❌ No recomendado | Problemas de renderizado con caracteres Unicode y ANSI |

## 📦 Requisitos del sistema

Antes de instalar, asegúrate de tener:

| Herramienta | Versión mínima | Cómo instalar |
|-------------|----------------|---------------|
| **Python** | 3.9+ | [python.org](https://www.python.org/downloads/) · `sudo apt install python3` (Debian/Ubuntu) |
| **pipx** | cualquiera | `sudo apt install pipx` · `brew install pipx` (Mac) · `pip install pipx` (Windows) |
| **notify-send** *(solo Linux, opcional)* | cualquiera | `sudo apt install libnotify-bin` |

> **¿Qué es pipx?** Es la herramienta recomendada para instalar aplicaciones CLI de Python sin contaminar el Python del sistema. Si no quieres usarla, puedes usar `pip install -e .` dentro de un entorno virtual.

## 🚀 Instalación

### Con pipx (recomendado)

```bash
git clone https://github.com/TU_USUARIO/repaso-tracker.git
cd repaso-tracker
pipx install -e .
```

### Con pip en un entorno virtual

```bash
git clone https://github.com/TU_USUARIO/repaso-tracker.git
cd repaso-tracker
python3 -m venv .venv
source .venv/bin/activate      # Linux/Mac
# .venv\Scripts\activate       # Windows
pip install -e .
```

Después de instalar, el comando `repaso` estará disponible en tu terminal.

> **Nota**: los datos se guardan en `~/.local/share/repaso/repaso_data.json` — fuera del repo, así tu historial es privado y no se sube a GitHub.

## 📖 Uso

```bash
repaso              # Ver repasos de hoy (comando por defecto)
repaso add          # Registrar un tema nuevo
repaso done         # Marcar un repaso como completado
repaso list         # Ver todos los temas con su estado
repaso stats        # Dashboard con estadísticas y carga semanal
repaso history      # Ver el historial completo de un tema
repaso undo         # Deshacer el último repaso
repaso remove       # Eliminar un tema
repaso subject      # Gestionar asignaturas
repaso archive      # Archivar el curso actual
repaso courses      # Ver cursos archivados
```

## 🧠 ¿Cómo funciona?

El tracker aplica el método de **repetición espaciada SM-2**:

1. Estudias un tema por primera vez → `repaso add`
2. Al día siguiente te recuerda que lo repases → `repaso done`
3. Eliges dificultad (Fácil / Normal / Difícil) y opcionalmente la nota del test
4. El siguiente repaso se calcula automáticamente (intervalos: 1 → 7 → 21 → 45 días)
5. Si marcas "Difícil", el intervalo se acorta. Si marcas "Fácil", se alarga.
6. Si en el último repaso dices "Difícil", el tracker añade un repaso extra en vez de darlo por afianzado.

## 📦 Dependencias

- [Typer](https://typer.tiangolo.com/) — CLI framework
- [Questionary](https://questionary.readthedocs.io/) — menús interactivos
- [Rich](https://rich.readthedocs.io/) — interfaz visual en terminal
