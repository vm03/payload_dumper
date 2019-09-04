# payload dumper
Script tested on Yandex Amber OTA's (full and incremental) under Linux(but may works on Windows too)

## System requirement

- Python3, pip
- google protobuf for python `pip install protobuf`

## Guide

- Make you sure you have Python 3.6 installed.
- Download payload_dumper.py and update_metadata_pb2.py
- Extract your OTA zip and place payload.bin in the same folder as these files.
- Open PowerShell, Command Prompt, or Terminal depending on your OS.
- Enter the following command: python -m pip install protobuf

### Full OTA

- When that’s finished, enter this command: python payload_dumper.py payload.bin
- This will start to extract the images within the payload.bin file to the output folder you are in.

### Incremental OTA

- Copy original images (from full OTA or dumped from devices) to old folder (with part name + .img, ex: boot.img, system.img)
- run python payload_dumper.py --diff payload.bin
- file extracted to the output folder you are in.
