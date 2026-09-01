# DRV8316CRRGFR → MP6541A conversion

Schematic only. The PCB is untouched and needs a full re-layout of both driver
areas (VQFN-40 7×5mm → TQFN-26 6×6mm) plus the new buck section.

Datasheet reference: MP6541/MP6541A Rev 1.0, MPS, 11/12/2021.

---

## 1. Removed

| Ref | Part | Why |
|---|---|---|
| U1, U13 | DRV8316CRRGFR | Replaced by U14 / U15 |
| L1, L2 | 47µH | DRV8316 internal-buck inductors; one replacement (L3) now serves the whole board |
| C35, C64 | 22µF | Buck output caps, ditto |
| C26, C59 | 1µF | AVDD bypass — MP6541A has no AVDD LDO |
| C25, C58 | 1µF | DRV8316 CP cap — replaced by correctly-rated VCP caps |
| C27, C60 | 100nF | DRV8316 CPH/CPL flying cap — replaced by ≥VIN-rated CP1/CP2 caps |

Retired nets: `AVDD`, `AVDD2`, `CPL/CPH/CP`, `CPL2/CPH2/CP2`, `SW_BK2`,
`BUCK2`, and all SPI (`DRV_CLK`, `DRV_MOSI`, `DRV_MISO`, `DRV_CS1`, `DRV_CS2`).

`DRVOFF` and `VREF/ILIM` have no MP6541A equivalent and are gone.

## 2. Kept

U14/U15 were moved into the vacated U1/U13 positions. These survive unchanged:

- nSLEEP networks — R19/D1 (ch1), R34/D4 (ch2)
- nFAULT pull-ups — R25 (ch1), R38 (ch2). Still required: nFAULT is open-drain.
- Current-sense RC filters into the ESP32 ADC — R22–R24 + C-filters (ch1),
  R35–R37 + C61–C63 (ch2)
- USB/buck ORing — Q1, R32, R33, D3
- VIN bulk decoupling, motor phase connectors, TVS

## 3. Pin mapping

| DRV8316 | Net (ch1 / ch2) | MP6541A |
|---|---|---|
| 27 INHA / 28 INLA | AH1,AL1 / AH2,AL2 | 6 HSA / 3 LSA |
| 29 INHB / 30 INLB | BH1,BL1 / BH2,BL2 | 7 HSB / 4 LSB |
| 31 INHC / 32 INLC | CH1,CL1 / CH2,CL2 | 8 HSC / 5 LSC |
| 13,14 OUTA | PHA1 / PHA2 | 9, 26 SA |
| 16,17 OUTB | PHB1 / PHB2 | 11, 24 SB |
| 19,20 OUTC | PHC1 / PHC2 | 13, 22 SC |
| 9,10,11 VM | VIN | 23, 25 VIN |
| 22 nFAULT | NFAULT / NFAULT2 | 1 |
| 23 nSLEEP | NSLEEP / NSLEEP2 | 2 |
| 40,39,38 SOA/B/C | SOA…SOC / SOA2…SOC2 | 15, 16, 17 |
| 12,15,18 PGND | GND | 10, 12 LSS + 18 GND |

LSS (pins 10, 12) is tied directly to GND per the datasheet — no shunt.

## 4. Added — charge pump and gate drive (per channel)

Values are the datasheet's Table 3 requirements.

| Ref | Value | Connection | Note |
|---|---|---|---|
| C1 / C4 | 1µF 16V X7R | VCP → VIN | min 1µF, min 10V |
| C2 / C5 | 100nF X7R | CP1 ↔ CP2 | **must be rated ≥ VIN** |
| C3 / C6 | 4.7µF 10V X7R | VG → GND | datasheet allows 4.7–10µF |

## 5. Added — current-sense bias (12 resistors)

MP6541A's SOx pins *source or sink current*, unlike the DRV8316's voltage
outputs. Each needs a termination resistor to a reference voltage:

`VSOUT = VREF + (RREF × ILOAD) / 11,000`

I used the datasheet's ratiometric arrangement — two equal resistors to 3V3 and
GND on each SOx node (R1, R4–R14). 3.3kΩ each gives VREF = 1.65V and
RREF = 1.65kΩ, so ±8A maps to roughly 1.65V ±1.2V — full-scale on a 3.3V ADC
with headroom. Datasheet minimums are 1.8kΩ pull-up / 1kΩ pull-down, so 3.3kΩ
clears both. Your existing 330Ω + 22pF filters stay in series after this node.

**Your old 330Ω resistors alone would have violated the minimum load
impedance** — that's why the extra parts are here.

## 6. Added — replacement buck (U2, MP2459GJ-Z)

The DRV8316's internal buck was the board's only VIN→5V path
(`VIN → SW_BK → L1 → BUCK → Q1 → 5V → U10 → 3V3`). The MP6541A has no such
regulator, so this rebuilds it discretely and reuses the existing Q1 ORing
network and U10 LDO untouched.

MP2459: 4.5–55V in, 0.5A, 480kHz, SOT-23-6. Chosen for headroom over your
SMCJ24A-implied 24V rail, and because it stays within the MPS line you're
already sourcing.

| Ref | Value | Function |
|---|---|---|
| U2 | MP2459GJ-Z | Buck controller |
| C7 | 10µF 50V | VIN input cap |
| C8 | 100nF 50V | BST cap, BS↔SW |
| L3 | 47µH | SW_BK → BUCK |
| C9 | 22µF 16V | Output cap |
| R15 / R16 | 51.1kΩ / 10kΩ | FB divider → 4.95V |
| R18 | 100kΩ | EN pull-up to VIN |
| D2 | SS36 | Freewheel Schottky (MP2459 is non-synchronous) |

47µH is the right value here, not a leftover: at 24V in, 5V out, 480kHz it
gives ~175mA ripple on a 0.5A part.

---

## What you must do before this is buildable

1. **Footprints for U2 and D2 are blank.** Your library has no SOT-23-6 or SMA
   land pattern. Assign or create them, or they'll silently drop off the PCB.
2. **Confirm the CP1↔CP2 cap voltage rating.** The 0402 100nF part I cloned
   (CL05B104KB54PNC) is almost certainly not rated for 24V+. Pick a real part.
3. **MPN/LCSC fields on all new parts say "TBD".** Fill them for BOM export.
4. **Re-annotate if you want tidy designators.** The allocator filled unused low
   numbers (C1, R4, …) rather than continuing from C74/R49.
5. **Firmware.** All SPI configuration is gone — current limit, slew rate and
   PWM mode are now fixed in silicon. Five ESP32 pins (IO11, IO12, IO13, RXD0,
   TXD0) are freed and currently drive nothing.
6. **Re-check 0.5A is enough.** ESP32-S3 WiFi bursts are lumpy; your U10 LDO
   caps 3V3 at 200mA, so it should be, but verify against your actual 5V loads.
7. **Sanity-check the ERC** in Eeschema before updating the PCB.
