import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sb19_selenium_rpa import SB19SeleniumRPA

if __name__ == "__main__":
    rpa = SB19SeleniumRPA(tracks_csv=r"D:\dev\sb19\temp_new_tracks.csv")
    rpa.run()
