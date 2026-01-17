import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sb19_tracks_streams_rpa import SB19TrackStreamsRPA

if __name__ == "__main__":
    rpa = SB19TrackStreamsRPA()
    rpa.run(track_csv_path=r"D:\dev\sb19\temp_new_tracks.csv")
