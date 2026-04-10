# Star Utility Quickstart (Raspberry Pi + TSP100IIU)

## 1) Environment Check

```bash
cd /home/tt18/omikuji_project
/home/tt18/omikuji_env/bin/python star_util.py --printer star doctor
```

## 2) Basic Operations

```bash
# Printer status
/home/tt18/omikuji_env/bin/python star_util.py --printer star status

# Print built-in test page (portrait paper, horizontal text)
/home/tt18/omikuji_env/bin/python star_util.py --printer star test --mode image --layout horizontal --orientation portrait

# Print text payload
/home/tt18/omikuji_env/bin/python star_util.py --printer star print-text --mode image --layout horizontal --orientation portrait --text 'おみくじ\n大吉\n'
```

## 3) Queue Option Control

```bash
# List queue options
/home/tt18/omikuji_env/bin/python star_util.py --printer star list-options

# Set options (example)
/home/tt18/omikuji_env/bin/python star_util.py --printer star set-options --option PrintDensity=4Plus1 --option DocCutType=1PartialCutDoc
```

## 4) TSP100IIU Presets (Official Tips .dat)

```bash
# List presets
/home/tt18/omikuji_env/bin/python star_util.py tsp100iiu-list

# Apply preset
/home/tt18/omikuji_env/bin/python star_util.py --printer star tsp100iiu-apply --preset compression-75
```

After applying preset, power-cycle the printer.

## 5) Profiles

```bash
# Save current queue options and print defaults
/home/tt18/omikuji_env/bin/python star_util.py --printer star profile-save --name shop_default

# List profiles
/home/tt18/omikuji_env/bin/python star_util.py profile-list

# Apply saved queue options
/home/tt18/omikuji_env/bin/python star_util.py --printer star profile-apply --name shop_default
```

## 6) Windows Config XML Reference

```bash
/home/tt18/omikuji_env/bin/python star_util.py win-xml-summary '/home/tt18/Downloads/tsp100_v770/Windows/ConfigurationSettingFiles/TSP100ECO/escpos.xml'
```

This command summarizes emulation plugins and substitution-rule counts for cross-platform tuning.
