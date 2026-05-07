


| Repo                                 | Description                                                                           |
| ------------------------------------ | ------------------------------------------------------------------------------------- |
| hotelops-osdchat-ai-guest-services   | Code repo for Checkin, checkout requests                                              |
| hotelops-osdchat-ai-house-keeping    | Towels, room cleaning, amenties                                                       |
| hotelops-osdchat-ai-food-services    |                                                                                       |
| hotelops-odschat-ai-guest-mcp-server | MCP Server hosting the Guest Services for Check in, checkout, house keeping services. |




```github repo
```hotel-mcp-server/
├── adapters/
│   ├── pms-adapter/      # Late checkout via PMS API
│   │   ├── late_checkout_tool.js
│   │   └── pms_client.js
│   └── housekeeping-adapter/  # Towels, room cleaning via POST
│       ├── towels_tool.js
│       └── room_cleaning_tool.js
├── src/
│   ├── server.js         # Core MCP server (tools/list, tools/call)
│   └── index.js
├── .env.example          # API keys for PMS/Housekeeping
├── docker-compose.yml    # For easy deployment
└── README.md             # Setup, tools list
