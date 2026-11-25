# converted mp4 to mp3
import os
import subprocess

files = os.listdir("FrontEnd")

for file in files:
    print(file)
    subprocess.run(['ffmpeg', '-i', f'FrontEnd/{file}', f'audioS/{file}.mp3'])