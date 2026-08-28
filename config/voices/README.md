# Voice assets

`vapi_voice_provider` / `vapi_voice_id` come from any TTS provider Vapi
supports natively (11labs, playht, azure, deepgram, cartesia, rime, etc.) —
no separate account needed for the built-in stock voices, Vapi brokers TTS
itself. Track which voice each business uses here so
`config/businesses/*.yaml` and this table never drift apart.

| business_id       | provider | voiceId | notes                  |
|--------------------|----------|---------|--------------------------|
| plumbing_co        | 11labs   | burt    | warm, mid-30s male       |
| personal_default    | 11labs   | sarah   | neutral, calm            |

If you need a cloned voice for a branded business, most providers Vapi
supports allow custom voice cloning — track consent/rights source here
before enabling it.
