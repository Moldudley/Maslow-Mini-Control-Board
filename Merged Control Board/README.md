# Maslow Mini — Merged Control Board

A third KiCad project that puts both existing boards on one PCB:

| Source | What it is | Files |
|---|---|---|
| `../Motor Controller Board/` | "Four Motor Control Board M5" — ESP32-S3, 4× DRV8876 belt-axis drivers, TCA9546A I²C mux, SD NAND, LM2596 3.3 V buck, XT60 inlet | **PCB only, no schematic** |
| `../KiCad Boards/` | "Driver Board 2026-08-01" — ESP32-S3, 2× MP6541A 3-phase drivers, MP2459 3.3 V buck, beam-break homing, vacuum control | schematic + PCB |

**Scope: schematic only.** There is no `.kicad_pcb` in this project yet — layout is the next step.

## The design decision you asked for

Both ESP32-S3 MCUs are retained. They are wired to each other **only** on the BoardCom pair,
which is exactly what the mated `H1` 2×5 headers used to carry:

| Merged net | Motor section | Driver section |
|---|---|---|
| `BOARDCOM_A` | `U110` pin 9 — IO16 | `U12` pin 31 — IO38 |
| `BOARDCOM_B` | `U110` pin 8 — IO15 | `U12` pin 32 — IO39 |

Note the crossover. On the original boards both headers carried a net called `BOARDCOM1` on
pins 1/3 and `BOARDCOM2` on pins 2/4 — but with the *opposite* assignment on each board, so
mating them swapped the pair. That swap is preserved here.

`H1` is deleted from both sections. Its remaining pins were power, so:

* pins 6/8/10 (`VIN` on the driver, `VCC` on the motor board) become **one shared `VIN` rail**
* pins 5/7/9 become **one shared `GND`**

## What stays separate

Everything else. In particular each section keeps its own MCU, its own USB-C programming
port and its own 3.3 V regulator — `+3V3_MC` (LM2596) and `+3V3_DRV` (MP2459) are two
different nets, exactly as they were when the boards were separate. Consolidating them onto
one regulator is a reasonable follow-up, but it is a design change, not a merge, so it was
not done here.

## Naming

| Original | Merged | Why |
|---|---|---|
| motor `VCC` | `VIN` | merges with the driver rail H1 used to carry |
| motor `3V3` | `+3V3_MC` | two independent regulators must not collide |
| driver `3V3` | `+3V3_DRV` | " |
| motor `BOOT` | `BOOT_MC` | each MCU has its own boot button |
| driver `BOOT` | `BOOT_DRV` | " |
| motor `U16_1`, `L2_1`, `U2_6`… | `VIN_BUCK_MC`, `SW_BUCK_MC`, `IPROPI_TR`… | the source PCB had auto-generated net names |

Motor-section reference designators are **the originals + 100** (`U2`→`U102`, `C7`→`C107`,
`CN3`→`CN103`, …). The driver section keeps its own designators unchanged; its highest was
`C82`, so nothing collides and you can still map any part back to its source board.

## Files

```
Maslow Mini Merged Board.kicad_pro    project
Maslow Mini Merged Board.kicad_sch    root sheet — the two sections + the BoardCom link
motor_control_section.kicad_sch       page 2
driver_section.kicad_sch              page 3
MaslowMerged.kicad_sym                symbols authored for the motor-control parts
MaslowMerged.pretty/                  footprints extracted from the motor board's PCB
ProPrj_Dri-easyedapro.kicad_sym       symbols carried over from the driver board
ProPrj_Dri-easyedapro.pretty/         footprints carried over from the driver board
tools/                                the scripts that generated all of the above
```

## How each section was produced

**Driver section** is the original schematic file, edited in place — same symbols, same
placement, same graphics. The only changes are the four listed above (delete `H1` and the ten
global labels that sat on its pins, convert the two surviving BoardCom labels to hierarchical
pins, rename `3V3`/`BOOT`, retarget the instance paths at this project).

**Motor control section** had to be reconstructed: that board exists only as a PCB. Its
connectivity here is taken pin-for-pin from `Four Motor Control Board M5_*.kicad_pcb`, and its
symbols were authored from the datasheet pinouts, each one cross-checked against how the PCB
actually wires the part (e.g. the 100 nF from DRV8876 pin 12 to VM identifies pin 12 as VCP,
which fixes the whole right-hand side of that package). Connectivity is drawn with a label on
every pin rather than routed wires — the same style the driver board's own EasyEDA-imported
schematic uses.

## Verification

`tools/verify_netlist.py` compares the merged schematic's netlist against both source boards
as a *partition of pins*, so net naming is irrelevant — what must match is which pins end up
electrically common. Current result:

```
expected multi-pin nets: 132   actual: 132
EXACT MATCH - every source net is reproduced and nothing extra was created.
```

The thirteen pins the merged schematic carries that the sources do not are pads that were
simply unconnected on the source PCB and are now explicit: `SW101` 1/3, `U109` 1/7 (SD NAND
DAT1/DAT2, unused in SPI mode), `USB102` A8/B8 (SBU), and seven spare ESP32 IOs on `U110`.

ERC over the whole project reports no dangling labels, no unresolved symbols and no missing
footprint links. What remains is inherited from the driver board's EasyEDA import and matches
its own pre-merge baseline: `pin_to_pin` and `pin_not_driven` warnings caused by that
library's pins being typed *Unspecified*, and `endpoint_off_grid` on that sheet's original
geometry. The motor-control sheet contributes zero off-grid endpoints.

## Deliberate correction

The LM2596's TO-263 tab (`U116` pad 6) was left with no net on the source PCB. The tab is
internally GND on that package, so it is bonded to GND here. This is the one place the merged
netlist intentionally differs from the source; `tools/verify_netlist.py` accounts for it
explicitly.

## Worth a look before layout

* Two 3.3 V regulators and two USB-C ports on one board is redundant. Keeping them was the
  conservative choice for a merge — revisit if you want to slim the BOM.
* The three LEDs do not agree on polarity: `D101` and `LED102` are wired anode-on-pin-1,
  `LED103` is anode-on-pin-2. That is reproduced from the source PCB (they use three different
  footprints), but it is worth confirming against the parts you actually buy.
* `R107` (1.5 kΩ, was `R7`) sits directly between `TRINAMICRX` and `TRINAMICTX` — the usual
  half-duplex TMC UART arrangement, carried over as-is.

## Regenerating

```bash
cd "Merged Control Board"
python3 tools/symlib.py MaslowMerged.kicad_sym
python3 tools/footprints.py
python3 tools/motor_sheet.py
python3 tools/driver_sheet.py
python3 tools/root_sheet.py
```

`motor_sheet.py` reads the analyzed motor PCB JSON and `driver_sheet.py` reads the original
driver schematic, so both regenerate from the source boards rather than from this project.
