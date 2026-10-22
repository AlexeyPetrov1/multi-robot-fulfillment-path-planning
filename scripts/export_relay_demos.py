"""Export real checked scenarios to GIF, browser video and an offline gallery."""

import argparse
import hashlib
import html
import json
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from frontend.demo_catalog import DESCRIPTIONS, ORDER
from frontend.relay_media import create_media
from robotics.relay.examples import example_actions, example_scenarios
from robotics.services.relay_service import plan_mission, replay_mission


def _gallery(items):
    cards = []
    for item in items:
        key = html.escape(item["id"], quote=True)
        title = html.escape(item["title"])
        description = html.escape(item["description"])
        metrics = item["metrics"]
        result = (f"Доставлено {metrics['delivered_tasks']}/{metrics['total_tasks']} · "
                  f"{metrics['timesteps']} тактов · {metrics['transfer_count']} передач · "
                  f"{metrics['total_energy']:g} энергии")
        cards.append(f'''<article><h2>{title}</h2><p>{description}</p>
<video controls preload="metadata" poster="{key}.png"><source src="{key}.mp4" type="video/mp4"></video>
<p class="result">{result}</p><p><a href="{key}.gif">Открыть GIF</a> ·
<a href="{key}.mp4" download>Скачать видео</a> · <a href="{key}.json">Проверенный отчёт</a></p></article>''')
    return '''<!doctype html><html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Роботы: примеры работы</title>
<style>body{max-width:1120px;margin:auto;padding:32px 20px;background:#f1f5f9;color:#172554;font:17px/1.5 system-ui,sans-serif}
h1{font-size:34px;margin-bottom:8px}h2{font-size:23px;margin:0 0 8px}p{margin:8px 0 16px;color:#475569}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:24px}article{padding:24px;background:white;border-radius:18px;border:1px solid #e2e8f0}
video{width:100%;border-radius:12px;background:#e2e8f0}a{color:#2563eb}.result{font-size:15px;color:#0f766e}</style>
<h1>Как роботы выполняют задачи вместе</h1><p>Настоящие прогоны симулятора. В каждом видео видны груз, заряд, встреча и результат.
Плеер поддерживает паузу, перемотку и полный экран. Все файлы работают без сервера.</p><main>''' + "\n".join(cards) + "</main></html>"


def export_demos(output_dir, *, names=None, size=(960, 640), fps=12, tick_seconds=.8,
                 overwrite=False, append=False):
    output_dir = Path(output_dir)
    examples = example_scenarios()
    chosen = list(names) if names is not None else [k for k in ORDER if k in examples]
    if names is None:
        chosen += sorted(set(examples) - set(chosen))
    if not chosen or len(set(chosen)) != len(chosen) or set(chosen) - set(examples):
        raise ValueError("unknown or duplicate demo name")
    files = [output_dir / f"{key}.{ext}" for key in chosen for ext in ("gif", "mp4", "png", "json")]
    metadata = [output_dir / filename for filename in ("manifest.json", "index.html", "README.md", "demos.zip")]
    if not overwrite:
        for path in files + ([] if append else metadata):
            if path.exists():
                raise FileExistsError(f"previous demo preserved: {path}")
    items = []
    if append and (output_dir / "manifest.json").exists():
        items = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))["demos"]
        items = [item for item in items if item["id"] not in chosen]
        for item in items:
            if item["id"] not in examples:
                raise ValueError("unknown existing demo")
            for extension in ("gif", "mp4", "png", "json"):
                if not (output_dir / f"{item['id']}.{extension}").is_file():
                    raise FileNotFoundError(f"missing previous demo: {item['id']}.{extension}")
    output_dir.mkdir(parents=True, exist_ok=True)
    for key in chosen:
        actions = example_actions(key)
        report = (plan_mission(examples[key], max_timesteps=40, time_limit=20)
                  if actions is None else replay_mission(examples[key], actions))
        if report["status"] not in {"optimal", "no_plan", "completed"}:
            raise RuntimeError(f"demo {key}: search did not finish ({report['status']})")
        media = create_media(report, size=size, fps=fps, tick_seconds=tick_seconds)
        encoded = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
        (output_dir / f"{key}.json").write_bytes(encoded)
        for extension in ("gif", "mp4", "png"):
            (output_dir / f"{key}.{extension}").write_bytes(media["poster" if extension == "png" else extension])
        items.append({"id": key, "title": examples[key]["name"],
                      "description": DESCRIPTIONS.get(key, examples[key]["name"]),
                      "status": report["status"], "metrics": report["metrics"],
                      "plan_source": "search" if actions is None else "prepared_demo",
                      "duration_seconds": media["duration"],
                      "report_sha256": hashlib.sha256(encoded).hexdigest(),
                      "media_sha256": {ext: hashlib.sha256(media[ext]).hexdigest() for ext in ("gif", "mp4")}})
        print(f"{key}: {report['status']}, {report['metrics']['timesteps']} ticks")
    manifest = {"schema_version": 1, "demos": items}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "index.html").write_text(_gallery(items), encoding="utf-8")
    gallery = ["# Примеры работы роботов", "",
               "Откройте [видеогалерею](index.html) или скачайте [все примеры одним архивом](demos.zip).", ""]
    for item in items:
        key = item["id"]
        gallery += [f"## {item['title']}", "", item["description"], "",
                    f"![{item['title']}]({key}.gif)", "",
                    f"[Видео MP4]({key}.mp4) · [Отчёт симулятора]({key}.json)", ""]
    (output_dir / "README.md").write_text("\n".join(gallery), encoding="utf-8")
    with ZipFile(output_dir / "demos.zip", "w", ZIP_DEFLATED) as archive:
        files = [output_dir / f"{item['id']}.{ext}" for item in items
                 for ext in ("gif", "mp4", "png", "json")] + metadata
        for path in files:
            if path.name != "demos.zip":
                archive.write(path, path.name)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs" / "demos")
    parser.add_argument("--names", nargs="+")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--append", action="store_true", help="add examples without re-rendering existing recordings")
    args = parser.parse_args(argv)
    export_demos(args.output_dir, names=args.names, overwrite=args.overwrite, append=args.append)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
