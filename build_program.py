import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))
from cx_programmer_mcp.cxt import CxtProject

SRC_ORIG = Path(__file__).parent / "project" / "template_kosong.cxp"
SRC  = Path(__file__).parent / "project" / "controller_penyiraman_dasar.cxp"
DEST = Path(__file__).parent / "project" / "controller_penyiraman_dasar.cxt"
PROG = "NewProgram1"


def add_rung(p, section, idx, comment, instructions):
    rungs = p.get_rungs(PROG, section, include_empty=True)
    if idx == 0 and len(rungs) == 1 and rungs[0]["empty"]:
        p.replace_rung(PROG, section, 0, instructions)
        p.set_rung_comment(PROG, section, 0, comment)
    else:
        p.insert_rung(PROG, section, idx, instructions)
        p.set_rung_comment(PROG, section, idx, comment)


def build_symbols(p):
    syms = [
        ("tombol_siram","0.00","BOOL","Tombol siram manual"),
        ("tombol_auto","0.01","BOOL","Tombol toggle mode otomatis"),
        ("pompa","100.00","BOOL","Output pompa penyiraman"),
        ("mode_auto","H0.00","BOOL","Flag mode otomatis aktif"),
        ("trigger_siram","W0.00","BOOL","Trigger siram aktif"),
        ("oneshot_1","W0.03","BOOL","One-shot jadwal 1"),
        ("oneshot_2","W0.04","BOOL","One-shot jadwal 2"),
        ("timer_siram","T0","BOOL","Timer durasi siram"),
        ("jam_rtc","W10","WORD","Jam BCD dari RTC"),
        ("menit_rtc","W11","WORD","Menit BCD dari RTC"),
        ("jam_1","D0","WORD","Jam jadwal 1 default=6"),
        ("menit_1","D1","WORD","Menit jadwal 1 default=0"),
        ("jam_2","D2","WORD","Jam jadwal 2 default=16"),
        ("menit_2","D3","WORD","Menit jadwal 2 default=0"),
        ("durasi_siram","D4","WORD","Durasi siram x100ms default=300"),
        ("tombol_pupuk","0.02","BOOL","Tombol pupuk manual"),
        ("pupuk","101.00","BOOL","Output solenoid pupuk"),
        ("tombol_lampu_on","0.03","BOOL","Tombol lampu ON manual"),
        ("tombol_lampu_off","0.04","BOOL","Tombol lampu OFF manual"),
        ("lampu","102.00","BOOL","Output lampu"),
        ("flag_lampu_manual","H0.01","BOOL","Flag lampu ON manual latch"),
        ("flag_lampu_auto","H0.02","BOOL","Flag lampu ON otomatis"),
        ("flag_lampu_override","H0.03","BOOL","Flag override paksa OFF lampu"),
        ("tombol_emergency","0.05","BOOL","Tombol emergency reset semua"),
        ("jam_lampu_on","D10","WORD","Jam nyala lampu default=18"),
        ("jam_lampu_off","D11","WORD","Jam mati lampu default=6"),
    ]
    for name, addr, dtype, comment in syms:
        try:
            p.upsert_symbol(addr, name, dtype, comment, "global")
        except Exception as e:
            print(f"  [WARN] {name}: {e}")


def build_section_penyiraman(p):
    S = "Penyiraman"
    add_rung(p, S, 0, "Init default hanya saat D4=0: D0=6 D1=0 D2=16 D3=0 D4=300",
        ["LD A200.11", "AND= D4 #0", "MOV(021) #6 D0", "MOV(021) #0 D1",
         "MOV(021) #16 D2", "MOV(021) #0 D3", "MOV(021) #300 D4"])
    add_rung(p, S, 1, "Pompa: manual (0.00) ATAU trigger otomatis (W0.00)",
        ["LD 0.00", "OR W0.00", "ANDNOT T0", "OUT 100.00"])
    add_rung(p, S, 2, "Toggle ON: tekan 0.01 aktifkan mode otomatis",
        ["LD 0.01", "ANDNOT H0.00", "SET H0.00"])
    add_rung(p, S, 3, "Toggle OFF: tekan 0.01 matikan mode otomatis",
        ["LD 0.01", "AND H0.00", "RSET H0.00"])
    add_rung(p, S, 4, "Baca RTC: jam dari A352 high byte -> W10",
        ["LD A200.12", "MOVB(082) A352 #1 W10"])
    add_rung(p, S, 5, "Baca RTC: menit dari A351 high byte -> W11",
        ["LD A200.12", "MOVB(082) A351 #1 W11"])
    add_rung(p, S, 6, "Reset one-shot saat menit bukan 0",
        ["LD<> W11 #0", "RSET W0.03", "RSET W0.04"])
    add_rung(p, S, 7, "Jadwal 1: jam=D0 menit=D1 mode ON belum siram -> trigger",
        ["LD= W10 D0", "AND= W11 D1", "AND H0.00", "ANDNOT W0.03", "SET W0.00", "SET W0.03"])
    add_rung(p, S, 8, "Jadwal 2: jam=D2 menit=D3 mode ON belum siram -> trigger",
        ["LD= W10 D2", "AND= W11 D3", "AND H0.00", "ANDNOT W0.04", "SET W0.00", "SET W0.04"])
    add_rung(p, S, 9, "Timer siram: durasi dari D4 x100ms",
        ["LD W0.00", "TIM T0 D4"])
    add_rung(p, S, 10, "Reset trigger setelah timer selesai",
        ["LD T0", "RSET W0.00"])


def build_section_pupuk(p):
    S = "Pupuk"
    # Input 0.02 = tombol pupuk manual (tekan = ON, lepas = OFF)
    # Output 101.00 = solenoid / pompa pupuk
    add_rung(p, S, 0, "Pupuk: tekan 0.02 -> output pupuk 101.00 ON",
        ["LD 0.02", "OUT 101.00"])


