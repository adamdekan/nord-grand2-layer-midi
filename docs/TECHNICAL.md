# Technical notes: Nord Grand 2 OS v1.22 (b245)

All addresses are for the decompressed main OS image (image A, `CODE` loaded at `0xC0000000`).

## Update tool and container
- **Where the OS lives.** The update tool keeps the OS in PE resource `BIN/101`, language 0x409. `BIN/105` is a separate embedded executable and is not involved.
- **The update tool calls the container a "CAB".** It is big-endian. Offset 0 holds up to 4 `(offset, size)` block entries; unused entries are `0,0`. The tool checks that the blocks do not overlap.
- **Block 0 is image A, the main OS** (version 0x7a = v1.22). Block 1 is image B (version 0x0c), a smaller support image that is not modified.
- **Block header, `0x2d4` bytes:**

  | Offset | Field |
  |---|---|
  | `+0` | version (u16) |
  | `+2` | `0x0100` (the update tool requires byte 2 = 1) |
  | `+4` | build (u16) |
  | `+6` | `~bytesum16(header[8:0x2d4])` |
  | `+0x10` | segment count |
  | `+0x14 + i*0x2c` | segment descriptors |

- **Segment descriptor:**

  | Field | Notes |
  |---|---|
  | tag | 4 chars |
  | offset | relative to the block start |
  | size | unpacked size |
  | load address | |
  | `~bytesum32(data)` | |
  | packed size | 0 = stored uncompressed |
  | `~bytesum32(packed)` | |
  | (rest) | zero |

  Segments follow the header back to back. Offsets do not need to be 4-aligned; image B's ARM0 is at an offset that is 2 mod 4.
- **Image A segments:**

  | Segment | Load address | Contents |
  |---|---|---|
  | `SRAM` | `0x80000000` | shared RAM: interrupt handlers and veneers |
  | `CODE` | `0xC0000000` | LZO1X-compressed, 2,525,648 bytes unpacked |
  | `ARM0` | `0xFFFF0020` | vector trampoline |

- **What the update tool checks before sending:**
  - the first 8 header bytes are not all `0xFF`;
  - the 16-bit header checksum;
  - header byte 2 = 1;
  - a segment with an entry address exists;
  - each tag is printable;
  - the low 16 bits of each segment checksum (packed data when compressed).

  The tool shows version and build only after these checks pass.
- **CPU and memory map:** an ARM926EJ-S class core (TI OMAP-L138 style map) with DDR at `0xC0000000`, shared RAM at `0x80000000` and high vectors.

## Compression
The original `CODE` stream is LZO1X-1 style: literal runs, M2, M3, M4 with 0–3 trailing literals, and the M4 end marker. It never uses M1 matches or the initial-literal opcode. `scripts/lzo1x_compress.py` emits only those same forms, so any decompressor that handled the stock image handles the patched one.

## MIDI receive path
1. **Byte parser.** `FUN_c007591c` is called from the SRAM interrupt code for each port. It decodes the status byte (running status and SysEx included) and calls a handler's virtual methods: NoteOn, NoteOff, PolyAT, CC, PC, ChanAT and PitchBend, each with the channel `status & 0xF`.
2. **Message queue.** The default handler, vtable `0xc01c3a6c`, posts typed 0x40-byte messages to a queue. The message types are BSS tags:

   | Tag | Message |
   |---|---|
   | `0xc0269d10` | NoteOn |
   | `…d14` | NoteOff |
   | `…d18` | All Notes Off (CC 123) |
   | `…d1c` | pedals (CC 64/66/67/114) |
   | `…d04` | PitchBend |
   | `…d08` | aftertouch |
   | `…d0c` | ProgramChange |

   Other CCs go to a separate queue.
3. **Two receivers subscribe to the queue.** Both are created in `FUN_c00cf604` and are referenced from the system-parameter object at `+0xfc` / `+0x100`:

   | Receiver | Handles | chanToSlot[16] | slotToChan[18] | Slot objects |
   |---|---|---|---|---|
   | R1 | NoteOn, NoteOff, All Notes Off | `+0x3c` | `+0x80` (16 = none) | `+0xcc` (transpose, velocity curve, held notes) |
   | R2 | pedals, PB, AT, PC | `+0x54` | `+0x98` | `+0xe4` |

4. **NoteOn handling.** R1's NoteOn handler (`FUN_c00aee40`):
   1. looks up `slot = chanToSlot[ch]` and drops the note if the slot is 0;
   2. applies the slot's transpose;
   3. limits velocity to 1–127 and maps it through the receive velocity curve;
   4. publishes a note event (kind `0x27`) on the internal bus at address `(3, 9, 0, slot)`.

   The bus dispatcher is `FUN_c00aeca4`. Subscribers carry a 64-bit mask, and bit `27 + slot` selects the slot.
5. **Local keyboard.** The keybed scanner (`FUN_c00ad17c`) publishes key events directly, so it is independent of the MIDI channel maps.

## Slots and layers
- **Slot numbers:**

  | Slot | Meaning |
  |---|---|
  | 1 | whole instrument, used by all layers |
  | 7 | Piano section |
  | 8 | Synth section |
  | 11, 12 | dedicated "Piano Slot A/B" |
  | 13, 14 | dedicated "Synth Slot A/B" |

- **Engine subscriptions.** The layer engines are Piano (`FUN_c001321c`, type 7) and Synth (`FUN_c00119f4`, type 8), with two of each. Each subscribes to slot 1 and to its dedicated slot via `FUN_c00b2a48`. It keeps note, zone and enable state per (voice set, slot).
- **Layer controllers.** The controller classes are Piano `FUN_c00e42f8` and Synth `FUN_c00e3adc`. On a layer enable/disable they set slot enable and controller routing for slot 1, the section slot and the dedicated slot together (`FUN_c00ded50` / `FUN_c00ddca0`). `FUN_c00d37b8` applies the same keyboard zone and octave shift to slot 1 and the dedicated slot. A dedicated slot therefore behaves exactly like playing that layer from the keys.

## Stock handling of the Global MIDI Channel
Parameter `0x47` is `Edt_Sys_kMIDIGlobal` (0 = Off, 1–16). It is handled in `FUN_c00d4fe4`: the jump table at `0xc00d5018` sends it to case `0xc00d5098`. That case does two things:
- **Slot assignment.** It assigns the channel to slots 1, 7, 8 and 11–14 in both receivers. After each assignment it rebuilds `chanToSlot` with a fully unrolled loop over slots 17→1, so the lowest slot wins and only slot 1 is effective.
- **MIDI Out.** It also sets the MIDI Out channel.

## The patch (`scripts/patch_layers.py`)
1. **Free space.** The last unrolled 17-store rebuild (`0xc00d656c`–`0xc00d6680`, 0x114 bytes) is replaced by an equivalent loop. The loop reproduces the side effects the following code relies on: `r7` and `r2`.
2. **Save the parameter object.** At `0xc00d6520`, `ldr r4,[r4,#0xfc]` overwrites the parameter-object pointer. It is redirected to a stub that first saves `r4` in an unused slot of the handler's own stack frame (`[sp,#0x28]`).
3. **Route every exit through the hook.** All three exits of the case go through the hook: `0xc00d66a4`, `0xc00d66d0`, and the release call at `0xc00d66dc`.
4. **The hook.** For R1 and R2 it writes `slotToChan[11+k] = k` and `chanToSlot[k] = 11+k` for `k = 0..3`, then jumps to the shared epilogue.

Total new code is 0x88 bytes inside the freed region. No other part of the image changes.
