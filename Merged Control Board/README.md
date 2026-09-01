# Maslow Mini — Merged Control Board

A third KiCad project that puts both existing boards on one PCB:

| Source | What it is | Files |
|---|---|---|
| `../Motor Controller Board/` | "Four Motor Control Board M5" — ESP32-S3, 4× DRV8876 belt-axis drivers, TCA9546A I²C mux, SD NAND, LM2596 3.3 V buck, XT60 inlet | **PCB only, no schematic** |
| `../KiCad Boards/` | "Driver Board 2026-08-01" — ESP32-S3, 2× MP6541A 3-phase drivers, MP2459 3.3 V buck, beam-break homing, vacuum control | schematic + PCB |

**Scope: schematic only.** There is no `.kicad_pcb` in this project yet — layout is the next step.

The merge is in two parts: joining the two circuits, and then removing the redundancy that a
single board makes pointless. **169 parts / 61 BOM lines → 156 parts / 53 BOM lines.**

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

## What was consolidated

Once both circuits sit on one board, some parts are doing the same job twice.

### One 3.3 V regulator

The driver board's `U2` was an **MP2459 — 0.5 A**, feeding an ESP32-S3-WROOM-1 that peaks around
355 mA on WiFi transmit. That rail had almost no margin before the merge. The motor board's
`U116` is an **LM2596-3.3 — 3 A**. Combined 3.3 V load across both sections is roughly 530 mA
typical, ~950 mA worst case, so the LM2596 carries both with ~3× headroom.

Deleted: `U2`, `L3` (47 µH), `D2` (catch), `D6` (OR-ing), `C80`, `C81`, `R61`, `R62`, `R63`.
`D7` is kept and now ORs the driver USB port's VBUS into the shared `VIN_BUCK`, so either USB
port can still power the whole board. `+3V3_MC` and `+3V3_DRV` are gone; there is one `+3V3`.

### One reset

The motor MCU had no reset button at all — just an RC on `EN`. Both `EN` pins now share one net
(`RST`) driven by `SW2`, with `R28` (10 kΩ) and `C134` (1 µF) as the single RC. `R128` and `C30`
are deleted. The 1 µF is kept over the driver board's 100 nF because that is the value
Espressif's design guide asks for.

### One power-on LED, one Schottky part number

`D101` + `R115` deleted; the driver section's `LED2` + `R17` is kept (3.6 mA rather than 11 mA,
and the LED was explicitly specified for low forward voltage on a 3.3 V rail). `D102`/`D103`
change from SS14 (40 V / 1 A) to the SS36 (60 V / 3 A) already used by `D7` — one BOM line
instead of two, and more margin on a 24 V rail that also carries six motor stages.

### Summary

| | parts | BOM lines |
|---|---|---|
| MP2459 buck chain | 9 | 6 |
| second power-on LED | 2 | 1 |
| second EN RC | 2 | 0 |
| SS14 → SS36 | 0 | 1 |
| **total** | **13** | **8** |

Nothing was added.

## What stays separate

Each section keeps its own ESP32-S3, its own USB-C programming port and its own boot button
(`BOOT_MC` / `BOOT_DRV`). Combining the two MCUs was explicitly out of scope. Combining the two
USB ports would need a hub IC — a net part *increase* — or flashing the driver MCU through the
motor MCU, which costs firmware work and makes recovery from a bad flash harder.

Also deliberately untouched: the VIN bulk capacitance. `C140` (680 µF) and `C72`/`C73`
(2× 220 µF) were sized as two independent reservoirs because a header sat between them, and one
of the 220 µF is probably surplus now — but that is a ripple-current question, not a schematic
one. The ten 1 kΩ I2C pull-ups are also unchanged; each mux channel needs its own pair, though
1 kΩ is unusually strong (2.2–4.7 kΩ is conventional).

## Two consequences of running one regulator

1. **USB-only power is tighter.** Each buck used to have its own port's 500 mA. Now both MCUs
   run from whichever single port is plugged in — fine for flashing (~230 mA from 5 V), close to
   the limit with both radios live (~460 mA). Plugging in both ports does not help; the diode-OR
   takes only the higher one.
