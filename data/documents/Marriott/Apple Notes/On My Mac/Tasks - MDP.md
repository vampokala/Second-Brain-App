No pre-arrival message instead using conversation id

gcv_guest_information field info such as name, confirmation number, altCustId(JSONB), 

Conversation id

Customizing this schema for MDP only

DLR for different to GXP and MDP with longer TTLY 

Two schemas 

**Phase 1 (80-95% of KPIs)** 
**First Schema** - Content Reservation info, conversation info (Pre-Arrival Life cycle info). - User profile will be created at MDP
**Second schema** - Payload reference to conversation id,  TIP AI intents response(Guest/Associate responses). — Post a message to Kafka topic
**Third schema** - consent information 
**Fourth schema** - DLR

**Phase 2**
SFTP batch process for free form text ——-  Dependent KPIs for the raw user data

Notes - No User free form body