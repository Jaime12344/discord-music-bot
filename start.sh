#!/bin/bash
# Instala ffmpeg localmente (sem precisar de sudo)
mkdir -p $HOME/bin
curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz | tar -xJ --strip-components=1 -C $HOME/bin ffmpeg-*-static/ffmpeg
export PATH="$HOME/bin:$PATH"
python3 bot.py
