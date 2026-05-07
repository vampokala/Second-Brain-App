
**Positives**

Session API enhancements to capture the Guest context with reservation and other info.
Session Patch -This is great addition to update ongoing stay related changes
Message Response- 




Questions
**Session Request**
As per the proposal, every message requests the session initialization with TIP AI. if the user is no longer responding to messages then the session will not be utilized. Tokens could be wasted or non utilized. 
Option - TIP AI adapter will hold the session metadata, it should send initiate upon first message from Guest/Associate to TIP AI platform.

TIP AI enhancements
Who performs these changes? 

Session lifecycle:
Closed at checkout or stay expiration. -- Is this automatic event by TIP AI based on the reservation details or manual invocation by the process? 

Per message table 
reply_mode - classify_only, draft or draft+action  these params are handled through ECMP? 

300 reservations 
10 Guests responsnded - 10 sessions 
2 reservations  Associate reaching out to guests using SMS channel then open up a session 