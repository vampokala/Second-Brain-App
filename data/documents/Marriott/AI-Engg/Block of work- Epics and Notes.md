
**Discovery AI Solution**  

- Infrsturcture setup - MOSD-16134
- Prove the pattern - [MOSD-16610-](https://marriottcloud.atlassian.net/browse/MOSD-16610)
- Disassociated from core systems - Not applicable
- Integrated Solution Arch between TIP.AI and ECMP - [MOSD-16122](https://marriottcloud.atlassian.net/browse/MOSD-16122?atlOrigin=eyJpIjoiYzZkYWNmNWZiYzJiNGYzZGE1ZmQwYWUyM2E1MTkyMTIiLCJwIjoiaiJ9)
- Build application per contracts 
- Simulate guest/associate responses based on Bonvoy App chat -MOSD-16138
	- UI to visualize the Guest/Associate messages for a specific timeline or data, searchable by user/guest details retrieve the information.
- Get back AI responses -- Evaluation Framework - MOSD-16138
	- How LLM retrieves the relevant information from Data Source(RAG)
	- How LLM generates the response based on the Context provided (Generation)
	- LLM Response validating fields by contact 
- Build a worker to connect with Product Catalog and provide specific information for Checkin or Checkout related. (New Story)


  
Shadow Mode (Production)  

- High level today
- Sources
- - Product Catalog
    - Auto responses in GXP
    - Previous responses from the associate
    - - Bonvoy App chat history
        - SMS chat history
    - Reservation information (later)
- Thank you loop and perhaps more based on Top 5 analysis
- AI in prod reviewing Bonvoy App and SMS
- Evaluate the message and determine next step
- Output of evaluation for next steps - ops, tech, legal, etc.
- - Socialization 30-45 days with hotel engagement
    - Training for solid responses, best foot forward