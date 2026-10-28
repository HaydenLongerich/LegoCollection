"""Launch BrickLedger, a local LEGO collection and sales tracker."""

import tkinter as tk

from brickfolio.app import BrickLedgerApp


if __name__ == "__main__":
    try:
        BrickLedgerApp().mainloop()
    except tk.TclError as error:
        # A few stripped-down Python installations omit Tcl/Tk.  Give the
        # collector a useful recovery note instead of an intimidating trace.
        if "init.tcl" in str(error):
            print("\nBrickLedger needs Python's desktop UI component (Tcl/Tk).")
            print("Rerun the official Python installer, choose Modify, and enable 'tcl/tk and IDLE'.")
            print("Then start BrickLedger again with: python main.py\n")
        else:
            raise
