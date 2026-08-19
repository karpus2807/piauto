# Python libraries

`requirements-max.txt` is the Max stack list (Flask, Pillow, Adafruit LED, …).

These are **not** SunFounder git repos. First `install.sh` may still fetch them from **PyPI**.

To keep even PyPI offline:

```bash
bash vendor/python/download-wheels.sh
git add vendor/python/wheels
```

Then `sudo bash install.sh --offline`.
