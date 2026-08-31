# Case walk-throughs

## A00008 — fraud

- Confidence: high
- Behaviour: Behaviour is fraud-like. 3 transaction(s) exceeded 5000: T0107083, T0107082, T0107081. Multiple transactions came from a new device in a short span. Recent transactions span 6 IP countries (threshold 3). Several transactions occurred at overnight hours. The triggered rule set matches a suspicious behaviour profile.
- Context: Context is supportive of fraud. Note N00051 (2026-02-28T09:21:10): Inbound call from customer. They received an SMS about a device registration they did not perform. They have not travelled and still hold the physical card.
- Network: The network footprint is suspicious. The account used more than one device during the alert window. Device DX01439 is a new but isolated device for this account. The account used several merchants, which is common in both legitimate and fraudulent behaviour.
- Disposition: A fraud verdict should be paused for approval before blocking the card and escalating the case.
- Supervisor: Behaviour finding: Behaviour is fraud-like. 3 transaction(s) exceeded 5000: T0107083, T0107082, T0107081. Multiple transactions came from a new device in a short span. Recent transactions span 6 IP countries (threshold 3). Several transactions occurred at overnight hours. The triggered rule set matches a suspicious behaviour profile. Context finding: Context is supportive of fraud. Note N00051 (2026-02-28T09:21:10): Inbound call from customer. They received an SMS about a device registration they did not perform. They have not travelled and still hold the physical card. Network finding: The network footprint is suspicious. The account used more than one device during the alert window. Device DX01439 is a new but isolated device for this account. The account used several merchants, which is common in both legitimate and fraudulent behaviour.

## A00134 — legitimate

- Confidence: medium
- Behaviour: Behaviour is fraud-like. 4 transaction(s) exceeded 5000: T0107808, T0107807, T0107806. Multiple transactions came from a new device in a short span. Recent transactions span 3 IP countries (threshold 3). The triggered rule set matches a suspicious behaviour profile.
- Context: Context is supportive of legitimacy. Note N00204 (2026-02-27T12:47:14): Support chat. Customer upgraded their phone on the 27th and could not log in. Walked them through re-registration. Verified with video KYC.
- Network: The network footprint is suspicious. The account used more than one device during the alert window. Device DX01489 is a new but isolated device for this account. The account used several merchants, which is common in both legitimate and fraudulent behaviour.
- Disposition: No irreversible action is recommended for a likely legitimate account.
- Supervisor: Behaviour finding: Behaviour is fraud-like. 4 transaction(s) exceeded 5000: T0107808, T0107807, T0107806. Multiple transactions came from a new device in a short span. Recent transactions span 3 IP countries (threshold 3). The triggered rule set matches a suspicious behaviour profile. Context finding: Context is supportive of legitimacy. Note N00204 (2026-02-27T12:47:14): Support chat. Customer upgraded their phone on the 27th and could not log in. Walked them through re-registration. Verified with video KYC. Network finding: The network footprint is suspicious. The account used more than one device during the alert window. Device DX01489 is a new but isolated device for this account. The account used several merchants, which is common in both legitimate and fraudulent behaviour.

## A00000 — insufficient_evidence

- Confidence: medium
- Behaviour: Behaviour is fraud-like. 4 transaction(s) exceeded 5000: T0107395, T0107394, T0107393. Multiple transactions came from a new device in a short span. Recent transactions span 3 IP countries (threshold 3). The triggered rule set matches a suspicious behaviour profile.
- Context: Context is mixed. The note history was not decisive either way.
- Network: The network footprint is suspicious. The account used more than one device during the alert window. Device DX01459 is a new but isolated device for this account. The account used several merchants, which is common in both legitimate and fraudulent behaviour.
- Disposition: The evidence is insufficient to justify any irreversible action.
- Supervisor: Behaviour finding: Behaviour is fraud-like. 4 transaction(s) exceeded 5000: T0107395, T0107394, T0107393. Multiple transactions came from a new device in a short span. Recent transactions span 3 IP countries (threshold 3). The triggered rule set matches a suspicious behaviour profile. Context finding: Context is mixed. The note history was not decisive either way. Network finding: The network footprint is suspicious. The account used more than one device during the alert window. Device DX01459 is a new but isolated device for this account. The account used several merchants, which is common in both legitimate and fraudulent behaviour. Missing evidence that would resolve this: a contemporaneous customer contact, a dispute, or verified device ownership.

