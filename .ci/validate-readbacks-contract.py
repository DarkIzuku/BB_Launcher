#!/usr/bin/env python3

from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
BACKEND_COMMIT = "c15eddd84c7d7e3b86849e353cfa396cf48da1a5"
BACKEND_HEADER_URL = (
    "https://raw.githubusercontent.com/DarkIzuku/shadp2p/"
    f"{BACKEND_COMMIT}/src/core/emulator_settings.h"
)
EXPECTED_MODES = {
    "Disabled": 0,
    "Relaxed": 1,
    "Precise": 2,
    "Optimized": 3,
}
EXPECTED_LABELS = ["Disabled", "Relaxed", "Precise", "Optimized (Experimental)"]


def parse_enum(source: str) -> dict[str, int]:
    match = re.search(r"enum GpuReadbacksMode\s*:\s*int\s*\{(?P<body>.*?)\};", source, re.S)
    if not match:
        raise AssertionError("GpuReadbacksMode enum was not found")

    body = re.sub(r"//.*", "", match.group("body"))
    modes: dict[str, int] = {}
    next_value = 0
    for entry in body.split(","):
        entry = entry.strip()
        if not entry:
            continue
        explicit = re.fullmatch(r"(?P<name>\w+)\s*=\s*(?P<value>\d+)", entry)
        if explicit:
            name = explicit.group("name")
            next_value = int(explicit.group("value"))
        else:
            name = entry
        modes[name] = next_value
        next_value += 1
    return modes


launcher_header = (ROOT / "settings/emulator_settings.h").read_text(encoding="utf-8-sig")
launcher_source = (ROOT / "settings/ShadSettings.cpp").read_text(encoding="utf-8")
settings_source = (ROOT / "settings/emulator_settings.cpp").read_text(encoding="utf-8")
ipc_source = (ROOT / "modules/ipc/ipc_client.cpp").read_text(encoding="utf-8")

with urllib.request.urlopen(BACKEND_HEADER_URL, timeout=30) as response:
    backend_header = response.read().decode("utf-8")

assert parse_enum(launcher_header) == EXPECTED_MODES
assert parse_enum(backend_header) == EXPECTED_MODES

combo = ET.parse(ROOT / "settings/ShadSettings.ui").find(
    ".//widget[@name='readbacksModeComboBox']"
)
assert combo is not None
labels = [item.findtext("property/string") for item in combo.findall("item")]
assert labels == EXPECTED_LABELS

for index, mode in enumerate(EXPECTED_MODES):
    pattern = (
        rf"setItemData\(\s*{index}\s*,\s*"
        rf"static_cast<int>\(GpuReadbacksMode::{mode}\)\s*\)"
    )
    assert re.search(pattern, launcher_source), f"Missing UI mapping {mode}={index}"

assert "currentData().toUInt()" in launcher_source
assert "SetReadbacksMode(readbacksMode, true)" in launcher_source
assert 'make_override<GPUSettings>("readbacks_mode"' in launcher_header
assert 'Common::GetShadUserDir() / "custom_configs"' in settings_source
assert "SaveGroupGameSpecific(m_gpu, gpuObj)" in settings_source
assert 'env.remove("SHADPS4_BLOODBORNE_RE_TRACE")' in ipc_source

print(
    "Readbacks contract OK: BBLauncher writes GPU.readbacks_mode=3 for "
    f"Optimized and matches DarkIzuku/shadp2p@{BACKEND_COMMIT}."
)
