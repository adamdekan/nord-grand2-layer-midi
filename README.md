# nord-grand2-layer-midi

A patch kit for the **Nord Grand 2 OS v1.22 (b245)**. The patched OS gives each of the four layers its own MIDI receive channel:

| MIDI channel | Layer |
|---|---|
| 1 | Piano A |
| 2 | Piano B |
| 3 | Synth / Sample A |
| 4 | Synth / Sample B |

On each of those channels the layer receives:
- notes and note-offs, velocity included;
- All Notes Off (CC 123);
- sustain, sostenuto and soft pedal (CC 64/66/67);
- pitch bend and aftertouch.

The local keyboard and MIDI Out are unchanged.

> **This repository contains no Clavia/Nord firmware or software.** You supply the official Nord Grand 2 OS v1.22 Update Tool yourself, and the build script produces the modded update tool on your own machine. This is an unofficial modification and is not affiliated with or endorsed by Clavia DMI AB / Nord Keyboards.

> **Status: not yet tested on real hardware.** The patch was verified by static analysis and by emulating the patched firmware code (see [Verification](#verification)). Flashing modified firmware is at your own risk and may affect warranty or support.

## Requirements
- Windows. The build uses the Win32 resource APIs to read and write the update tool.
- Python 3.10+ and `pip install -r requirements.txt` (`capstone`, `keystone-engine`; `unicorn` only for the tests).
- The official **Nord Grand 2 OS v1.22** update tool from nord.com. The build checks the SHA-256 of its embedded OS container and refuses any other version.

## Build
```
python scripts\build_layers.py <path\to\official nord update tool.exe> build
```
The script runs these steps:
1. Extracts the OS container (`BIN/101` resource).
2. Decompresses the main OS image (LZO1X).
3. Applies the patch.
4. Recompresses the image.
5. Rebuilds the container with all checksums.
6. Validates the result the way the update tool does.
7. Writes `build\nord-fun-layers.exe`.

Intermediate files go to `build\work\`. `.gitignore` keeps them out of git; never commit them.

Expected output hashes (SHA-256):

| File | SHA-256 |
|---|---|
| `bin101_layers.bin` | `d18ee2ed9ce07fa32cf900ac9e0844cfb507133aa5249794b08f5c9c8a92b05f` |
| `nord-fun-layers.exe` | `955a7ede6fabc60001e87b6078cf88b82de9ac17ec2d8f23556d658c61046e52` |

## Install
1. Back up your programs and samples with Nord Sound Manager.
2. Keep the official update tool. It restores the stock OS.
3. Connect the Grand 2 over USB and close all other Nord applications.
4. Run `nord-fun-layers.exe` and press **Update**.
5. The instrument still reports v1.22 b245. To confirm the mod is active, play on MIDI channels 1–4.

The modded update tool is no longer signed by Clavia, so Windows may warn about an unsigned program.

## Behaviour
- **Layer enable:** a layer only sounds if it is enabled in the program (Piano A/B, Synth A/B).
- **Split, zones and octave:** each layer channel uses that layer's keyboard zone and octave shift, like playing the layer from the keys. With Split off, every channel covers the full key range.
- **Global MIDI Channel** (System menu):
  - **5–16:** that channel still plays the whole instrument (all enabled layers). Channels 1–4 address single layers. **This is the recommended setting.**
  - **1–4:** that channel is taken by its layer. Program changes sent on it are not expected to switch programs; this is inferred, not verified.
  - **Off:** no whole-instrument channel, but channels 1–4 still drive the layers.
- **Changing the Global MIDI Channel** releases notes held on the layer channels, the same panic behaviour the stock OS applies to its own channel.

## Recovery
The patch changes only the main OS image. The update mode the tool reboots the instrument into is not modified. Running the official update tool restores the stock OS. If the instrument does not start normally, use Nord's documented procedure for forcing update mode, or contact Nord support, then run the official update tool.

## How it works
The firmware already has an input slot per layer, plus a whole-instrument slot:
- slot 11: "Piano Slot A";
- slot 12: "Piano Slot B";
- slot 13: "Synth Slot A";
- slot 14: "Synth Slot B";
- slot 1: the whole instrument.

The layer engines subscribe to their slot. The layer controllers switch the slot on and off with the layer and apply the layer's zone to it. The stock OS never points a MIDI channel at slots 11–14: the Global MIDI Channel handler gives every slot the same channel, and slot 1 wins.

The patch hooks the end of that handler and pins `chanToSlot[ch 1..4] = slots 11..14` in both MIDI receivers. One receiver handles notes and All Notes Off; the other handles pedals, pitch bend, aftertouch and program change. The code space comes from replacing an unrolled 17-store table rebuild inside the same handler with an equivalent loop.

Full notes are in [docs/TECHNICAL.md](docs/TECHNICAL.md).

## Verification
- **Emulation:** `tests/emu47.py` runs the real handler under unicorn for global channel values Off, 1, 5 and 16, on both the stock and the patched image. The maps come out as intended, callee-saved registers and the stack are preserved, and note releases behave correctly.
- **Compression:** the recompressed image uses only the LZO1X instruction forms present in Clavia's own stream (`tests/lzostat.py`). It round-trips identically through two independent decoders.
- **Container:** `scripts/validate.py` checks the container the way the update tool does (16-bit header and segment checksums, block table), plus 32-bit checksums and a full decompression. The modded update tool starts and shows v1.22 b245 like the original.
- **Reproducibility:** rebuilds from scratch produce identical files.

```
python tests\emu47.py build\work\A_CODE.bin 1 5 0 16
python tests\emu47.py build\work\A_CODE_patched.bin 1 5 0 16
```

## Layout
| Folder | Contents |
|---|---|
| `scripts/` | build pipeline: `build_layers.py`, `patch_layers.py`, `lzo1x.py` / `lzo1x_compress.py`, `repack.py`, `validate.py`, `embed.py`, `fixpe.py` |
| `tests/` | handler emulation and LZO stream statistics |
| `tools/` | reverse-engineering helpers (capstone disassembly, string, xref and vtable search, ELF/PE wrappers for raw ARM blobs) |
| `ghidra_scripts/` | headless Ghidra scripts: create functions from vtable pointers, dump all decompiled C |
