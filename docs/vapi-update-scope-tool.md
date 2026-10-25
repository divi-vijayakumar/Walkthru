# Vapi tool: update_scope

Replaces `get_quote_estimate` in the Vapi assistant. Server URL: `{BACKEND}/api/vapi/tools` (same secret header as before).

```json
{
  "type": "function",
  "function": {
    "name": "update_scope",
    "description": "Call every time the homeowner describes work or answers a question. Returns next_action (ask, show, confirm, measure or price) and next_text to say. Speak only numbers from this tool.",
    "parameters": {
      "type": "object",
      "properties": {
        "said": {"type": "string", "description": "The homeowner's words describing work, verbatim"},
        "answers": {"type": "object", "description": "Answer to the last question, keyed by the 'fact' field the tool returned, e.g. {\"replacing_vanity\": \"new floating one\"}"},
        "camera_on": {"type": "boolean", "description": "Ignored while a call is live (the portal reports the camera)"},
        "wants_price": {"type": "boolean", "description": "True when the homeowner asks for a quote, price or how much, or says they're done (that's it, nothing else, wrap up); returns one exact total at once"},
        "skipped": {"type": "array", "items": {"type": "string"}, "description": "Fact names the homeowner declined or couldn't answer; they are assumed and never asked again"}
      }
    }
  }
}
```

Prompt notes for Alex: one question per turn; read `next_text` in your own words; when `next_action` is `price`, summarize the scope in two sentences and give the one exact `total` (never a range); if `if_not` is present, read it as the exact difference; mention any `insights` at the next pause. Lines starting "To be priced by Apex" have no amount yet; say Apex will price them. Camera updates may also arrive as system messages during the call; mention each once, naturally. `request_adjustment` and `queue_quote_followup` stay unchanged.
