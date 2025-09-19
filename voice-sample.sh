#!/usr/bin/env bash
SAMPLE=${1:-1}
cp -v audio_samples/sample-recording-${SAMPLE}* .data/local_voice_inbox/test$(date -Iseconds | tr -d '[:punct:]').mp3
