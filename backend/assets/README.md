# Audio Assets

This directory contains pre-recorded/pre-rendered audio assets streamed by the Voicera server:

- `greeting.pcm`: 16kHz 16-bit mono raw PCM greeting audio played when an inbound call connects.
- `greeting_8k.pcm`: 8kHz 16-bit mono raw PCM greeting audio used when Exotel negotiates an 8kHz sample rate.

> **Regenerating greetings**: You can regenerate both files using `python scripts/gen_greeting.py`.
