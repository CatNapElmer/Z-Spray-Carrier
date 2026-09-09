# Z Spray Carrier Fabricator

Generates a shop pack for a welded steel carrier that hauls a **Z-Spray Junior**
on the back of a truck, hanging off the **two receiver sockets the truck already
has**.

The truck is finished and does not get modified. Nothing braces to the flatbed,
the headache rack or anything else. The carrier mounts through those two sockets
and that is it.

This is a tape-measure-and-welder job. The software exists to make it faster than
Kentucky windage, not to turn it into a precision engineering exercise.

---

## What gets built

| | |
|---|---|
| Deck frame | 63" long, 36" outside the side rails, about 17-1/4" off the ground |
| Usable width | 38" across the deck, ramp and guides (measured off the steel, not assumed) |
| Ramp | one rigid 61" assembly, swings from the ground to straight up |
| Wheel tracks | 11-1/2" each for an 8.5" rear tire, 13" open down the middle |
| Truck mount | two 2x2x1/4 tubes into the existing sockets, sleeved with 2-1/2x2-1/2x3/16 outside the socket |
| Load path | three under-deck mount beams cut to fit between the tubes, welded flat to the rails and cross tubes |
| Hinge | one 3/4" pin, seven 1-1/4" OD barrels alternating carrier / ramp, no ears, nothing machined |
| Securement | front chain and shackle |

### The hinge, in one line

**The gap between the deck and the ramp is one barrel diameter.** Lay a scrap of
the barrel stock in the gap and that is your spacer. Each barrel sits in the
corner of its own cross tube — bottom flush with the top of the frame, back
against the cross tube face — and gets a fillet above and below. Slide all seven
onto the pin, clamp, tack, swing it by hand, then weld it out.

The bore is 7/8" on a 3/4" pin. That 1/8" of slop is on purpose: it swings freely
and never needs reaming after welding.

---

## Field fit — not drawing dimensions

The truck is the fixture. These are settled on the truck or with the machine, and
the shop pack says so instead of printing a number:

- **Mounting tube spacing** — FIELD FIT TO TRUCK. Slide both tubes into the
  sockets; the spacing sets itself. No socket measurement, no centreline
  calculation.
- **Hitch pin holes** — TRANSFER PIN HOLES FROM TRUCK.
- **Mount beam lengths (MB1/2/3)** — CUT TO FIT between the mounting tubes.
- **Sleeve position** — slide up against the socket face.
- **Ramp / rear tire gap** — CHECK DURING MACHINE FIT-UP.
- **Machine body clearance past the guides** — CHECK DURING MACHINE FIT-UP. The
  guides guide the tires; the published 36" body width is measured well above a
  3" guide and is not a gate on the design.

Internally the program keeps one nominal spacing coordinate so it can draw the
model. It is tagged `MODEL_ONLY` and never reaches paper as a dimension — there
is a test that fails if it does.

---

## What the program checks

`physical.py` works on the real outside size of every piece of steel. A note
saying two parts are welded proves nothing; only steel in the same place counts.

It answers one question: **did we design pieces that do not connect, or cannot
move?**

- every declared weld is backed by real contact (gap, graze, face contact,
  tangent fillet or interference)
- nothing occupies the same space unintentionally — sleeves over tubes are
  `NESTED_FIT`, coped joints are `FIT_REQUIRED`, neither is a failure
- the ramp swings from deployed through straight up without hitting anything
- usable width is measured across the deck / ramp / guides; the under-truck
  mounting tubes are reported separately and are not held to that target
- the tracks take the tire

It does not model weld beads or grinder chamfers, and it does not report ordinary
fit-up as a catastrophe.

### Strength

Kept deliberately simple. The whole carrier hangs off two tubes, so the bending
at the socket is just weight × how far back it sits, split between two tubes.
Checked against a rough-road bump, a hard stop and a hard corner.

Acceptance rule: **nothing yields at 2 g.** That is a factor of 2 against yield on
the static load. No second safety factor is stacked on top of an already-factored
load — that would be a 4 g bar and would make this carrier absurdly heavy.

The bare 2x2 tube would yield around 1.4 g, which is why the slip-on sleeve is
there. Sleeved, nothing yields below about 3 g. **The sleeves are structural — do
not leave them off.**

---

## Shop pack

`POST /api/export` (or the Export button) writes:

- `Z-Spray-Carrier-Shop-Drawings.pdf` — 9 sheets
- `README-FOR-FABRICATOR.txt` — build order, field-fit items, hinge notes, the
  fit-up and strength results
- `BOM.csv`, `Cut-List.csv` — every piece in the model, with field-fit pieces
  marked `CUT TO FIT - APPROX.` rather than pretending to be production lengths
- `Purchase-List.csv` — what to buy. If the job needs a full sheet, the row is a
  full sheet at the full sheet's weight
- `Stock-Cutting-Plan.pdf`, `Project-Parameters.pdf`
- all of it zipped

---

## Running it

Windows 10/11, Python 3.12+, Node 18+.

```powershell
.\Start-ZSprayCarrier.ps1
```

Backend on `http://localhost:8000`, frontend on `http://localhost:5173`.

Tests:

```powershell
.\Test-ZSprayCarrier.ps1
```

or

```powershell
cd backend
.\.venv\Scripts\pytest -q
```

---

## Layout

- `backend/models.py` — parameters and result types
- `backend/geometry.py` — the actual carrier: members, plates, holes, welds,
  hinge layout, build sequence, strength check
- `backend/physical.py` — does it fit together and does the ramp swing
- `backend/optimizer.py` — cut nesting and the buy list
- `backend/drawings.py` — the drawing sheets
- `backend/main.py` — API and package export
- `frontend/` — React parameter UI and preview
