# ImageSizer

ImageSizer is a desktop app for **batch image preparation**. It runs on Linux, Windows and macOS. Give it a folder of photos and it will:

1. **Upscale** each image with AI models from [Upscayl](https://github.com/upscayl/upscayl). This step is optional.
2. **Fit** the image to every aspect ratio you choose, either by cropping or by padding.
3. **Resize** each version to the size you want.
4. **Save** the results into **a separate folder for each image**, named the way you specify.

```
ImageSizer/                      ← output folder you choose
├── beach/                       ← one folder per input image
│   ├── beach_1x1_2048x2048.png
│   ├── beach_4x5_1638x2048.png
│   └── beach_16x9_2048x1152.png
└── portrait/
    ├── portrait_1x1_1800x1800.png
    └── ...
```

Everything runs locally. Nothing is uploaded. The internet is used only once, to download the upscaling engine.

### ⬇ [Download the latest version](https://github.com/hembone/imagesizer/releases/latest)

Windows installer · macOS disk image (Apple Silicon or Intel) · Linux AppImage. You don't need Python or any other setup. See [Download](#download) for step-by-step instructions.

---

## Contents

- [Download](#download)
- [Requirements](#requirements)
- [First run: installing the upscaling engine](#first-run-installing-the-upscaling-engine)
- [Updating](#updating)
- [Using the app](#using-the-app)
- [Naming templates](#naming-templates)
- [Presets](#presets)
- [Command line](#command-line)
- [Where files are stored](#where-files-are-stored)
- [Troubleshooting](#troubleshooting)
- [Running from source](#running-from-source)
- [Development](#development)
- [Credits and licenses](#credits-and-licenses)

---

## Download

Go to the **[latest release](https://github.com/hembone/imagesizer/releases/latest)** and download the file for your computer from the *Assets* list:

| Your computer | Download |
|---|---|
| Windows 10 / 11 | `ImageSizer-<version>-Windows-Setup.exe` |
| Mac with Apple Silicon (M1, M2, M3, M4…) | `ImageSizer-<version>-macOS-arm64.dmg` |
| Mac with an Intel processor | `ImageSizer-<version>-macOS-x86_64.dmg` |
| Linux (64-bit, most distributions) | `ImageSizer-<version>-x86_64.AppImage` |

> **Which Mac do I have?** Open the Apple menu  → **About This Mac**. *Chip: Apple M…* means Apple Silicon. *Processor: Intel…* means Intel.

The apps aren't code-signed yet (signing costs money every year), so Windows and macOS warn you the first time. The steps below show how to get past the warning once.

### Windows

1. Run **`ImageSizer-…-Windows-Setup.exe`**.
2. If a blue **"Windows protected your PC"** box appears, click **More info → Run anyway**.
3. Click through the installer. You don't need administrator rights. ImageSizer installs for your user account only, and you can tick *Create a desktop shortcut*.
4. Start **ImageSizer** from the Start menu.

To uninstall, go to **Settings → Apps → Installed apps → ImageSizer → Uninstall**.

### macOS

1. Open **`ImageSizer-…-macOS-….dmg`**.
2. Drag **ImageSizer** onto the **Applications** folder in the window that opens.
3. The first time, open your **Applications** folder, **right-click** ImageSizer and choose **Open**, then **Open** again.
   On recent macOS versions you may instead get a box with only *Done* / *Move to Trash*. If so, click **Done**, go to **System Settings → Privacy & Security**, scroll down, click **Open Anyway** next to the ImageSizer message, and confirm.
4. After that, open it normally from Launchpad, Spotlight or the Dock.

To uninstall, drag **ImageSizer** from Applications to the Trash.

### Linux

1. Download **`ImageSizer-…-x86_64.AppImage`**.
2. Make it executable. In your file manager, **right-click → Properties → Permissions → Allow executing file as program**. Or in a terminal:
   ```bash
   chmod +x ImageSizer-*-x86_64.AppImage
   ```
3. Double-click it, or run `./ImageSizer-*-x86_64.AppImage`.

AppImages run without being installed and include everything they need, so there is nothing to `apt install`. To add ImageSizer to your applications menu, you can use [Gear Lever](https://flathub.org/apps/it.mijorus.gearlever) or [AppImageLauncher](https://github.com/TheAssassin/AppImageLauncher) (optional). To uninstall, delete the file.

## Requirements

| | |
|---|---|
| **OS** | Windows 10/11 (64-bit), macOS 12 or newer, or 64-bit Linux from roughly 2022 onwards (glibc 2.35+, e.g. Ubuntu 22.04, Fedora 36, Debian 12). |
| **GPU** | Upscaling needs one that supports **Vulkan**: most NVIDIA, AMD and Intel GPUs from the last ~8 years, and Apple Silicon or recent Intel Macs (through Metal). Without one you can still crop and resize, just not upscale. |
| **Disk** | About 200 MB for the app, about 215 MB for the upscaling engine and models, plus room for your output. Upscaled images are large: 4× makes an image 16 times as many pixels. |
| **Internet** | Only to download the app and, once, the upscaling engine. |

## First run: installing the upscaling engine

The upscaler is a separate program, `upscayl-bin`, plus a set of model files. To keep the download small, they aren't included in the app.

The first time you open ImageSizer, it asks:

> *Download the AI upscaling engine now? (about 215 MB, one time)*

Click **Download**. Progress appears at the bottom of the window, and when it finishes the Upscale panel says *Engine ready · 7 models*.

If you click **Later**, you won't be asked again. You can still:

- click **Download engine** in the **Upscale (Upscayl)** panel at any time (click it again to cancel), or
- use the app without upscaling: untick *Upscale before resizing* and it will crop and resize only.

**Already have Upscayl installed?** Click **Engine paths…** and point it at Upscayl's `upscayl-bin` and its `models` folder. Then you don't need to download anything. You can also put extra ncnn models (`.param` + `.bin` pairs) in the models folder and they'll appear in the model list.

## Updating

Download the new version from the [latest release](https://github.com/hembone/imagesizer/releases/latest) and install it the same way:

- **Windows:** run the new Setup.exe. It replaces the old version.
- **macOS:** drag the new ImageSizer into Applications and choose **Replace**.
- **Linux:** delete the old AppImage and use the new one.

Your settings, presets and the downloaded upscaling engine are kept. They are stored separately from the app (see [Where files are stored](#where-files-are-stored)). The window title shows which version you're running.

## Using the app

The window has two halves. **Images and preview** are on the left, **settings** on the right. **Process images** is in the bottom-right corner.

### 1. Add images

- **Drag and drop** files or folders onto the list, or use **Add images…** / **Add folder…**.
- Folders are scanned **including subfolders**.
- Supported inputs: PNG, JPEG, WebP, BMP, TIFF and GIF (first frame).
- If you add the same file twice, it's only listed once. Use **Remove** for the selected entries, or **Clear** for all of them.

Click an image in the list to preview it.

### 2. Upscale (optional)

| Setting | What it does |
|---|---|
| **Upscale before resizing** | Turn off to only crop and resize. |
| **Model** | Which AI model to use (see the table below). Models that aren't installed are marked *(not installed)*. |
| **Scale** | 2×, 3× or 4× the original size. |
| **GPU** | Leave empty for automatic. If you have more than one GPU, enter its number (`0`, `1`, …). |
| **Tile size** | *auto* is usually best. If you get out-of-memory errors on large images, try 256 or 128. |

| Model | Good for |
|---|---|
| Upscayl Standard | General photos; good default |
| Upscayl Lite (fast) | Much faster, slightly less detail. Good on laptops and integrated GPUs |
| High Fidelity | Detailed, natural-looking photos |
| Digital Art | Illustrations, anime, drawn artwork |
| Remacri | Natural textures *(non-commercial use only)* |
| Ultramix Balanced | Balance of sharpness and smoothness *(non-commercial use only)* |
| Ultrasharp | Maximum sharpness *(non-commercial use only)* |

> **Speed:** upscaling is the slow part, especially on integrated graphics. For example, a 400×300 image with Upscayl Standard on an Intel Iris Xe takes about 25 seconds. Try **Lite** first if you have a big batch.

Upscayl doesn't understand camera rotation tags (EXIF orientation). ImageSizer turns each photo the right way up **before** upscaling, so portrait phone photos don't come out sideways.

### 3. Aspect ratios

Each row is one output file per image. Tick the ratios you want.

- **Ratio:** pick a preset (1:1, 4:5, 5:4, 3:2, 2:3, 4:3, 3:4, 16:9, 9:16, 21:9) or type your own, e.g. `5:7` or `2.39:1`. An invalid entry turns red.
- **Size**, set per ratio:
  - **Max resolution:** keep every pixel and only crop or pad. The size depends on the image (and on the upscale).
  - **Long edge:** the longer side becomes this many pixels, e.g. 2048. The other side follows from the ratio.
  - **Exact size:** exactly W×H pixels, e.g. 1080×1350. When you change the width, the height is filled in from the ratio. You can still edit the height, and the output is then fitted to the exact W×H you entered.
- **+ Add ratio** adds a row, and **✕** removes one.

### 4. Fit to ratio

What happens when an image's shape doesn't match the ratio:

- **Crop (fill):** fills the whole frame and trims the edges. The **Anchor** grid picks which part of the image to keep: ● keeps the center, ↑ keeps the top (good for portraits where heads would otherwise be cut off), ← keeps the left side, and so on.
- **Pad (letterbox):** keeps the whole image and adds bars. Choose the **pad color**, or **Transparent** (PNG and WebP only). The anchor decides where the image sits within the bars.

The **Preview** under the image list shows the result for the ratio chosen in its drop-down. In crop mode, the shaded area is what gets trimmed. In pad mode, you see the bars.

### 5. Output

| Setting | What it does |
|---|---|
| **Folder** | Where results go. Default: `Pictures/ImageSizer`. **Open** shows it in your file manager. |
| **Format** | PNG (lossless, supports transparency), JPEG (smallest files), or WebP (small, supports transparency). |
| **Quality** | 1–100 for JPEG/WebP. 90+ gives full-color JPEGs without chroma subsampling. |
| **Folder name / File name** | Naming templates. See [Naming templates](#naming-templates). |
| **If folder exists** | *Write into it*, *Make a new numbered folder* (`beach_1`, `beach_2`…), or *Skip the image*. |
| **If file exists** | *Add a number* (`…_1.png`), *Overwrite*, or *Skip*. |
| **Also save the full upscaled image** | Also saves the upscaled image before cropping, named with `upscaled` in place of the ratio. |
| **Keep color profile and EXIF** | Copies the ICC color profile and camera metadata into the outputs. The rotation tag is reset, because the pixels are already upright. |

The **Preview** line underneath shows the exact folder and file names the selected image will get, including real pixel sizes.

### 6. Process

Click **Process images**. Images are processed one at a time:

- The status bar shows the current image and step (*Upscaling*, *Resizing 4:5*…). The progress bar covers the whole batch.
- Each list entry is updated with ✔ and the number of files written, or ✖ and the error. **Hover** over an entry for details: its output folder, skipped files, or the full error message.
- If one image fails (for example, a corrupt file), the rest of the batch still runs.
- **Cancel** stops after the current step and kills the upscaler if it's running. Files are written to a temporary name first and renamed when complete, so you never get half-written images. A folder created for an image that was cancelled before any files were written is removed again.

If something is wrong before starting, such as no ratio ticked, a bad template, or the engine not installed, you get a list of what to fix.

## Naming templates

Templates are text with **tokens** in curly braces.

| Token | Value | Example |
|---|---|---|
| `{name}` | Original file name, without extension | `beach` |
| `{date}` | Date of the run | `2026-10-12` |
| `{index}` | Position in the batch, starting at 1 | `3` |
| `{scale}` | Upscale factor (`1` if upscaling is off) | `4` |
| `{model}` | Model id (`none` if upscaling is off) | `upscayl-lite-4x` |
| `{ratio}` | Aspect ratio *(file names only)* | `16x9` |
| `{w}`, `{h}` | Output width and height in pixels *(file names only)* | `1920`, `1080` |

The extension (`.png`/`.jpg`/`.webp`) is added automatically.

**Examples**

| Folder template | File template | Result |
|---|---|---|
| `{name}` *(default)* | `{name}_{ratio}_{w}x{h}` *(default)* | `beach/beach_16x9_1920x1080.png` |
| `{date}_{name}` | `{ratio}` | `2026-10-12_beach/16x9.png` |
| `{index}-{name}` | `{name}-{w}w` | `3-beach/beach-1920w.png` |
| `{name}_x{scale}` | `{name}_{model}_{ratio}` | `beach_x4/beach_upscayl-lite-4x_16x9.png` |

Names are made safe for every OS. Characters such as `< > : " / \ | ? *` are removed, and reserved Windows names like `CON` are prefixed with `_`. A typo such as `{nmae}` shows an error in the preview instead of producing odd file names.

## Presets

All settings (upscale, ratios, fit and output) can be saved under a name and reused:

- **Save preset…** stores the current settings. Using an existing name asks before replacing it.
- Pick a preset from the **Preset** drop-down to load it.
- **Delete** removes the selected preset.

Example presets: *Instagram* (1:1 at 1080×1080 and 4:5 at 1080×1350, JPEG), *Print* (Max resolution, 3:2 and 4:5, PNG, 4× upscale), *Web banners* (16:9 and 21:9, long edge 1920, WebP).

Separately from presets, your **current settings are saved automatically** and restored the next time you open the app.

## Command line

`imagesizer-cli` runs the same pipeline without the GUI, which is useful for scripts and automation. It uses your saved settings (from the GUI) as the starting point.

> The command line comes with the [source install](#running-from-source). The downloadable installers contain only the GUI.

```bash
# Upscale a folder 4x, then make 1:1, 4:5 (long edge 2048) and 16:9 (exactly 1920x1080)
imagesizer-cli ~/Pictures/shoot -o ~/out -r 1:1 -r 4:5@2048 -r 16:9=1920x1080

# Resize only, letterbox on black, save JPEG
imagesizer-cli photos/ -o out --no-upscale -r 9:16=1080x1920 --fit pad --pad-color '#000000' --format jpg

# Use a preset saved in the GUI
imagesizer-cli photos/ --preset "Instagram"

# Install the engine without the GUI
imagesizer-cli --download-engine
```

| Option | Meaning |
|---|---|
| `INPUT…` | Image files and/or folders (folders are scanned recursively) |
| `-o, --output DIR` | Output folder |
| `-r, --ratio SPEC` | Repeatable. `4:5` = max size, `4:5@2048` = long edge, `4:5=1080x1350` = exact size |
| `--preset NAME` | Start from a preset saved in the GUI |
| `--no-upscale` | Skip upscaling |
| `--model ID` | e.g. `upscayl-standard-4x`, `upscayl-lite-4x`, `digital-art-4x` |
| `--scale {2,3,4}` | Upscale factor |
| `--gpu ID` | GPU number (default: auto) |
| `--fit {crop,pad}` | Fit mode |
| `--anchor POS` | `center`, `top`, `bottom`, `left`, `right`, `top-left`, … |
| `--pad-color COLOR` | Hex color such as `#ffffff`, or `transparent` |
| `--format {png,jpg,webp}` / `--quality N` | Output format and quality |
| `--folder-template T` / `--file-template T` | Naming templates |
| `--keep-upscaled` | Also save the full upscaled image |
| `--download-engine` | Download `upscayl-bin` and all models, then exit |

Exit codes: `0` success, `1` one or more images failed, `2` invalid settings or no images found.

## Where files are stored

| | Linux | macOS | Windows |
|---|---|---|---|
| Settings and presets | `~/.config/imagesizer/settings.json` | `~/Library/Application Support/imagesizer/settings.json` | `%LOCALAPPDATA%\imagesizer\settings.json` |
| Engine and models | `~/.local/share/imagesizer/engine/` | `~/Library/Application Support/imagesizer/engine/` | `%LOCALAPPDATA%\imagesizer\engine\` |
| Default output | `~/Pictures/ImageSizer` | `~/Pictures/ImageSizer` | `Pictures\ImageSizer` |

To reset all settings, delete `settings.json`. To uninstall the engine, delete the `engine` folder.

## Troubleshooting

**Windows: "Windows protected your PC"**
This is SmartScreen warning about an app that isn't code-signed. Click **More info → Run anyway**. You only need to do this for the installer.

**macOS: "ImageSizer can't be opened" / "Apple could not verify…"**
The app isn't signed with an Apple developer certificate. Right-click ImageSizer in Applications and choose **Open**. If that doesn't offer an *Open* button, go to **System Settings → Privacy & Security** and click **Open Anyway** next to the ImageSizer message. You only need to do this once per version.

**Linux: the AppImage doesn't start**
- Make sure it's executable (`chmod +x ImageSizer-*.AppImage`, or *Properties → Allow executing*).
- Run it from a terminal to see the error message.
- On distributions older than about 2022 (glibc below 2.35) it can fail with `GLIBC_2.35 not found`. Use the [source install](#running-from-source) instead.

**Linux, source install: "Could not load the Qt platform plugin xcb"**
Install the missing library: `sudo apt install libxcb-cursor0` (Fedora: `sudo dnf install xcb-util-cursor`). The AppImage already includes it.

**"upscayl-bin failed" / "No usable Vulkan GPU was found"**
- Update your graphics drivers. On Linux, make sure the Vulkan driver is installed (`mesa-vulkan-drivers` for Intel/AMD; the proprietary driver for NVIDIA). `vulkaninfo --summary` should list your GPU.
- If the GPU runs out of memory on big images, set **Tile size** to 256 or 128.
- With several GPUs, try another **GPU** number.
- You can always untick **Upscale before resizing** and process without upscaling.

**The engine download fails**
It downloads from GitHub, so check that `github.com` and `raw.githubusercontent.com` are reachable. Alternatively, download `upscayl-bin` for your OS from [upscayl-ncnn releases](https://github.com/upscayl/upscayl-ncnn/releases) and the models from [Upscayl's models folder](https://github.com/upscayl/upscayl/tree/main/resources/models), then set them under **Engine paths…**.

**Upscaling is very slow**
That's normal on integrated graphics. Use the **Upscayl Lite** model, a lower **Scale**, or turn upscaling off for images that are already large.

**Transparent areas turned a solid color**
JPEG has no transparency, so transparent pixels are filled with the pad color (white unless you change it, even when Transparent is ticked). Use PNG or WebP to keep transparency.

## Running from source

Use this route for development, to get the [command line](#command-line), or on a platform without a download. It needs **Python 3.11 or newer**.

**Linux / macOS**
```bash
git clone https://github.com/hembone/imagesizer.git && cd imagesizer
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/imagesizer            # GUI
.venv/bin/imagesizer-cli -h     # command line
```

**Windows (PowerShell)**
```powershell
git clone https://github.com/hembone/imagesizer.git; cd imagesizer
py -m venv .venv
.venv\Scripts\pip install -e .
.venv\Scripts\imagesizer
```

On **Linux** a source install also needs Qt's `libxcb-cursor0` library: `sudo apt install libxcb-cursor0` (Fedora: `xcb-util-cursor`).

You can also pass files or folders when you launch it, and they are added to the list straight away:
```bash
.venv/bin/imagesizer ~/Pictures/holiday photo1.jpg
```

## Development

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest                                  # all tests; GUI tests run offscreen
.venv/bin/pyinstaller packaging/imagesizer.spec   # standalone app in dist/ImageSizer
packaging/linux/make_appimage.sh 0.1.0            # Linux: wrap dist/ImageSizer into an AppImage
```

Project layout:

```
src/imagesizer/
  __main__.py          GUI entry point
  cli.py               command line
  config.py            settings and presets (JSON)
  engine/              upscayl-bin download, location and execution
  processing/          ratios, crop/pad/resize math, naming, per-image pipeline
  gui/                 Qt (PySide6) window, panels, preview, background workers
  resources/icon.png   app icon
tests/                 pytest suite
packaging/
  imagesizer.spec      PyInstaller build (all OSes)
  make_icons.py        regenerates icon.png / icon.ico / icon.icns
  windows/             Inno Setup script → Setup.exe
  macos/               make_dmg.sh → .dmg
  linux/               make_appimage.sh + .desktop entry → .AppImage
.github/workflows/
  ci.yml               tests on Ubuntu, Windows and macOS for every push / PR
  release.yml          builds the installers and publishes a GitHub Release for version tags
```

### Making a release

1. Bump `version` in `pyproject.toml` (e.g. `0.2.0`) and commit.
2. Tag and push:
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```
3. The **Release** workflow tests and builds on Windows, macOS (Apple Silicon and Intel) and Linux. It then publishes a GitHub Release with the four installers attached. This takes about 3–5 minutes.

The tag must match the version in `pyproject.toml`, or the build stops with an error. A suffix after a hyphen is allowed: `v0.2.0-rc1` matches version `0.2.0`, and it's published as a **pre-release**. The installers' file names and the app's window title both show the full tag version (e.g. *ImageSizer 0.2.0-rc1*). That's useful for testing the installers before announcing a version. To build the installers without publishing anything, run the Release workflow manually from the *Actions* tab. The files then appear as workflow artifacts.

## Credits and licenses

- Upscaling is powered by [Upscayl](https://github.com/upscayl/upscayl) and [upscayl-ncnn](https://github.com/upscayl/upscayl-ncnn) (Real-ESRGAN on ncnn/Vulkan). They are downloaded at runtime and are not distributed with this app.
- **Remacri, Ultramix Balanced and Ultrasharp** are licensed for **non-commercial use only**. Use Upscayl Standard, Lite, High Fidelity or Digital Art for commercial work.
- GUI built with [Qt for Python (PySide6)](https://doc.qt.io/qtforpython/). Image processing by [Pillow](https://python-pillow.org/).