def build_section_lampu(p):
    S = "Lampu"
    # Address:
    #   Input  0.03  = tombol lampu ON manual (momentary)
    #   Input  0.04  = tombol lampu OFF manual (momentary)
    #   Output 102.00 = lampu
    #   H0.01  = flag lampu manual ON (latch)
    #   H0.02  = flag lampu auto ON
    #   H0.03  = flag override paksa OFF (manual beats auto)
    #   D10    = jam nyala default=18 (6 sore)
    #   D11    = jam mati  default=6  (6 pagi)
    # Jadwal crossing midnight: ON saat jam>=D10 ATAU jam<D11
    # Override: tekan OFF saat auto aktif -> lampu mati paksa sampai jadwal berikutnya

    # Rung 0: Init D10=18 D11=6 hanya saat D10=0 (fresh)
    add_rung(p, S, 0, "Init default lampu: D10=18 D11=6 (hanya saat D10=0)",
        ["LD A200.11", "AND= D10 #0", "MOV(021) #18 D10", "MOV(021) #6 D11"])

    # Rung 1: Manual ON - tekan 0.03 -> SET H0.01, batalkan override H0.03
    add_rung(p, S, 1, "Manual ON: tekan 0.03 -> lampu ON (SET H0.01, batal override)",
        ["LD 0.03", "SET H0.01", "RSET H0.03"])

    # Rung 2: Manual OFF - tekan 0.04 -> RSET H0.01, SET override H0.03
    add_rung(p, S, 2, "Manual OFF: tekan 0.04 -> lampu OFF paksa (RSET H0.01, SET H0.03)",
        ["LD 0.04", "RSET H0.01", "SET H0.03"])

    # Rung 3: Auto ON - jam >= D10 (sore/malam) -> SET H0.02
    add_rung(p, S, 3, "Auto ON: jam >= D10 (sore/malam) -> SET flag auto lampu",
        ["LD>= W10 D10", "SET H0.02"])

    # Rung 4: Auto OFF - siang (jam >= D11 AND jam < D10) -> RSET H0.02 + RSET override
    # Override di-reset saat siang agar jadwal malam berikutnya bisa jalan normal
    add_rung(p, S, 4, "Auto OFF: siang -> RSET flag auto + reset override H0.03",
        ["LD>= W10 D11", "AND< W10 D10", "RSET H0.02", "RSET H0.03"])

    # Rung 5: Output - (manual OR auto) AND NOT override -> 102.00
    add_rung(p, S, 5, "Output lampu: (H0.01 OR H0.02) AND NOT override H0.03 -> 102.00",
        ["LD H0.01", "OR H0.02", "ANDNOT H0.03", "OUT 102.00"])


def build_section_reset(p):
    S = "Emergency"
    # Input  0.05 = tombol emergency reset (momentary NO)
    # Efek: reset semua flag, DM ke 0 (init default akan jalan ulang scan berikutnya)
    # Rung 0: Tekan 0.05 -> reset semua output flag
    add_rung(p, S, 0, "Emergency: reset semua flag output (pompa, lampu, pupuk, mode auto)",
        ["LD 0.05", "RSET H0.00", "RSET H0.01", "RSET H0.02", "RSET H0.03",
         "RSET W0.00", "RSET W0.03", "RSET W0.04",
         "RSET 100.00", "RSET 101.00", "RSET 102.00"])
    # Rung 1: Tekan 0.05 -> reset DM ke 0 (init default jalan ulang scan berikutnya)
    add_rung(p, S, 1, "Emergency: reset DM jadwal ke 0 (init default akan jalan ulang)",
        ["LD 0.05",
         "MOV(021) #0 D0", "MOV(021) #0 D1", "MOV(021) #0 D2",
         "MOV(021) #0 D3", "MOV(021) #0 D4",
         "MOV(021) #0 D10", "MOV(021) #0 D11"])


def main():
    import shutil
    print(f"Loading  : {SRC_ORIG} -> {SRC}")
    shutil.copy2(SRC_ORIG, SRC)
    p = CxtProject.from_path(SRC)

    print("Setup    : rename + buat 4 sections")
    p.rename_section(PROG, "Section1", "Penyiraman")
    p.create_section(PROG, "Pupuk",  before_section="END")
    p.create_section(PROG, "Lampu",  before_section="END")
    p.create_section(PROG, "Emergency",  before_section="END")

    p.clear_symbols("global")
    print("Symbols  : membangun symbol table...")
    build_symbols(p)

    print("Rungs    : membangun program ladder...")
    build_section_penyiraman(p)
    build_section_pupuk(p)
    build_section_lampu(p)
    build_section_reset(p)

    print(f"Saving   : {DEST}")
    p.save_cxt(DEST)
    print(f"Saving   : {SRC}")
    p.save_cxp(SRC, backup=False)

    print("\n=== VERIFIKASI ===")
    q = CxtProject.from_path(DEST)
    val = q.validate()
    print(f"Validasi XML : {'OK' if val['ok'] else 'GAGAL'}")
    for sec_info in q.list_sections(PROG):
        sec = sec_info["name"]
        if sec == "END":
            continue
        rungs = q.get_rungs(PROG, sec, include_empty=False)
        print(f"\nSection [{sec}] - {len(rungs)} rung")
        for i, r in enumerate(rungs):
            n = len(r.get("instructions", []))
            c = r.get("comment", "")[:60]
            print(f"  Rung {i:2d}: {n:2d} instruksi | {c}")
    syms = q.list_symbols("global")
    print(f"\nSymbols  : {len(syms)} total")
    print(f"\nSelesai! File: {DEST}")


if __name__ == "__main__":
    main()
