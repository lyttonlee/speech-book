"""Engine adapters: LLM parse / TTS / clone / moderation.

Business layer depends only on the Protocols declared here, never on a
concrete engine, so new engines (cloud TTS, real LLM) are drop-in.
"""
