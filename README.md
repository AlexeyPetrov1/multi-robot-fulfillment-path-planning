# Диспетчер передачи грузов между роботами

Ветка `clean`: только алгоритм и фронтенд. Роботы с конечной энергией развозят
грузы по графу склада, каждый груз хотя бы раз передаётся свободному роботу,
все роботы возвращаются на станции с резервом не меньше 10%. Любой план заново
проверяется симулятором.

## Состав

| Путь | Что там |
|---|---|
| `robotics/relay/` | Алгоритм: модель сценария (`model.py`), симулятор и правила (`simulator.py`), точный планировщик (`planner.py`), диспетчер длинных смен (`dispatch.py`) |
| `robotics/services/relay_service.py` | Планирование, повторная проверка и продолжение миссии, отчёт в JSON |
| `frontend/` | Streamlit-стенд (`relay_app.py`, `relay_workbench.py`) и интерактивный плеер (`relay_player.py`, `static/relay_player.html`) |
| `scenarios/` | Готовые сценарии и подготовленные планы |
| `scripts/run_relay_mission.py` | Запуск из командной строки без интерфейса |
| `scripts/build_grid16_team4_25.py` | Генератор сценария 16×16 на 25 заказов |
| `docs/relay_missions.md` | Правила, формат сценария и описание планировщиков |
| `tests/` | Тесты алгоритма и стенда |

## Как запустить

Нужен Python 3.11 или новее и git.

### 1. Переключиться на ветку

```powershell
cd "C:\Users\1\OneDrive\Рабочий стол\git\multi-robot-fulfillment-path-planning"
git checkout clean
```

### 2. Окружение и зависимости (один раз)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Если PowerShell запрещает запуск `Activate.ps1`, выполните один раз
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` или запускайте без активации
через `.venv\Scripts\python.exe` вместо `python`. В cmd активация: `.venv\Scripts\activate.bat`.
На Linux/macOS: `python3 -m venv .venv && source .venv/bin/activate`.

### 3. Стенд с плеером

```powershell
python -m streamlit run frontend/relay_app.py
```

Браузер откроется сам на http://localhost:8501 (если нет, откройте адрес вручную).
Дальше:

1. Выберите сценарий в списке «Проверочный сценарий» или загрузите свой JSON.
2. «Показать готовый прогон» заново проверяет сохранённый план (есть не у всех сценариев).
   «Построить и проверить план» считает маршруты с нуля.
3. Прогон показывает интерактивный плеер: пробел запускает и ставит на паузу,
   стрелки листают такты, с Shift переходят к соседнему событию, клик по роботу
   показывает его маршрут. «Скачать плеер (HTML)» сохраняет прогон одним файлом,
   который открывается без сервера.

Остановить стенд: Ctrl+C в терминале.

### 4. Без интерфейса, из командной строки

```powershell
python scripts/run_relay_mission.py --scenario scenarios/energy_relay.json --output artifacts/energy_relay.json
python scripts/run_relay_mission.py --scenario scenarios/grid16_team4_25.json --planner dispatch --output artifacts/shift.json
python scripts/run_relay_mission.py --resume artifacts/partial.json --output artifacts/continued.json
```

Скрипт печатает итог (доставлено, такты, энергия, передачи) и пишет отчёт в `--output`.
Существующий файл он не перезаписывает. `--resume` продолжает незавершённый
прогон из сохранённого отчёта с теми же позициями, грузами и зарядом. Планировщик: `--planner auto|exact|dispatch`,
пределы: `--max-timesteps`, `--max-states`, `--time-limit`. Отчёт можно открыть в стенде
через «Проверить готовый план или отдельное действие».

### 5. Тесты

```powershell
python -m pytest
```

Формат сценария и правила: [docs/relay_missions.md](docs/relay_missions.md).
