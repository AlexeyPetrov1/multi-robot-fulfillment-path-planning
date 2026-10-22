"""Encode the recorded warehouse run without inventing mission state."""

import matplotlib.pyplot as plt
from PIL import Image

from frontend.plotting import draw_warehouse
from frontend.relay_media import encode_mp4


PHASES = {"initialized": "Начало", "assigned": "Задания назначены", "pickup": "К грузу",
          "loaded": "Груз получен", "delivery": "Доставка", "completed": "Доставка завершена"}


def create_warehouse_video(report):
    frames = []
    for snapshot in report["snapshots"]:
        figure = draw_warehouse(report["warehouse"], snapshot["robots"], {})
        figure.set_size_inches(9.6, 6.4)
        figure.set_dpi(100)
        figure.suptitle(f"Такт {snapshot['timestep']} · Волна {snapshot['wave']} · "
                        + PHASES.get(snapshot["phase"], snapshot["phase"]))
        figure.canvas.draw()
        frames.append(Image.frombytes("RGBA", figure.canvas.get_width_height(),
                                      figure.canvas.buffer_rgba()).convert("RGB"))
        plt.close(figure)
    if not frames:
        raise ValueError("recording contains no snapshots")
    return encode_mp4(frames + [frames[-1]] * 6, fps=3)