2. **Dropout on USB power.** The LM2596 needs roughly Vout + 1.5–2 V. 5 V minus cable sag minus
   the OR-ing diode leaves ~4.3 V at high load. Fine at flashing currents, marginal at full load.
   This already existed on the motor board; merging just makes more depend on it.

## Naming

| Original | Merged | Why |
|---|---|---|
| motor `VCC` | `VIN` | merges with the driver rail H1 used to carry |
| motor `3V3`, driver `3V3` | `+3V3` | one regulator now, so one rail |
| motor `MCU_RST`, driver `RST` | `RST` | one reset for both MCUs |
| motor `U16_1`, driver `VIN_BUCK` | `VIN_BUCK` | one buck input, fed by three OR-ing diodes |
| motor `BOOT` | `BOOT_MC` | each MCU keeps its own boot button |
| driver `BOOT` | `BOOT_DRV` | " |
| motor `L2_1`, `U2_6`… | `SW_BUCK`, `IPROPI_TR`… | the source PCB had auto-generated net names |

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
placement, same graphics for everything that survives. The edits are: delete the listed symbols,
convert the two surviving BoardCom labels to hierarchical pins, rename `3V3`/`BOOT`, and retarget
the instance paths at this project. Everything the deletions leave behind — labels that sat on a
deleted pin, wires with nothing at one end, junctions in a wholly removed branch — is found by
walking the sheet's connectivity graph rather than by hard-coded position, so the script stays
correct if the source schematic moves. Two cosmetic repairs come with that: `D7`'s reference and
value text had been parked at `D2`'s position by whoever added those diodes, and was re-seated
next to `D7` once `D2` went; and the block captioned "3.3V Regulator / 200ma LDO / Power OR-ing
with PMOS" — describing an arrangement this schematic never actually contained — is retitled
"3.3 V DECOUPLING" with the stale notes removed.

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
electrically common. Every intentional change is declared in that script and applied to the
expectation, so anything else that moved would show up as a mismatch. Current result:

```
declared deletions: 15 parts
expected multi-pin nets: 124   actual: 124
EXACT MATCH - every remaining source net is reproduced, and nothing beyond the
declared changes was altered.
```

The thirteen pins the merged schematic carries that the sources do not are pads that were
simply unconnected on the source PCB and are now explicit: `SW101` 1/3, `U109` 1/7 (SD NAND
DAT1/DAT2, unused in SPI mode), `USB102` A8/B8 (SBU), and seven spare ESP32 IOs on `U110`.

ERC over the whole project: 203 findings, all inherited from the driver board's EasyEDA import —
`pin_to_pin` and `pin_not_driven` caused by that library typing its pins *Unspecified*,
`endpoint_off_grid` on that sheet's original geometry, and one `power_pin_not_driven` on its
`#PWR01` ground symbol. There are **no** dangling labels, dangling wires, unconnected wire
endpoints, unresolved symbols or missing footprint links; the driver board's own pre-merge
baseline had 8 unconnected wire endpoints and 4 dangling wires, which the deletion cleanup
removed. The motor-control sheet contributes zero off-grid endpoints.

## Deliberate correction

The LM2596's TO-263 tab (`U116` pad 6) was left with no net on the source PCB. The tab is
internally GND on that package, so it is bonded to GND here. This is the one place the merged
netlist intentionally differs from the source; `tools/verify_netlist.py` accounts for it
explicitly.

## Worth a look before layout

* Two 3.3 V regulators and two USB-C ports on one board is redundant. Keeping them was the
  conservative choice for a merge — revisit if you want to slim the BOM.
* The remaining LEDs do not agree on polarity: `LED102` is wired anode-on-pin-1, `LED103`
  anode-on-pin-2. That is reproduced from the source PCB (different footprints), but it is worth
  confirming against the parts you actually buy.
* `10uF / C0805` still appears as two BOM lines because both project libraries carry a `C0805`
  footprint. Their pads differ by 0.0001 mm — they are the same EasyEDA export — so pointing all
  the passives at one library would collapse that line, and several others. Not done here
  because it touches every passive's footprint field.
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
