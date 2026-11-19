# BrickLedger

I got tired of tracking my LEGO in a spreadsheet so I made this. It keeps track of the sets I own, what I paid, what they're worth, and what I've sold. It's mostly built around my Speed Champions obsession but it works for any theme.

Everything stays on your own computer. No account, no cloud, nothing gets uploaded anywhere.

## Just want to use it?

<p align="center">
  <a href="https://github.com/HaydenLongerich/LegoCollection/releases/download/v1.0.0/BrickLedger.exe">
    <img src="assets/download-button.png" alt="Download BrickLedger.exe" width="460">
  </a>
</p>

Hit the button, double click the exe, done. You don't need Python or anything else.

Heads up, this is still a **beta**. It works fine for me but there might be some bugs, so back up your data now and then. If something breaks let me know in [issues](https://github.com/HaydenLongerich/LegoCollection/issues). Older and newer versions are on the [releases page](https://github.com/HaydenLongerich/LegoCollection/releases).

Couple things:

- Windows will probably throw a blue "Windows protected your PC" popup the first time because I'm not paying for a code signing certificate lol. Hit **More info** then **Run anyway**.
- It takes a few seconds to open the first time.
- If you want it on your taskbar, right click the exe > Show more options > Pin to taskbar.
- Your stuff gets saved in `%LOCALAPPDATA%\BrickLedger` (paste that into File Explorer if you want to find it). Back that folder up if you care about your data. You can delete or move the exe whenever, your collection stays put.

## What it does

- Add sets by searching the built in catalogue (pretty much every LEGO set, works offline)
- Track paid price, estimated value, condition, built/not built, keeping vs for sale
- Log sales and it works out what you actually made
- A gallery view of your collection with pictures, plus a Speed Champions completion tracker (6 stud, 8 stud and polybags) so you can see what you're missing
- Separate lists for loose boxes and instruction manuals
- Import from a BrickEconomy CSV export so you don't have to type everything in again
- Export anything to CSV

## Running it from the code

If you'd rather run it from source or mess with it:

```powershell
git clone https://github.com/HaydenLongerich/LegoCollection.git
cd LegoCollection
pip install -r requirements.txt
python main.py
```

You need Python 3.10+. If it complains about `init.tcl`, rerun the Python installer, pick Modify and tick "tcl/tk and IDLE".

When you run it this way your data goes in the `data` folder inside the repo instead. That folder is gitignored so you won't accidentally push your collection.

### Building the exe yourself

```powershell
.\tools\build_exe.ps1 -Release
```

That spits out a standalone `dist\BrickLedger.exe` (the one that goes on the releases page). For a new version, bump the tag in the download link above and the text in `tools\make_download_button.py`, then run that script to redraw the button.

Running it without `-Release` makes a `BrickLedger.exe` in the main folder that just runs whatever code is sitting next to it. That's what I use day to day since it picks up changes without rebuilding. It only needs a rebuild if the tests say a new import is missing, or if the logo or `tools\launcher.py` changes.

### Tests

```powershell
python -m unittest discover -s tests -v
```

## Credits

Set data and images come from [Rebrickable](https://rebrickable.com). LEGO is a trademark of the LEGO Group, who have nothing to do with this.
