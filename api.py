"""
Safe PLC Project API for High-Level Scripting and Agent Interaction.
100% self-contained within mcp package.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any

import os
import subprocess

CX_PROGRAMMER_PATHS = [
    Path(r"C:\Program Files (x86)\OMRON\CX-One\CX-Programmer\CX-P.exe"),
    Path(r"C:\Program Files\OMRON\CX-One\CX-Programmer\CX-P.exe"),
]

def get_cxp_executable(custom_path: str | Path | None = None) -> Path | None:
    if custom_path:
        p = Path(custom_path).resolve()
        if p.is_file():
            return p
        if (p / "CX-P.exe").is_file():
            return p / "CX-P.exe"

    env_path = os.environ.get("OMRON_CXP_PATH")
    if env_path:
        p = Path(env_path).resolve()
        if p.is_file():
            return p
        if (p / "CX-P.exe").is_file():
            return p / "CX-P.exe"

    for p in CX_PROGRAMMER_PATHS:
        if p.exists():
            return p
    return None

def is_cx_programmer_running() -> bool:
    try:
        output = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq CX-P.exe"], text=True, errors="ignore")
        return "CX-P.exe" in output
    except Exception:
        return False

def close_cx_programmer(force: bool = False) -> bool:
    """NEVER kill CX-Programmer. User requested CX-P to remain open at all times."""
    return False

def open_cx_programmer(project_path: str | Path, custom_exe: str | Path | None = None) -> bool:
    exe = get_cxp_executable(custom_exe)
    if not exe:
        return False
    target = Path(project_path).resolve()
    if target.with_suffix(".cxp").exists():
        target = target.with_suffix(".cxp")
    try:
        subprocess.Popen([str(exe), str(target)], cwd=str(exe.parent))
        return True
    except Exception:
        return False


try:
    from .engine import CxtEngine, CxtBlockError
    from .cp1e import parse_address_info
except ImportError:  # Supports direct CLI execution from this directory.
    from engine import CxtEngine, CxtBlockError
    from cp1e import parse_address_info

class SafePlcProject:
    """Safe, high-level project manager for Omron PLC CXP/CXT projects."""

    def __init__(self, target_path: str | Path = "project/Traffic_Light.cxt", auto_reload_cxp: bool = False, cxp_exe_path: str | Path | None = None):
        self.cxt_path = Path(target_path).resolve()
        
        # Auto reload and force killing CX-Programmer is completely disabled
        self.auto_reload_cxp = False
        self.cxp_exe_path = cxp_exe_path
        if self.cxt_path.suffix.lower() == ".cxp":
            self.cxp_path = self.cxt_path
            self.cxt_path = self.cxt_path.with_suffix(".cxt")
        else:
            self.cxp_path = self.cxt_path.with_suffix(".cxp")

        # Load from .cxt if exists, else from .cxp, else initialize from blank template
        if not self.cxt_path.exists() and not self.cxp_path.exists():
            template_path = Path(__file__).resolve().parent / "templates" / "CP1E" / "CP1E-NA.cxt"
            if template_path.exists():
                self.cxt_path.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy(template_path, self.cxt_path)
            load_from = self.cxt_path
        else:
            load_from = self.cxt_path if self.cxt_path.exists() else self.cxp_path

        self.engine = CxtEngine.from_path(load_from)
        programs = self.engine.list_programs()
        if not programs:
            raise CxtBlockError("Project contains no program")
        self.program_name = programs[0]["name"]

    def summary(self) -> dict[str, Any]:
        """Dapatkan ringkasan program, section, dan jumlah rung secara ringkas."""
        sections = self.engine.list_sections(self.program_name)
        symbols = self.engine.list_symbols("global")
        hw = self.get_hardware_profile()
        return {
            "file": str(self.cxt_path),
            "program": self.program_name,
            "hardware": hw["name"],
            "sections": sections,
            "total_symbols": len(symbols),
        }

    def get_hardware_profile(self) -> dict[str, Any]:
        """Dapatkan profil hardware PLC yang terdeteksi dari Config."""
        return self.engine.get_hardware_profile()

    def simulate_scan(self, section: str, inputs: dict[str, Any] | None = None, scans: int = 1) -> list[dict[str, Any]]:
        """Simulasikan eksekusi ladder pada section tertentu sebanyak N scan cycle."""
        try:
            from .simulator import LadderSimulator
        except ImportError:
            from simulator import LadderSimulator
        sim = LadderSimulator()
        rungs = self.engine.get_rungs(self.program_name, section)
        results = []
        for s in range(max(1, scans)):
            res = sim.run_scan(rungs, inputs if s == 0 else None)
            results.append(res)
        return results

    def list_sections(self) -> list[dict[str, Any]]:
        """Daftar section program aktif beserta jumlah rung-nya."""
        return self.engine.list_sections(self.program_name)

    def list_rungs(self, section: str, start: int = 0, count: int | None = None, mode: str = "summary") -> dict[str, Any]:
        """Baca batch rung dengan metadata pagination dan nomor tampilan 1-based."""
        if start < 0:
            raise ValueError("start harus >= 0")
        if count is not None and count < 0:
            raise ValueError("count harus >= 0")
        all_rungs = self.engine.get_rungs(self.program_name, section)
        if mode not in {"summary", "full"}:
            raise ValueError("mode harus 'summary' atau 'full'")
        end = start + count if count is not None else len(all_rungs)
        selected = all_rungs[start:end]
        items = [self._format_rung(rung, mode) for rung in selected]
        return {"section": section, "total": len(all_rungs), "start": start,
                "count": len(items), "has_more": end < len(all_rungs), "items": items}

    def get_rung(self, section: str, index: int, mode: str = "full") -> dict[str, Any]:
        """Ambil satu rung tanpa membaca seluruh section."""
        if index < 0:
            raise ValueError("index harus >= 0")
        result = self.list_rungs(section, index, 1, mode)
        if not result["items"]:
            raise IndexError(f"Rung index di luar batas: {section}/{index}")
        return result["items"][0]

    @staticmethod
    def _format_rung(rung: dict[str, Any], mode: str) -> dict[str, Any]:
        result = {"index": rung["index"], "display_number": rung["index"] + 1,
                  "comment": rung.get("comment", "")}
        if mode == "full":
            result.update({"instructions": rung.get("instructions", []), "sl_raw": rung.get("sl_raw", [])})
        else:
            result["instruction_count"] = len(rung.get("instructions", []))
            result["mnemonics"] = [line.split(":", 1)[0].strip().upper() for line in rung.get("instructions", []) if line.strip()]
        return result

    def analyze(self, section: str | None = None) -> dict[str, Any]:
        """Analisis konservatif komentar-vs-logika dan penulisan alamat."""
        return self.engine.analyze(self.program_name, section)

    def set_symbol(self, address: str, name: str, data_type: str = "BOOL", comment: str = ""):
        """Tambah atau perbarui simbol memori tanpa merusak VariableCount."""
        return self.engine.upsert_symbol(address, name=name, data_type=data_type, comment=comment)

    def delete_symbol(self, address_or_name: str) -> bool:
        """Hapus simbol berdasarkan alamat atau nama simbol dan otomatis perbarui VariableCount."""
        return self.engine.delete_symbol(address_or_name)


    def replace_rung(self, section: str, rung_index: int, instructions: list[str], comment: str = ""):
        """Ganti logika pada rung tertentu secara presisi."""
        self.engine.replace_rung(self.program_name, section, rung_index, instructions, comment=comment)

    def insert_rung(self, section: str, rung_index: int, instructions: list[str], comment: str = ""):
        """Sisipkan rung baru pada indeks tertentu (otomatis renumber & perbarui RC)."""
        self.engine.insert_rung(self.program_name, section, rung_index, instructions, comment=comment)

    def delete_rung(self, section: str, rung_index: int):
        """Hapus rung pada indeks tertentu (otomatis renumber & perbarui RC)."""
        self.engine.delete_rung(self.program_name, section, rung_index)

    def add_section(self, section_name: str, before_section: str = "END"):
        """Tambah section baru pada program aktif."""
        self.engine.add_section(self.program_name, section_name, before_section=before_section)

    def rename_section(self, old_name: str, new_name: str):
        """Ubah nama section pada program aktif."""
        self.engine.rename_section(self.program_name, old_name, new_name)

    def search(self, query: str, section: str | None = None, result_type: str = "all") -> list[dict[str, Any]]:
        """Cari kemunculan instruksi, address, atau keyword."""
        return self.engine.search(query, section=section, result_type=result_type)

    def validate(self) -> dict[str, Any]:
        """Validasi integritas AST dan header counter."""
        return self.engine.validate()

    def commit(self, backup: bool = True, reload_cxp: bool | None = None) -> dict[str, Any]:
        """
        Validasi integritas, lalu simpan ke .cxt dan .cxp secara serempak.
        Menghasilkan output sempurna tanpa resiko file korup.
        Opsional: reload_cxp=True (atau via konfigurasi self.auto_reload_cxp) akan menutup
        CX-Programmer sebelum menulis, dan membukanya kembali setelah file berhasil diperbarui.
        """
        val = self.validate()
        if not val["ok"]:
            raise CxtBlockError(f"Validasi gagal! Transaksi dibatalkan: {val['errors']}")

        # Safely save CXT/CXP pair to disk without killing CX-Programmer
        result = self.engine.save_pair(self.cxt_path, self.cxp_path, backup=backup)
        return {"ok": True, **result, "reopened_cxp": False}
    @classmethod
    def create_new_project(cls, target_path: str | Path, template_name: str = "CP1E-NA.cxt") -> "SafePlcProject":
        """Create a new .cxt/.cxp project file from a template in the templates/ folder."""
        target_cxt = Path(target_path).with_suffix(".cxt").resolve()
        target_cxp = target_cxt.with_suffix(".cxp")
        target_cxt.parent.mkdir(parents=True, exist_ok=True)

        # Search for template
        templates_dir = Path(__file__).resolve().parent / "templates"
        matched_templates = list(templates_dir.rglob(template_name))
        if not matched_templates:
            # Fallback search by key
            matched_templates = list(templates_dir.rglob("*.cxt"))
        
        if not matched_templates:
            raise FileNotFoundError(f"Template '{template_name}' not found in templates/ directory")

        src_template = matched_templates[0]
        import shutil
        shutil.copy(src_template, target_cxt)

        project = cls(target_cxt)
        project.commit(backup=False)
        return project

    def capture_screenshot(self, output_path: str | Path | None = None, auto_launch: bool = True) -> dict[str, Any]:
        """Capture a screenshot of CX-Programmer window for visual verification."""
        import subprocess
        from pathlib import Path

        if not output_path:
            out_file = Path(r"C:\Users\ricou\.gemini\antigravity\brain\85540553-45af-482c-bf3e-b6320bb9837e\real_cxp_screenshot.png")
        else:
            out_file = Path(output_path).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)

        ps_script = Path(r"C:\Users\ricou\capture_window.ps1")
        if ps_script.exists():
            cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps_script), "-TitleContains", "CX-Programmer", "-OutputPath", str(out_file)]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            out_str = proc.stdout.strip()
            if out_str.startswith("OK:"):
                return {"ok": True, "image_path": str(out_file), "window_title": out_str[3:], "file": str(self.cxp_path)}

        # Fallback to internal ladder renderer if window not found
        try:
            from ladder_renderer import render_rungs_preview
            first_sec = self.list_sections()["sections"][0]["name"]
            rungs = self.list_rungs(first_sec, start=0, count=4, mode="full")["items"]
            render_rungs_preview(first_sec, rungs, output_path=out_file)
            return {"ok": True, "image_path": str(out_file), "fallback_rendered": True, "file": str(self.cxp_path)}
        except Exception as exc:
            return {"ok": False, "error": f"Capture failed: {exc}"}

