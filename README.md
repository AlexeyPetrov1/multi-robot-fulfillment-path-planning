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

## Запуск (Windows)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run frontend/relay_app.py
```

Стенд откроется в браузере. Выберите сценарий или загрузите свой JSON, нажмите
«Построить и проверить план», прогон покажет интерактивный плеер. Плеер можно
скачать одним HTML-файлом, он открывается без сервера.

Из командной строки:

```powershell
python scripts/run_relay_mission.py --scenario scenarios/energy_relay.json --output artifacts/relay_energy.json
```

Тесты: `python -m pytest`.

Формат сценария и правила: [docs/relay_missions.md](docs/relay_missions.md).
