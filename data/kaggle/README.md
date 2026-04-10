# Kaggle Dataset Download

Use this folder for downloading the competition files.

## Why it may fail with 401

If you see `401 Unauthorized`, usually one of these is still missing:

1. You did not accept the competition rules on Kaggle.
2. Your API token is old/invalid and needs regeneration.

## One-time setup

1. Join the competition page in browser:
   - `https://www.kaggle.com/competitions/autonomy-in-the-fields-life-saving-computer-vision`
2. Create a fresh API token on Kaggle Account page.
3. Save token to:
   - `/Users/philipp/.kaggle/kaggle.json`
4. Set permissions:

```bash
chmod 600 /Users/philipp/.kaggle/kaggle.json
```

## Download command

From this folder:

```bash
/Users/philipp/Documents/HackHPI/.venv-1/bin/python -m kaggle.cli competitions download -c autonomy-in-the-fields-life-saving-computer-vision
```

## Unzip command

```bash
unzip autonomy-in-the-fields-life-saving-computer-vision.zip -d extracted
```
